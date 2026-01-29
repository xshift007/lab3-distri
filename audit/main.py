import json
import os
import sqlite3
import time
import uuid
from datetime import datetime

import pika

import settings


def connect_rabbitmq():
    while True:
        try:
            params = pika.ConnectionParameters(
                host=settings.RABBIT_HOST,
                port=settings.RABBIT_PORT,
                heartbeat=60,
                blocked_connection_timeout=120,
            )
            connection = pika.BlockingConnection(params)
            channel = connection.channel()

            # Aseguramos que los exchanges existan (por si Audit levanta antes que otros servicios)
            channel.exchange_declare(exchange=settings.TARGET_EXCHANGE, exchange_type="topic", durable=True)
            channel.exchange_declare(exchange=settings.METRICS_EXCHANGE, exchange_type="topic", durable=True)

            # Colas DURABLES (si Audit se cae, RabbitMQ conserva mensajes)
            channel.queue_declare(queue=settings.QUEUE_NAME, durable=True)
            channel.queue_declare(queue=settings.METRICS_QUEUE_NAME, durable=True)

            # Escuchar TODO lo que entra al exchange principal
            channel.queue_bind(exchange=settings.TARGET_EXCHANGE, queue=settings.QUEUE_NAME, routing_key="#")

            # Escuchar routing key de métricas
            channel.queue_bind(
                exchange=settings.METRICS_EXCHANGE,
                queue=settings.METRICS_QUEUE_NAME,
                routing_key=settings.METRICS_ROUTING_KEY,
            )

            print(f"[*] Audit Service conectado. Guardando en {settings.LOG_FILE_PATH}")
            return connection, channel

        except pika.exceptions.AMQPConnectionError:
            print("[!] Esperando a RabbitMQ...")
            time.sleep(5)


def append_to_log(event_body: bytes) -> None:
    """Escribe el evento en un archivo (JSON Lines). Best-effort."""
    try:
        data = json.loads(event_body)

        audit_entry = {
            "audit_timestamp": datetime.now().isoformat(),
            "event_content": data,
        }

        with open(settings.LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")

    except Exception as e:
        # No abortamos la auditoría DB por falla de archivo, pero lo reportamos.
        print(f"[!] Error escribiendo log en disco: {e}")


def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False, timeout=5)

    # Pragmas: concurrencia y consistencia
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=5000;")  # ms

    # Schema
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS events_in (
          event_id TEXT PRIMARY KEY,
          timestamp TEXT NOT NULL,
          region TEXT NOT NULL,
          source TEXT NOT NULL,
          schema_version TEXT,
          correlation_id TEXT,
          payload_json TEXT NOT NULL,
          run_id TEXT DEFAULT 'default',
          inserted_at TEXT DEFAULT (datetime('now'))
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS metrics_out (
          metric_id TEXT PRIMARY KEY,
          date TEXT NOT NULL,
          region TEXT NOT NULL,
          run_id TEXT DEFAULT 'default',
          metrics_json TEXT NOT NULL,
          created_at TEXT DEFAULT (datetime('now'))
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS trace (
          event_id TEXT NOT NULL,
          metric_id TEXT NOT NULL,
          contribution_type TEXT DEFAULT 'window_member',
          PRIMARY KEY (event_id, metric_id),
          FOREIGN KEY (event_id) REFERENCES events_in(event_id),
          FOREIGN KEY (metric_id) REFERENCES metrics_out(metric_id)
        );
        """
    )
    conn.commit()
    return conn


def get_run_id(properties, payload: dict) -> str:
    headers = getattr(properties, "headers", None) or {}
    return headers.get("run_id") or payload.get("run_id") or "default"


def store_event(conn: sqlite3.Connection, event: dict, run_id: str) -> None:
    """
    Solo ejecuta INSERT. El COMMIT lo hace el caller (transacción en handle_event).
    """
    if not event.get("event_id") or not event.get("timestamp") or not event.get("region") or not event.get("source"):
        raise ValueError("Evento inválido: faltan campos requeridos (event_id, timestamp, region, source)")

    conn.execute(
        """
        INSERT OR IGNORE INTO events_in
        (event_id, timestamp, region, source, schema_version, correlation_id, payload_json, run_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event.get("event_id"),
            event.get("timestamp"),
            event.get("region"),
            event.get("source"),
            event.get("schema_version"),
            event.get("correlation_id"),
            json.dumps(event.get("payload", {}), ensure_ascii=False),
            run_id,
        ),
    )


def store_metric_and_trace(conn: sqlite3.Connection, metric_msg: dict) -> None:
    """
    Inserta metrics_out + trace en UNA sola transacción (caller).
    Si falla un trace por FK, se revierte TODO (métrica incluida).
    """
    metric_id = metric_msg.get("metric_id") or str(uuid.uuid4())
    date = metric_msg["date"]
    region = metric_msg["region"]
    run_id = metric_msg.get("run_id", "default")
    metrics_json = json.dumps(metric_msg["metrics"], ensure_ascii=False)

    conn.execute(
        """
        INSERT OR REPLACE INTO metrics_out(metric_id, date, region, run_id, metrics_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (metric_id, date, region, run_id, metrics_json),
    )

    for event_id in metric_msg.get("input_event_ids", []):
        conn.execute(
            """
            INSERT OR IGNORE INTO trace(event_id, metric_id, contribution_type)
            VALUES (?, ?, 'window_member')
            """,
            (event_id, metric_id),
        )


def handle_event(conn: sqlite3.Connection, ch, method, properties, body: bytes):
    append_to_log(body)

    try:
        event = json.loads(body)
        run_id = get_run_id(properties, event)

        with conn:  # transacción atómica
            store_event(conn, event, run_id)

        print(f" [A] Auditado evento con RK: {method.routing_key}")
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except json.JSONDecodeError as e:
        print(f"[!] Evento no es JSON válido. Se descarta. Error: {e}")
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except (sqlite3.OperationalError, sqlite3.IntegrityError) as e:
        print(f"[!] Error DB guardando evento (requeue): {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    except Exception as e:
        print(f"[!] Error inesperado guardando evento (requeue): {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def handle_metric(conn: sqlite3.Connection, ch, method, properties, body: bytes):
    try:
        metric_msg = json.loads(body)

        with conn:  # métrica + trazas juntas o nada
            store_metric_and_trace(conn, metric_msg)

        print(f" [M] Métrica auditada con RK: {method.routing_key}")
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except json.JSONDecodeError as e:
        print(f"[!] Métrica no es JSON válido. Se descarta. Error: {e}")
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except (sqlite3.OperationalError, sqlite3.IntegrityError) as e:
        print(f"[!] Error DB guardando métrica/trace (requeue): {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    except Exception as e:
        print(f"[!] Error inesperado guardando métrica (requeue): {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def main():
    os.makedirs(os.path.dirname(settings.LOG_FILE_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(settings.AUDIT_DB_PATH), exist_ok=True)

    conn = init_db(settings.AUDIT_DB_PATH)

    connection, channel = connect_rabbitmq()

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(
        queue=settings.QUEUE_NAME,
        on_message_callback=lambda ch, method, properties, body: handle_event(conn, ch, method, properties, body),
    )
    channel.basic_consume(
        queue=settings.METRICS_QUEUE_NAME,
        on_message_callback=lambda ch, method, properties, body: handle_metric(conn, ch, method, properties, body),
    )

    print(" [*] Audit Service grabando eventos...")
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
        connection.close()


if __name__ == "__main__":
    main()
