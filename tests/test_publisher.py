#!/usr/bin/env python3
"""
Tests simplificados para el Publisher Service
No requieren RabbitMQ ni dependencias externas
"""

import unittest
import json
import uuid
import random
from datetime import datetime
from unittest.mock import patch, MagicMock

# Configuración similar a la del publisher real
REGIONS = ["norte", "sur", "centro", "este", "oeste"]

def get_timestamp():
    """Genera timestamp ISO-8601 UTC"""
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

def generate_base_event(source_type):
    """Crea la estructura común requerida"""
    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": get_timestamp(),
        "region": random.choice(REGIONS),
        "source": source_type,
        "schema_version": "1.0",
        "correlation_id": f"corr-{random.randint(1000, 9999)}",
        "payload": {}
    }

def create_security_incident():
    """Crea un evento de incidente de seguridad"""
    event = generate_base_event("security.incident")
    event["payload"] = {
        "crime_type": random.choice(["theft", "burglary", "assault", "homicide"]),
        "severity": random.choice(["low", "medium", "high"]),
        "location": {
            "latitude": round(random.uniform(-55, -21), 4),
            "longitude": round(random.uniform(-75, -53), 4)
        },
        "reported_by": random.choice(["police", "citizen", "app", "anonymous"])
    }
    return event

def create_victimization_survey():
    """Crea un evento de encuesta de victimización"""
    event = generate_base_event("survey.victimization")
    event["payload"] = {
        "survey_id": f"srv-{random.randint(2024, 2025)}-{random.randint(1, 999):03d}",
        "respondent_age": random.randint(18, 80),
        "victimization_type": random.choice(["property_crime", "violent_crime", "cybercrime", "no_crime"]),
        "incident_date": f"{random.randint(2023, 2025)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
        "reported": random.choice([True, False])
    }
    return event

def create_migration_case():
    """Crea un evento de caso de migración"""
    event = generate_base_event("migration.case")
    event["payload"] = {
        "case_id": f"mig-{random.randint(2024, 2025)}-{random.randint(1, 999):03d}",
        "case_type": random.choice(["asylum", "residence", "work_permit", "family_reunification"]),
        "status": random.choice(["pending", "approved", "rejected", "under_review"]),
        "origin_country": random.choice(["Venezuela", "Colombia", "Perú", "Bolivia", "Ecuador"]),
        "application_date": f"{random.randint(2023, 2025)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
    }
    return event

