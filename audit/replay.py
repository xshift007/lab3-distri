import json
import time
import os
import pika
import settings  # Usa la configuración local de audit

def replay_events():
    # 1. Ubicación del log (definida en tus settings de Audit)
    log_path = settings.LOG_FILE_PATH 
    
    if not os.path.exists(log_path):
        print(f"[!] No se encontró el archivo de log en: {log_path}")
        print("    (Asegúrate de que el sistema haya corrido y generado datos primero)")
        return

    print(f"[*] Conectando a RabbitMQ en host: {settings.RABBIT_HOST}...")
    
    try:
        # 2. Conexión a RabbitMQ
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=settings.RABBIT_HOST, port=settings.RABBIT_PORT)
        )
        channel = connection.channel()

        # IMPORTANTE: Enviamos al 'events_exchange' (el inicio del pipeline)
        # para probar que el Validator y Aggregator vuelvan a procesar todo.
        # Hardcodeamos el nombre porque en audit/settings.py no tienes esta variable.
        TARGET_REPLAY_EXCHANGE = "events_exchange" 
        
        # Aseguramos que el exchange exista (por si acaso)
        channel.exchange_declare(exchange=TARGET_REPLAY_EXCHANGE, exchange_type='topic', durable=True)

        print(f"[*] Iniciando Replay desde {log_path} hacia '{TARGET_REPLAY_EXCHANGE}'...")
        count = 0

        with open(log_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line: continue
                
                try:
                    # El log de audit suele guardar algo como: {"timestamp":..., "event": {...}}
                    # O directamente el evento. Intentamos detectar la estructura.
                    record = json.loads(line)
                    
                    # Si el log tiene el evento anidado bajo una llave "event" u "original_event"
                    if "event" in record and isinstance(record["event"], dict):
                        payload = record["event"]
                    elif "original_event" in record:
                        payload = record["original_event"]
                    else:
                        # Asumimos que la línea entera es el evento
                        payload = record

                    # Extraemos el routing_key original o usamos uno por defecto
                    # (Si tus eventos tienen campo 'source', úsalo)
                    routing_key = payload.get('source', 'replay.generic')

                    # 3. Publicar de nuevo
                    channel.basic_publish(
                        exchange=TARGET_REPLAY_EXCHANGE,
                        routing_key=routing_key,
                        body=json.dumps(payload),
                        properties=pika.BasicProperties(
                            delivery_mode=2, # Persistente
                            headers={'x-replay': 'true'} # Marca de agua para depuración
                        )
                    )
                    
                    count += 1
                    if count % 10 == 0:
                        print(f" -> Reinyectados {count} eventos...")
                    
                    # Pequeña pausa para no saturar (simula tiempo real acelerado)
                    time.sleep(0.05) 

                except json.JSONDecodeError:
                    print(f"[!] Línea corrupta ignorada.")
                except Exception as e:
                    print(f"[!] Error procesando línea: {e}")

        print(f"\n[OK] Replay finalizado exitosamente. Total reinyectados: {count}")
        connection.close()

    except Exception as e:
        print(f"[!] Error crítico de conexión o ejecución: {e}")

if __name__ == "__main__":
    replay_events()