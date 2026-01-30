import json
import threading
import time
import pika
from flask import Flask, render_template, jsonify
import settings

app = Flask(__name__)

# --- ESTADO GLOBAL (Memoria compartida entre hilos) ---
current_state = {
    "status": "waiting",
    "last_update": None,
    "stats_by_region": {}
}

# --- RABBITMQ CONSUMER (Background Thread) ---
def start_consumer():
    """Función que corre en un hilo separado para escuchar RabbitMQ"""
    while True:
        try:
            params = pika.ConnectionParameters(host=settings.RABBIT_HOST, port=settings.RABBIT_PORT)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()

            # Asegurar exchange y cola
            channel.exchange_declare(exchange=settings.INPUT_EXCHANGE, exchange_type='topic', durable=True)
            # Cola exclusiva temporal (si se cae el dashboard, no importa perder visualización antigua)
            result = channel.queue_declare(queue='', exclusive=True) 
            queue_name = result.method.queue

            channel.queue_bind(exchange=settings.INPUT_EXCHANGE, queue=queue_name, routing_key="#")

            print("[*] Dashboard escuchando actualizaciones...")

            def callback(ch, method, properties, body):
                global current_state
                try:
                    data = json.loads(body)
                    # Actualizamos el estado global que lee Flask
                    current_state = data
                    print(" [D] Dashboard actualizado con nueva ventana.")
                except Exception as e:
                    print(f"Error parseando dashboard data: {e}")

            channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)
            channel.start_consuming()

        except pika.exceptions.AMQPConnectionError:
            print("[!] Conexión perdida. Reintentando en 5s...")
            time.sleep(5)

# --- FLASK WEB SERVER ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/data')
def get_data():
    return jsonify(current_state)

def main():
    # 1. Iniciar Consumer en un hilo aparte (Daemon muere cuando muere el main)
    consumer_thread = threading.Thread(target=start_consumer, daemon=True)
    consumer_thread.start()

    # 2. Iniciar Web Server (Bloqueante)
    print(f"[*] Web Server corriendo en puerto {settings.WEB_PORT}")
    app.run(host='0.0.0.0', port=settings.WEB_PORT, debug=False)

if __name__ == "__main__":
    main()