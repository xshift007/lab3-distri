import json
import time
import pika
import settings
from datetime import datetime

def connect_rabbitmq():
    while True:
        try:
            params = pika.ConnectionParameters(host=settings.RABBIT_HOST, port=settings.RABBIT_PORT)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()

            # Aseguramos que el exchange exista (por si Audit levanta antes que Validator)
            channel.exchange_declare(exchange=settings.TARGET_EXCHANGE, exchange_type='topic', durable=True)

            # Declaramos una cola DURABLE y EXCLUSIVA para Audit
            # Así aseguramos que si Audit se cae, los mensajes se acumulan en RabbitMQ
            channel.queue_declare(queue=settings.QUEUE_NAME, durable=True)

            # Binding con '#' para escuchar TODO lo que entre al exchange
            channel.queue_bind(exchange=settings.TARGET_EXCHANGE, queue=settings.QUEUE_NAME, routing_key="#")

            print(f"[*] Audit Service conectado. Guardando en {settings.LOG_FILE_PATH}")
            return connection, channel
        except pika.exceptions.AMQPConnectionError:
            print(f"[!] Esperando a RabbitMQ...")
            time.sleep(5)

def append_to_log(event_body):
    """Escribe el evento en un archivo (JSON Lines format)"""
    try:
        # Decodificamos para asegurar que es texto, o si queremos agregar metadata extra
        data = json.loads(event_body)
        
        # Agregamos timestamp de auditoría (cuándo lo guardamos)
        audit_entry = {
            "audit_timestamp": datetime.now().isoformat(),
            "event_content": data
        }

        # Abrimos en modo 'append' (a). 
        # En producción, esto debería rotar logs o ir a Elasticsearch.
        with open(settings.LOG_FILE_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(audit_entry) + "\n")
            
    except Exception as e:
        print(f"[!] Error escribiendo en disco: {e}")

def callback(ch, method, properties, body):
    # 1. Escribir en persistencia
    append_to_log(body)
    
    # 2. Imprimir en consola (para ver que funciona en docker logs)
    print(f" [A] Auditado evento con RK: {method.routing_key}")
    
    # 3. Confirmar a RabbitMQ
    ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    # Asegurar que el directorio de logs exista
    import os
    os.makedirs(os.path.dirname(settings.LOG_FILE_PATH), exist_ok=True)

    connection, channel = connect_rabbitmq()
    
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=settings.QUEUE_NAME, on_message_callback=callback)
    
    print(' [*] Audit Service grabando eventos...')
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
        connection.close()

if __name__ == "__main__":
    main()