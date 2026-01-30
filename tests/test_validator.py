#!/usr/bin/env python3
"""
Tests simplificados para el Validator Service
No requieren RabbitMQ ni dependencias externas
"""

import unittest
import json
from datetime import datetime

# Schemas JSON (copiados del validator real)
BASE_SCHEMA = {
    "type": "object",
    "properties": {
        "event_id": {"type": "string", "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"},
        "timestamp": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"},
        "region": {"type": "string", "enum": ["norte", "sur", "centro", "este", "oeste"]},
        "source": {"type": "string"},
        "schema_version": {"type": "string"},
        "payload": {"type": "object"}
    },
    "required": ["event_id", "timestamp", "region", "source", "schema_version", "payload"]
}

PAYLOAD_SCHEMAS = {
    "security.incident": {
        "type": "object",
        "required": ["crime_type", "severity", "location", "reported_by"],
        "properties": {
            "crime_type": {"type": "string"},
            "severity": {"type": "string"},
            "location": {"type": "object", "required": ["latitude", "longitude"]},
            "reported_by": {"type": "string"}
        }
    },
    "survey.victimization": {
        "type": "object",
        "required": ["survey_id", "respondent_age", "victimization_type", "reported"],
        "properties": {
            "respondent_age": {"type": "integer"},
            "reported": {"type": "boolean"}
        }
    },
    "migration.case": {
        "type": "object",
        "required": ["case_id", "case_type", "status", "origin_country"],
        "properties": {
            "status": {"type": "string"}
        }
    }
}

def validate_event(event_data):
    """
    Retorna (True, None) si es válido.
    Retorna (False, error_msg) si es inválido.
    """
    try:
        # 1. Validar Estructura Base
        validate_schema(event_data, BASE_SCHEMA)
        
        # 2. Validar que 'source' coincida con la lógica
        source = event_data.get("source")
        payload = event_data.get("payload")

        if source in PAYLOAD_SCHEMAS:
            validate_schema(payload, PAYLOAD_SCHEMAS[source])
        else:
            return False, f"Tipo de evento desconocido: {source}"
            
        return True, None

    except ValidationError as e:
        return False, f"Error de Schema: {e.message}"
    except Exception as e:
        return False, f"Error inesperado: {str(e)}"

def validate_schema(data, schema):
    """Validación simple de schema sin jsonschema"""
    # Validar tipo
    if "type" in schema:
        if schema["type"] == "object":
            if not isinstance(data, dict):
                raise ValidationError("Se espera un objeto")
        elif schema["type"] == "string":
            if not isinstance(data, str):
                raise ValidationError("Se espera un string")
        elif schema["type"] == "integer":
            if not isinstance(data, int):
                raise ValidationError("Se espera un integer")
        elif schema["type"] == "boolean":
            if not isinstance(data, bool):
                raise ValidationError("Se espera un boolean")
    
    # Validar propiedades requeridas
    if isinstance(data, dict) and "required" in schema:
        for field in schema["required"]:
            if field not in data:
                raise ValidationError(f"Campo requerido faltante: {field}")
    
    # Validar propiedades específicas
    if isinstance(data, dict) and "properties" in schema:
        for field, field_schema in schema["properties"].items():
            if field in data:
                validate_schema(data[field], field_schema)
    
    # Validar enum
    if "enum" in schema:
        if data not in schema["enum"]:
            raise ValidationError(f"Valor no permitido: {data}")
    
    # Validar pattern
    if "pattern" in schema and isinstance(data, str):
        import re
        if not re.match(schema["pattern"], data):
            raise ValidationError(f"Formato inválido: {data}")

class ValidationError(Exception):
    """Error de validación personalizado"""
    def __init__(self, message):
        self.message = message
        super().__init__(message)

