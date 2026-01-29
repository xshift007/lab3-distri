# lab3-Sistemas_distribuidos


## Resumen del código existente

Este proyecto implementa un **pipeline de eventos** basado en microservicios que se comunican mediante **RabbitMQ**.  El sistema simula la generación y procesamiento de eventos de seguridad, encuestas de victimización y casos de migración.  Cada servicio se despliega en un contenedor Docker y está orquestado por `docker‑compose`.  A continuación se resume la funcionalidad de cada servicio y los archivos clave.

### Generador de eventos (`publisher`)

* **Responsabilidad**: genera de manera continua eventos sintéticos para tres tópicos de entrada (`security.incident`, `survey.victimization` y `migration.case`).  Cada evento incluye campos comunes (`event_id`, `timestamp`, `region`, `source`, `schema_version`, `correlation_id`) y un `payload` específico de cada tipo.  El generador puede operar en modo normal o en modo **burst**: con una probabilidad se genera una ráfaga de eventos de incidentes de seguridad.
* **Estructura**: en `publisher/main.py` se definen funciones para crear cada tipo de evento y un bucle principal que calcula el retardo según la tasa configurada (`EVENT_RATE`) y publica eventos de manera persistente en el exchange `events_exchange`.  Las variables de configuración (tasa, regiones, modo burst) se definen en `publisher/settings.py`.

### Validador de eventos (`validator`)

* **Responsabilidad**: consume eventos de los tópicos de entrada, valida su estructura y contenidos usando **jsonschema**, y decide si son válidos.  Los eventos válidos se reenvían al exchange `processing_exchange`; los inválidos se encapsulan con un mensaje de error y se envían a la cola de “dead letter” (`deadletter.validation`).
* **Validaciones**: la función `validate_event` comprueba el esquema base (UUID, timestamp ISO 8601, región permitida) y el esquema del `payload` según el `source.  Los esquemas están definidos en `validator/schemas.py`.  El validador utiliza QoS para procesar un mensaje a la vez y confirma (`ack`) los mensajes solo después de publicarlos, implementando semántica *al menos una vez*.
* **Configuración**: los tópicos de entrada y salida y la dead‑letter se especifican en `validator/settings.py`.

### Agregador (`aggregator`)

* **Responsabilidad**: agrega eventos validados en ventanas temporales (por defecto 5 s) y publica dos tipos de mensajes:
  - **Resumen de ventana** (routing key `analytics.window`): contiene el recuento de eventos procesados por tipo y región junto con la lista de `event_id` que contribuyeron.  Estos resúmenes permiten que otros componentes (dashboard, audit) conozcan la composición de cada ventana.
  - **Métricas diarias** (routing key `metrics.daily`): para cada región publica un registro agregando todos los eventos de la ventana a nivel diario, con un `metric_id` único y los `input_event_ids` para trazabilidad【615348102083414†L48-L86】.
* **Deduplicación**: mantiene un conjunto `processed_ids` con los `event_id` ya procesados; si un evento se repite, se descarta.  Esto asegura idempotencia aunque el generador emita duplicados.
* **Reinicio de ventana**: la función `flush_window` publica los resúmenes y métricas, luego reinicia el estado para la siguiente ventana.  La duración de la ventana y los exchanges se configuran en `aggregator/settings.py`【14862071178537†L7-L14】.

### Servicio de auditoría (`audit`)

* **Responsabilidad**: registra todos los eventos válidos y las métricas publicadas para posibilitar **trazabilidad**.  Recibe mensajes de los exchanges de procesamiento (`processing_exchange`) y de métricas (`analytics_exchange`), los persiste en un archivo JSONL y en una base de datos SQLite.
* **Base de datos**: al iniciar, el servicio crea tablas relacionales `events_in`, `metrics_out` y `trace`.  `events_in` almacena eventos de entrada, `metrics_out` almacena las métricas diarias, y `trace` vincula qué eventos (`event_id`) aportaron a cada métrica (`metric_id`).  Estas tablas permiten consultar posteriormente qué eventos generaron una métrica dada.
* **Persistencia atómica**: las funciones `store_event` y `store_metric_and_trace` ejecutan inserciones dentro de una transacción (`with conn:`) y solo se confirma el mensaje a RabbitMQ (`ack`) después de que la base de datos se actualiza con éxito.  En caso de error se hace `nack` con requeue para reintentar y así cumplir semántica al menos una vez.
* **Configuración**: los nombres de intercambio, colas y rutas de dead‑letter, así como la ruta de la base de datos (`AUDIT_DB_PATH`), se configuran en `audit/settings.py`.

### Dashboard / API de métricas (`dashboard`)

* **Responsabilidad**: ofrece una interfaz web y una API para visualizar las métricas agregadas.  Consume resúmenes de ventana (`analytics.window`) y actualiza un estado global en memoria con los recuentos más recientes.  Se expone un endpoint `GET /data` que devuelve un JSON con las métricas actuales y una página HTML que actualiza periódicamente para mostrar los recuentos por región y tipo..
* **Configuración**: este servicio se conecta a RabbitMQ utilizando el exchange `analytics_exchange` y escucha la cola `dashboard_queue`; el puerto del servidor web se define en `dashboard/settings.py`.

### Configuración y despliegue

* **`docker-compose.yml`**: orquesta los seis contenedores (`rabbitmq`, `publisher`, `validator`, `aggregator`, `audit`, `dashboard`) con las variables de entorno adecuadas para cada servicio【124126403228911†L43-L74】.  RabbitMQ incluye el *management plugin* para acceder a su UI en el puerto 15672.  La base de datos y los logs del audit se montan en un volumen persistente.
* **Variables de entorno**: cada servicio lee sus parámetros (host/puerto de RabbitMQ, nombres de exchanges, colas y rutas) desde su módulo `settings.py` para facilitar la configuración en despliegues distintos【14862071178537†L7-L14】【867155149108393†L7-L14】.
* **Ejemplo de ejecución**: con Docker y docker‑compose instalados, se puede levantar todo el sistema ejecutando:

  ```sh
  # clonar repositorio y levantar servicios
  git clone <REPO_URL>
  cd lab3-distri
  docker compose up --build
  ```

  Esto descargará/compilará las imágenes y levantará los servicios.  La interfaz web del dashboard estará disponible en `http://localhost:5000` y se actualizará en tiempo real.

