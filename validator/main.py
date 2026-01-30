import json
import time
import random
import pika
import jsonschema
from jsonschema import validate
import settings
import schemas
import os

# Configuración de Retries
MAX_RETRIES = 3
BASE_BACKOFF = 1.0 # Segundos

def connect_rabbitmq():
    """Conexión robusta con reintentos"""
    while True:
        try:
            params = pika.ConnectionParameters(host=settings.RABBIT_HOST, port=settings.RABBIT_PORT)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            
            # 1. Declarar Exchanges (Infraestructura)
            # Input (Topic)
            channel.exchange_declare(exchange=settings.INPUT_EXCHANGE, exchange_type='topic', durable=True)
            # Output (Topic) - Para que el Aggregator consuma
            channel.exchange_declare(exchange=settings.OUTPUT_EXCHANGE, exchange_type='topic', durable=True)
            # DLQ (Fanout o Direct) - Para errores
            channel.exchange_declare(exchange=settings.DLQ_EXCHANGE, exchange_type='direct', durable=True)

            # 2. Declarar Cola de Entrada del Validator
            channel.queue_declare(queue=settings.INPUT_QUEUE, durable=True)

            # 3. Bindings: Escuchar los tópicos definidos
            for topic in settings.LISTEN_TOPICS:
                channel.queue_bind(exchange=settings.INPUT_EXCHANGE, queue=settings.INPUT_QUEUE, routing_key=topic)

            print(f"[*] Validator conectado. Escuchando en {settings.INPUT_QUEUE}")
            return connection, channel
        except pika.exceptions.AMQPConnectionError:
            print(f"[!] Esperando a RabbitMQ en {settings.RABBIT_HOST}...")
            time.sleep(5)

def validate_event(event_data):
    """
    Retorna (True, None) si es válido.
    Retorna (False, error_msg) si es inválido.
    """
    try:
        # 1. Validar Estructura Base
        validate(instance=event_data, schema=schemas.BASE_SCHEMA)
        
        # 2. Validar que 'source' coincida con la lógica
        source = event_data.get("source")
        payload = event_data.get("payload")

        if source in schemas.PAYLOAD_SCHEMAS:
            validate(instance=payload, schema=schemas.PAYLOAD_SCHEMAS[source])
        else:
            return False, f"Tipo de evento desconocido: {source}"
            
        return True, None

    except jsonschema.exceptions.ValidationError as e:
        return False, f"Error de Schema: {e.message}"
    except Exception as e:
        return False, f"Error inesperado: {str(e)}"

def callback(ch, method, properties, body):
    """Procesa mensajes con política de Retry (Exponential Backoff)"""
    print(f" [>] Recibido: {method.routing_key}")
    
    retry_count = 0
    
    while retry_count <= MAX_RETRIES:
        try:
            if os.getenv('SIMULATE_ERRORS') == 'true':
                # Falla aleatoriamente (30% de veces) en los primeros intentos
                if random.random() < 0.3 and retry_count < 2:
                    print(f" [⚡] Simulación de Caos: Fallo de conexión inyectado.")
                    raise Exception("Fallo de red simulado (Chaos Testing)")

            try:
                event_data = json.loads(body)
            except json.JSONDecodeError:
                # Error permanente: No es JSON. A DLQ directo.
                print(" [!] Error Fatal: No es un JSON válido.")
                send_to_dlq(ch, method, body, "Invalid JSON", "validator")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            # Validación de Negocio
            is_valid, error_msg = validate_event(event_data)

            if is_valid:
                # Éxito: Enviar al exchange de procesamiento
                ch.basic_publish(
                    exchange=settings.OUTPUT_EXCHANGE,
                    routing_key=method.routing_key, 
                    body=body,
                    properties=pika.BasicProperties(delivery_mode=2)
                )
                print(f" [V] Válido. Reenviado a {settings.OUTPUT_EXCHANGE}")
            else:
                # Error de Negocio (Permanente): A DLQ directo.
                # No reintentamos porque el dato está malo siempre.
                send_to_dlq(ch, method, body, error_msg, "validator")
                print(f" [X] Inválido ({error_msg}). Enviado a DLQ.")

            # Si llegamos aquí sin excepción, todo salió bien. Confirmamos y salimos.
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        except Exception as e:
            # === MANEJO DE ERRORES TRANSITORIOS ===
            print(f" [!] Error transitorio (Intento {retry_count+1}/{MAX_RETRIES+1}): {e}")
            
            if retry_count < MAX_RETRIES:
                # Calculamos espera: 1s, 2s, 4s... (Exponential Backoff)
                sleep_time = BASE_BACKOFF * (2 ** retry_count)
                print(f"     ... Reintentando en {sleep_time} segundos.")
                time.sleep(sleep_time)
                retry_count += 1
                continue # Vuelve al inicio del while
            else:
                # Se acabaron los intentos. A DLQ.
                print(" [!!!] Agotados los reintentos. Moviendo a DLQ.")
                send_to_dlq(ch, method, body, f"Max retries exceeded: {str(e)}", "validator")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

def send_to_dlq(ch, method, body, error_msg, service_name):
    """Helper para enviar a DLQ"""
    # Intentamos parsear para envolver, si falla mandamos raw
    try:
        original_event = json.loads(body)
    except:
        original_event = body.decode('utf-8', errors='ignore')

    dlq_message = {
        "original_event": original_event,
        "error": error_msg,
        "failed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "service": service_name
    }
    
    ch.basic_publish(
        exchange=settings.DLQ_EXCHANGE,
        routing_key="deadletter.validation",
        body=json.dumps(dlq_message),
        properties=pika.BasicProperties(delivery_mode=2)
    )

def main():
    connection, channel = connect_rabbitmq()
    
    # QoS: Procesar 1 a la vez para balancear carga si escalamos
    channel.basic_qos(prefetch_count=1)
    
    channel.basic_consume(queue=settings.INPUT_QUEUE, on_message_callback=callback)
    
    print(' [*] Esperando eventos. Para salir presiona CTRL+C')
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
        connection.close()

if __name__ == "__main__":
    main()