class TestValidatorSchemas(unittest.TestCase):
    """Tests para los schemas de validación del validator"""

    def test_valid_security_incident(self):
        """Test que un evento security.incident válido pasa la validación"""
        event = {
            "event_id": "550e8400-e29b-41d4-a716-446655440000",
            "timestamp": "2025-01-15T10:30:00Z",
            "region": "norte",
            "source": "security.incident",
            "schema_version": "1.0",
            "payload": {
                "crime_type": "theft",
                "severity": "medium",
                "location": {
                    "latitude": -33.4489,
                    "longitude": -70.6693
                },
                "reported_by": "citizen"
            }
        }
        
        is_valid, error_msg = validate_event(event)
        self.assertTrue(is_valid, f"Evento válido fue rechazado: {error_msg}")

    def test_valid_victimization_survey(self):
        """Test que un evento survey.victimization válido pasa la validación"""
        event = {
            "event_id": "550e8400-e29b-41d4-a716-446655440000",
            "timestamp": "2025-01-15T10:30:00Z",
            "region": "sur",
            "source": "survey.victimization",
            "schema_version": "1.0",
            "payload": {
                "survey_id": "srv-2025-001",
                "respondent_age": 35,
                "victimization_type": "property_crime",
                "incident_date": "2025-01-10",
                "reported": True
            }
        }
        
        is_valid, error_msg = validate_event(event)
        self.assertTrue(is_valid, f"Evento válido fue rechazado: {error_msg}")

    def test_valid_migration_case(self):
        """Test que un evento migration.case válido pasa la validación"""
        event = {
            "event_id": "550e8400-e29b-41d4-a716-446655440000",
            "timestamp": "2025-01-15T10:30:00Z",
            "region": "centro",
            "source": "migration.case",
            "schema_version": "1.0",
            "payload": {
                "case_id": "mig-2025-001",
                "case_type": "asylum",
                "status": "pending",
                "origin_country": "Venezuela",
                "application_date": "2025-01-01"
            }
        }
        
        is_valid, error_msg = validate_event(event)
        self.assertTrue(is_valid, f"Evento válido fue rechazado: {error_msg}")

    def test_invalid_uuid_format(self):
        """Test que UUID inválido falla validación"""
        event = {
            "event_id": "invalid-uuid",
            "timestamp": "2025-01-15T10:30:00Z",
            "region": "norte",
            "source": "security.incident",
            "schema_version": "1.0",
            "payload": {
                "crime_type": "theft",
                "severity": "medium",
                "location": {"latitude": -33.4489, "longitude": -70.6693},
                "reported_by": "citizen"
            }
        }
        
        is_valid, error_msg = validate_event(event)
        self.assertFalse(is_valid)
        self.assertIn("Formato inválido", error_msg)

    def test_invalid_timestamp_format(self):
        """Test que timestamp inválido falla validación"""
        event = {
            "event_id": "550e8400-e29b-41d4-a716-446655440000",
            "timestamp": "2025/01/15 10:30:00",  # Formato inválido
            "region": "norte",
            "source": "security.incident",
            "schema_version": "1.0",
            "payload": {
                "crime_type": "theft",
                "severity": "medium",
                "location": {"latitude": -33.4489, "longitude": -70.6693},
                "reported_by": "citizen"
            }
        }
        
        is_valid, error_msg = validate_event(event)
        self.assertFalse(is_valid)
        self.assertIn("Formato inválido", error_msg)

    def test_invalid_region(self):
        """Test que región inválida falla validación"""
        event = {
            "event_id": "550e8400-e29b-41d4-a716-446655440000",
            "timestamp": "2025-01-15T10:30:00Z",
            "region": "region_invalida",
            "source": "security.incident",
            "schema_version": "1.0",
            "payload": {
                "crime_type": "theft",
                "severity": "medium",
                "location": {"latitude": -33.4489, "longitude": -70.6693},
                "reported_by": "citizen"
            }
        }
        
        is_valid, error_msg = validate_event(event)
        self.assertFalse(is_valid)
        self.assertIn("Valor no permitido", error_msg)

    def test_missing_required_fields(self):
        """Test que falta de campos requeridos falla validación"""
        event = {
            "event_id": "550e8400-e29b-41d4-a716-446655440000",
            "timestamp": "2025-01-15T10:30:00Z",
            # Falta "region"
            "source": "security.incident",
            "schema_version": "1.0",
            "payload": {
                "crime_type": "theft",
                "severity": "medium",
                "location": {"latitude": -33.4489, "longitude": -70.6693},
                "reported_by": "citizen"
            }
        }
        
        is_valid, error_msg = validate_event(event)
        self.assertFalse(is_valid)
        self.assertIn("Campo requerido faltante", error_msg)

    def test_invalid_payload_security_incident(self):
        """Test que payload inválido de security.incident falla validación"""
        event = {
            "event_id": "550e8400-e29b-41d4-a716-446655440000",
            "timestamp": "2025-01-15T10:30:00Z",
            "region": "norte",
            "source": "security.incident",
            "schema_version": "1.0",
            "payload": {
                "crime_type": "theft",
                # Falta "severity"
                "location": {"latitude": -33.4489, "longitude": -70.6693},
                "reported_by": "citizen"
            }
        }
        
        is_valid, error_msg = validate_event(event)
        self.assertFalse(is_valid)
        self.assertIn("Campo requerido faltante", error_msg)

    def test_invalid_payload_survey_types(self):
        """Test que tipos incorrectos en payload de survey fallan validación"""
        event = {
            "event_id": "550e8400-e29b-41d4-a716-446655440000",
            "timestamp": "2025-01-15T10:30:00Z",
            "region": "sur",
            "source": "survey.victimization",
            "schema_version": "1.0",
            "payload": {
                "survey_id": "srv-2025-001",
                "respondent_age": "35",  # Debería ser integer, no string
                "victimization_type": "property_crime",
                "incident_date": "2025-01-10",
                "reported": True
            }
        }
        
        is_valid, error_msg = validate_event(event)
        self.assertFalse(is_valid)
        self.assertIn("Se espera un integer", error_msg)

    def test_unknown_event_type(self):
        """Test que tipo de evento desconocido falla validación"""
        event = {
            "event_id": "550e8400-e29b-41d4-a716-446655440000",
            "timestamp": "2025-01-15T10:30:00Z",
            "region": "norte",
            "source": "unknown.event.type",
            "schema_version": "1.0",
            "payload": {
                "some_field": "some_value"
            }
        }
        
        is_valid, error_msg = validate_event(event)
        self.assertFalse(is_valid)
        self.assertIn("Tipo de evento desconocido", error_msg)

    def test_non_dict_event(self):
        """Test que evento no-dict falla validación"""
        event = "esto no es un diccionario"
        
        is_valid, error_msg = validate_event(event)
        self.assertFalse(is_valid)
        self.assertIn("Se espera un objeto", error_msg)

    def test_empty_payload(self):
        """Test que payload vacío es válido para tipos desconocidos"""
        event = {
            "event_id": "550e8400-e29b-41d4-a716-446655440000",
            "timestamp": "2025-01-15T10:30:00Z",
            "region": "norte",
            "source": "unknown.type",
            "schema_version": "1.0",
            "payload": {}
        }
        
        is_valid, error_msg = validate_event(event)
        # Debería ser inválido porque el tipo es desconocido
        self.assertFalse(is_valid)
        self.assertIn("Tipo de evento desconocido", error_msg)

if __name__ == '__main__':
    unittest.main()
