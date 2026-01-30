import json
import time
import uuid
from datetime import datetime

import pika

import settings

# --- ESTADO EN MEMORIA --
# En un sistema real distribuido, esto debería estar en Redis
current_window_start = time.time()
processed_ids = set()     # Para Deduplicación
stats_buffer = {}         # Estructura: { "norte": { "theft": 5, "assault": 1 }, ... }
event_ids_by_region = {}  # Estructura: { "norte": {"id1", "id2"} }

def connect_rabbitmq():
    while True:
        try:
            params = pika.ConnectionParameters(host=settings.RABBIT_HOST, port=settings.RABBIT_PORT)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()

            # Declarar Exchanges
            channel.exchange_declare(exchange=settings.INPUT_EXCHANGE, exchange_type='topic', durable=True)
            channel.exchange_declare(exchange=settings.OUTPUT_EXCHANGE, exchange_type='topic', durable=True)

            # Declarar y bindear cola
            channel.queue_declare(queue=settings.QUEUE_NAME, durable=True)
            # Escuchamos TODO (#) lo que venga validado
            channel.queue_bind(exchange=settings.INPUT_EXCHANGE, queue=settings.QUEUE_NAME, routing_key="#")

            print(f"[*] Aggregator conectado. Ventana de {settings.AGGREGATION_WINDOW}s")
            return connection, channel
        except pika.exceptions.AMQPConnectionError:
            print(f"[!] Esperando a RabbitMQ...")
            time.sleep(5)

def flush_window(channel):
    """Publica los resultados acumulados y reinicia el buffer"""
    global current_window_start, stats_buffer, processed_ids, event_ids_by_region

    if not stats_buffer:
        # Si no hubo datos, solo actualizamos el tiempo
        current_window_start = time.time()
        return

    # Crear mensaje de resumen
    summary = {
        "type": "window_summary",
        "window_start_iso": datetime.fromtimestamp(current_window_start).isoformat(),
        "window_end_iso": datetime.now().isoformat(),
        "total_processed": len(processed_ids),
        "stats_by_region": stats_buffer
    }

    # Publicar al exchange de analytics
    channel.basic_publish(
        exchange=settings.OUTPUT_EXCHANGE,
        routing_key="analytics.window",
        body=json.dumps(summary),
        properties=pika.BasicProperties(delivery_mode=2)
    )

    # Publicar métricas diarias por región con trazabilidad
    for region, region_stats in stats_buffer.items():
        metric_msg = {
            "metric_id": str(uuid.uuid4()),
            "date": datetime.now().date().isoformat(),
            "region": region,
            "run_id": "default",
            "metrics": region_stats,
            "input_event_ids": sorted(event_ids_by_region.get(region, set())),
        }
        channel.basic_publish(
            exchange=settings.OUTPUT_EXCHANGE,
            routing_key="metrics.daily",
            body=json.dumps(metric_msg),
            properties=pika.BasicProperties(delivery_mode=2),
        )

    print(f" [S] Ventana cerrada. Publicado resumen de {len(processed_ids)} eventos.")
    
    # Reiniciar estado
    stats_buffer = {}
    processed_ids = set()
    event_ids_by_region = {}
    current_window_start = time.time()

def process_event(event):
    """Lógica de agregación pura"""
    region = event.get("region", "unknown")
    source = event.get("source", "unknown")
    event_id = event.get("event_id")
    
    # Inicializar contadores si no existen
    if region not in stats_buffer:
        stats_buffer[region] = {}
    if source not in stats_buffer[region]:
        stats_buffer[region][source] = 0
        
    stats_buffer[region][source] += 1

    if event_id:
        event_ids_by_region.setdefault(region, set()).add(event_id)

def callback(ch, method, properties, body):
    
    try:
        event = json.loads(body)
        event_id = event.get("event_id")

        # 1. DEDUPLICACIÓN (Idempotencia)
        if event_id in processed_ids:
            print(f" [d] Duplicado detectado e ignorado: {event_id}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        # 2. PROCESAMIENTO
        process_event(event)
        processed_ids.add(event_id)

        # 3. VERIFICAR SI CERRAMOS VENTANA
        # verificamos el tiempo en cada mensaje. Si no llegan mensajes, la ventana no se cierra.
        if time.time() - current_window_start >= settings.AGGREGATION_WINDOW:
            flush_window(ch)

    except Exception as e:
        print(f" [!] Error agregando: {e}")
    
    finally:
        ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    connection, channel = connect_rabbitmq()
    channel.basic_qos(prefetch_count=10) # Traer varios mensajes para ser eficiente
    channel.basic_consume(queue=settings.QUEUE_NAME, on_message_callback=callback)
    
    print(' [*] Aggregator corriendo...')
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
        connection.close()

if __name__ == "__main__":
    main()
