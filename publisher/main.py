import json
import uuid
import time
import random
import argparse
import pika
from datetime import datetime, timezone
import settings  # <--- Importamos nuestra configuración

# --- Generadores de Datos ---

def get_timestamp():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

def generate_base_event(source_type):
    """Crea la estructura común requerida por el PDF"""
    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": get_timestamp(),
        "region": random.choice(settings.REGIONS), # Usa las regiones de settings
        "source": source_type,
        "schema_version": "1.0",
        "correlation_id": f"corr-{random.randint(1000, 9999)}",
        "payload": {}
    }

def create_security_incident():
    event = generate_base_event("security.incident")
    event["payload"] = {
        "crime_type": random.choice(["theft", "assault", "burglary", "homicide"]),
        "severity": random.choice(["low", "medium", "high"]),
        "location": {
            "latitude": round(random.uniform(-55.0, -17.0), 4),
            "longitude": round(random.uniform(-75.0, -66.0), 4)
        },
        "reported_by": random.choice(["citizen", "police", "app"])
    }
    return event

def create_victimization_survey():
    event = generate_base_event("survey.victimization")
    event["payload"] = {
        "survey_id": f"srv-{random.randint(10000, 99999)}",
        "respondent_age": random.randint(18, 90),
        "victimization_type": random.choice(["theft", "assault"]),
        "incident_date": datetime.now().strftime("%Y-%m-%d"),
        "reported": random.choice([True, False])
    }
    return event

def create_migration_case():
    event = generate_base_event("migration.case")
    event["payload"] = {
        "case_id": f"mig-{random.randint(10000, 99999)}",
        "case_type": random.choice(["asylum", "visa", "residence"]),
        "status": random.choice(["pending", "approved", "rejected"]),
        "origin_country": random.choice(["Venezuela", "Haiti", "Peru", "Colombia"]),
        "application_date": datetime.now().strftime("%Y-%m-%d")
    }
    return event

# --- Lógica de RabbitMQ ---

def connect_rabbitmq():
    """Conecta con reintentos infinitos hasta que RabbitMQ esté listo"""
    while True:
        try:
            params = pika.ConnectionParameters(host=settings.RABBIT_HOST, port=settings.RABBIT_PORT)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            
            # Declaramos el Exchange aquí para asegurar que exista antes de publicar
            channel.exchange_declare(exchange=settings.EXCHANGE_NAME, exchange_type='topic', durable=True)
            
            print(f"[*] Publisher conectado a {settings.RABBIT_HOST}")
            return connection, channel
        except pika.exceptions.AMQPConnectionError:
            print(f"[!] RabbitMQ no está listo en {settings.RABBIT_HOST}. Reintentando en 5s...")
            time.sleep(5)

def publish_event(channel, event):
    routing_key = event["source"]
    channel.basic_publish(
        exchange=settings.EXCHANGE_NAME,
        routing_key=routing_key,
        body=json.dumps(event),
        properties=pika.BasicProperties(
            delivery_mode=2, # Mensaje persistente
            content_type='application/json'
        )
    )
    print(f"[x] Enviado {routing_key}: {event['event_id']}")

def main():
    # Permitimos configurar la semilla (seed) por argumentos para pruebas reproducibles
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, default=None, help='Seed para random')
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)
        print(f"[*] Usando Seed: {args.seed}")

    connection, channel = connect_rabbitmq()

    try:
        # Calculamos el delay base según la configuración
        delay = 1.0 / settings.EVENT_RATE
        
        while True:
            # 1. Lógica Burst (Opcional)
            if settings.ENABLE_BURST and random.random() < 0.1: # 10% de probabilidad de ráfaga
                print("!!! INICIANDO RÁFAGA (BURST) !!!")
                burst_size = random.randint(5, 15)
                for _ in range(burst_size):
                    event = create_security_incident() # En ráfaga solemos mandar incidentes
                    publish_event(channel, event)
            
            # 2. Generación Normal
            # Elegimos un tipo de evento al azar
            generator = random.choices(
                [create_security_incident, create_victimization_survey, create_migration_case],
                weights=[0.5, 0.3, 0.2]
            )[0]
            
            event = generator()
            publish_event(channel, event)
            
            # Esperar para respetar el Rate Limit
            time.sleep(delay)

    except KeyboardInterrupt:
        print("Deteniendo Publisher...")
        connection.close()

if __name__ == "__main__":
    main()