## Cómo funciona el flujo de eventos

1. **Generación y publicación**.  El servicio `publisher` genera eventos de manera continua y los publica en el exchange `events_exchange`.  Puede activarse el modo burst para simular picos de tráfico.
2. **Validación**.  `validator` consume de `events_exchange`, valida el esquema y re‑emite eventos válidos al exchange `processing_exchange` y los inválidos al dead‑letter `deadletter.validation`.
3. **Agregación y deduplicación**.  `aggregator` escucha `processing_exchange`, elimina duplicados por `event_id`, acumula recuentos por ventana y región, y publica resúmenes (`analytics.window`) y métricas diarias (`metrics.daily`).
4. **Auditoría y trazabilidad**.  `audit` registra cada evento válido y métrica en SQLite; además relaciona qué eventos generaron cada métrica en la tabla `trace`.  Esto permite reconstruir a posteriori qué eventos se consideraron para una métrica.
5. **Visualización**.  `dashboard` consume resúmenes de ventana para actualizar su estado y expone una API REST (`/data`) y una página web que muestra los recuentos agregados en tiempo real.

## Uso y personalización

* **Tasas de generación**: la variable `EVENT_RATE` en `publisher/settings.py` controla el intervalo medio entre eventos (en segundos).  Para reproducir un patrón exacto se puede pasar un `seed` al generador.  El modo burst (`ENABLE_BURST`) añade ráfagas aleatorias de eventos.
* **Duración de la ventana**: `AGGREGATION_WINDOW` en `aggregator/settings.py` define la duración de cada ventana temporal.  Ajustar este valor modifica la granularidad de los resúmenes publicados.
* **Esquemas de eventos**: los campos obligatorios y las estructuras de los `payload` se encuentran en `validator/schemas.py`.  Para añadir nuevos tipos de eventos bastaría con definir un esquema nuevo y actualizar la validación.
* **Persistencia y pruebas**: la base de datos SQLite se almacena en `data/audit.db` (ver `AUDIT_DB_PATH`).  Puede inspeccionarse con cualquier cliente SQLite para verificar la trazabilidad o realizar replays de eventos.
* **Extensiones posibles**: implementar un modo de duplicados controlados y orden fuera de secuencia en el generador, añadir detección de anomalías que publique alertas en `alerts.anomaly`, o agregar endpoints de métricas Prometheus para observar throughput y latencia.

## Conclusión

El código presenta una solución completa y extensible para procesar flujos de eventos con **garantías de al menos una vez**, deduplicación y trazabilidad end‑to‑end.  Utiliza RabbitMQ como bus de eventos, SQLite para persistencia ligera y Flask para la visualización en tiempo real.  La estructura modular facilita su despliegue mediante Docker y permite personalizar tasas de generación, ventanas de agregación y esquemas de validación conforme a las necesidades de cada caso.


# Ejecutar los siguientes comandos para borrar contenedros viejos en caso de problemas
docker compose down -v
docker compose up --build

# Si se busca cambiar solo un contenedor
docker compose build NOMBRE_CONTENEDOR
docker compose up -d

# Detener contenedor
docker compose stop NOMBRE_CONTENEDOR

# Para ver replay, primero se debe detener publisher
docker compose exec audit python replay.py

# Para lo que son los scripts, si se esta utilizando linux se debe utilizar el siguiente comando primero
chmod +x run_load.sh run_burst.sh run_chaos.sh run_demo.sh replay.sh