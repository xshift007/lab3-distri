import os

# RabbitMQ
RABBIT_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
RABBIT_PORT = int(os.getenv('RABBITMQ_PORT', 5672))

# Escuchamos los resúmenes del Aggregator
INPUT_EXCHANGE = 'analytics_exchange'
QUEUE_NAME = 'dashboard_queue'

# Configuración Web
WEB_PORT = int(os.getenv('WEB_PORT', 5000))