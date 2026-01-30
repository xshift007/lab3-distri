import os

# RabbitMQ
RABBIT_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
RABBIT_PORT = int(os.getenv('RABBITMQ_PORT', 5672))

# Exchanges
INPUT_EXCHANGE = 'processing_exchange'  # Viene del Validator
OUTPUT_EXCHANGE = 'analytics_exchange'  # Resultados agregados

# Queue específica del aggregator
QUEUE_NAME = 'aggregator_queue'

# Configuración de Agregación
AGGREGATION_WINDOW = float(os.getenv('AGGREGATION_WINDOW', 5.0)) # Segundos