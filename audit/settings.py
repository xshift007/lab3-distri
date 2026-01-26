import os

# RabbitMQ
RABBIT_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
RABBIT_PORT = int(os.getenv('RABBITMQ_PORT', 5672))

# Exchange a auditar
# Generalmente auditamos los eventos YA validados ("processing_exchange")
# Pero podrías cambiarlo a "events_exchange" si quieres auditar incluso lo crudo.
TARGET_EXCHANGE = os.getenv('TARGET_EXCHANGE', 'processing_exchange')

# Cola específica (Durable para no perder logs si el servicio se cae)
QUEUE_NAME = 'audit_queue'

# Archivo de salida
LOG_FILE_PATH = os.getenv('LOG_FILE_PATH', '/data/audit_log.jsonl')