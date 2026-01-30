import os

# --- Conexión a RabbitMQ ---
RABBIT_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
RABBIT_PORT = int(os.getenv('RABBITMQ_PORT', 5672))
EXCHANGE_NAME = os.getenv('EXCHANGE_NAME', 'events_exchange')

# --- Configuración de Simulación ---
# Tasa de eventos por segundo (default: 1 evento/seg)
EVENT_RATE = float(os.getenv('EVENT_RATE', 1.0))

# Modo Ráfaga: Si es True, ocasionalmente envía muchos eventos juntos
ENABLE_BURST = os.getenv('ENABLE_BURST', 'false').lower() == 'true'

# Regiones permitidas (configurable por variable de entorno separada por comas)
# Ejemplo: REGIONS="norte,sur"
REGIONS_ENV = os.getenv('REGIONS', 'norte,sur,centro,este,oeste')
REGIONS = REGIONS_ENV.split(',')