import os

# RabbitMQ Connection
RABBIT_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
RABBIT_PORT = int(os.getenv('RABBITMQ_PORT', 5672))

# Exchanges y Queues
INPUT_EXCHANGE = 'events_exchange'      # Donde publica el Generator
OUTPUT_EXCHANGE = 'processing_exchange' # Donde enviamos los válidos
DLQ_EXCHANGE = 'dlq_exchange'           # Donde enviamos los inválidos

INPUT_QUEUE = 'validator_input_queue'

# Routing Keys (Topics) que vamos a escuchar
LISTEN_TOPICS = ["security.incident", "survey.victimization", "migration.case"]