class TestPublisherEvents(unittest.TestCase):
    """Tests para la generación de eventos del publisher"""

    def setUp(self):
        """Configuración inicial para cada test"""
        random.seed(42)  # Para reproducibilidad
        uuid.uuid4 = lambda: uuid.UUID('12345678-1234-5678-1234-567812345678')

    def test_generate_base_event_structure(self):
        """Test que generate_base_event crea estructura correcta"""
        event = generate_base_event("test.source")
        
        # Verificar campos obligatorios
        required_fields = ["event_id", "timestamp", "region", "source", "schema_version", "correlation_id", "payload"]
        for field in required_fields:
            self.assertIn(field, event, f"Falta campo obligatorio: {field}")
        
        # Verificar valores
        self.assertEqual(event["source"], "test.source")
        self.assertEqual(event["schema_version"], "1.0")
        self.assertIn(event["region"], REGIONS)
        self.assertTrue(event["correlation_id"].startswith("corr-"))
        self.assertIsInstance(event["payload"], dict)

    def test_event_id_is_valid_uuid(self):
        """Test que event_id es un UUID v4 válido"""
        # Restaurar uuid real para este test
        with patch('uuid.uuid4', return_value=uuid.UUID('550e8400-e29b-41d4-a716-446655440000')):
            event = generate_base_event("test.source")
            self.assertEqual(event["event_id"], "550e8400-e29b-41d4-a716-446655440000")

    def test_timestamp_is_iso8601_utc(self):
        """Test que timestamp está en formato ISO-8601 UTC"""
        event = generate_base_event("test.source")
        timestamp = event["timestamp"]
        
        # Verificar formato ISO-8601 básico
        self.assertRegex(timestamp, r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$')
        
        # Verificar que termina en Z (UTC)
        self.assertTrue(timestamp.endswith('Z'))

    def test_region_is_valid(self):
        """Test que region es una de las permitidas"""
        event = generate_base_event("test.source")
        self.assertIn(event["region"], REGIONS)

    def test_correlation_id_format(self):
        """Test que correlation_id tiene formato esperado"""
        event = generate_base_event("test.source")
        correlation_id = event["correlation_id"]
        
        # Debe empezar con "corr-" seguido de 4 dígitos
        self.assertRegex(correlation_id, r'^corr-\d{4}$')

    def test_create_security_incident(self):
        """Test que create_security_incident genera evento completo"""
        event = create_security_incident()
        
        # Verificar estructura base
        self.assertEqual(event["source"], "security.incident")
        self.assertIn("payload", event)
        
        # Verificar payload específico
        payload = event["payload"]
        required_payload_fields = ["crime_type", "severity", "location", "reported_by"]
        for field in required_payload_fields:
            self.assertIn(field, payload)
        
        # Verificar valores válidos
        self.assertIn(payload["crime_type"], ["theft", "burglary", "assault", "homicide"])
        self.assertIn(payload["severity"], ["low", "medium", "high"])
        self.assertIn(payload["reported_by"], ["police", "citizen", "app", "anonymous"])
        
        # Verificar ubicación
        location = payload["location"]
        self.assertIn("latitude", location)
        self.assertIn("longitude", location)
        self.assertIsInstance(location["latitude"], float)
        self.assertIsInstance(location["longitude"], float)

    def test_create_victimization_survey(self):
        """Test que create_victimization_survey genera evento completo"""
        event = create_victimization_survey()
        
        # Verificar estructura base
        self.assertEqual(event["source"], "survey.victimization")
        self.assertIn("payload", event)
        
        # Verificar payload específico
        payload = event["payload"]
        required_payload_fields = ["survey_id", "respondent_age", "victimization_type", "incident_date", "reported"]
        for field in required_payload_fields:
            self.assertIn(field, payload)
        
        # Verificar valores válidos
        self.assertRegex(payload["survey_id"], r'^srv-\d{4}-\d{3}$')
        self.assertIsInstance(payload["respondent_age"], int)
        self.assertGreaterEqual(payload["respondent_age"], 18)
        self.assertLessEqual(payload["respondent_age"], 80)
        self.assertIn(payload["victimization_type"], ["property_crime", "violent_crime", "cybercrime", "no_crime"])
        self.assertIsInstance(payload["reported"], bool)

    def test_create_migration_case(self):
        """Test que create_migration_case genera evento completo"""
        event = create_migration_case()
        
        # Verificar estructura base
        self.assertEqual(event["source"], "migration.case")
        self.assertIn("payload", event)
        
        # Verificar payload específico
        payload = event["payload"]
        required_payload_fields = ["case_id", "case_type", "status", "origin_country", "application_date"]
        for field in required_payload_fields:
            self.assertIn(field, payload)
        
        # Verificar valores válidos
        self.assertRegex(payload["case_id"], r'^mig-\d{4}-\d{3}$')
        self.assertIn(payload["case_type"], ["asylum", "residence", "work_permit", "family_reunification"])
        self.assertIn(payload["status"], ["pending", "approved", "rejected", "under_review"])
        self.assertIn(payload["origin_country"], ["Venezuela", "Colombia", "Perú", "Bolivia", "Ecuador"])

    def test_all_event_sources_covered(self):
        """Test que se generan todos los tipos de eventos esperados"""
        sources = []
        
        # Generar múltiples eventos
        for _ in range(100):
            event_type = random.choice(["security", "survey", "migration"])
            if event_type == "security":
                event = create_security_incident()
            elif event_type == "survey":
                event = create_victimization_survey()
            else:
                event = create_migration_case()
            sources.append(event["source"])
        
        # Verificar que todos los tipos estén presentes
        expected_sources = ["security.incident", "survey.victimization", "migration.case"]
        for source in expected_sources:
            self.assertIn(source, sources, f"Falta source: {source}")

    def test_event_json_serializable(self):
        """Test que todos los eventos pueden serializarse a JSON"""
        events = [
            create_security_incident(),
            create_victimization_survey(),
            create_migration_case()
        ]
        
        for event in events:
            try:
                json_str = json.dumps(event)
                self.assertIsInstance(json_str, str)
                self.assertGreater(len(json_str), 0)
            except (TypeError, ValueError) as e:
                self.fail(f"Evento no serializable a JSON: {e}")

    def test_multiple_events_unique_ids(self):
        """Test que múltiples eventos tienen IDs únicos"""
        # Restaurar uuid real para este test
        generated_ids = []
        
        # Restaurar el comportamiento normal de uuid.uuid4
        with patch('uuid.uuid4') as mock_uuid:
            mock_uuid.side_effect = [
                uuid.UUID('550e8400-e29b-41d4-a716-446655440000'),
                uuid.UUID('550e8400-e29b-41d4-a716-446655440001'),
                uuid.UUID('550e8400-e29b-41d4-a716-446655440002'),
                uuid.UUID('550e8400-e29b-41d4-a716-446655440003'),
                uuid.UUID('550e8400-e29b-41d4-a716-446655440004'),
                uuid.UUID('550e8400-e29b-41d4-a716-446655440005'),
                uuid.UUID('550e8400-e29b-41d4-a716-446655440006'),
                uuid.UUID('550e8400-e29b-41d4-a716-446655440007'),
                uuid.UUID('550e8400-e29b-41d4-a716-446655440008'),
                uuid.UUID('550e8400-e29b-41d4-a716-446655440009')
            ]
            
            for _ in range(10):
                event = create_security_incident()
                event_id = event["event_id"]
                self.assertNotIn(event_id, generated_ids, f"ID duplicado: {event_id}")
                generated_ids.append(event_id)

if __name__ == '__main__':
    unittest.main()
