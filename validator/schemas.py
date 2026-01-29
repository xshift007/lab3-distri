# Esquema base (campos comunes)
BASE_SCHEMA = {
    "type": "object",
    "properties": {
        "event_id": {"type": "string", "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"}, # Regex UUID v4
        "timestamp": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"}, # Simple ISO format check
        "region": {"type": "string", "enum": ["norte", "sur", "centro", "este", "oeste"]},
        "source": {"type": "string"},
        "schema_version": {"type": "string"},
        "payload": {"type": "object"}
    },
    "required": ["event_id", "timestamp", "region", "source", "schema_version", "payload"]
}

# Esquemas específicos para el payload
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