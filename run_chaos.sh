#!/bin/bash
echo "--- INICIANDO PRUEBA DE CAOS (CHAOS TESTING) ---"

# 1. Levantar el sistema en segundo plano (detached)
docker compose up -d --build

echo "[*] Sistema arrancado. Esperando 10 segundos para estabilizar..."
sleep 10

# 2. Matar al Validator (Simular caída del consumidor)
echo ""
echo "[☠️] MATANDO SERVICIO VALIDATOR..."
docker compose stop validator
echo "[*] Validator detenido. El Publisher sigue enviando."
echo "[*] Mira RabbitMQ: La cola 'events_queue' debería estar acumulando mensajes (Backpressure)."
sleep 10

# 3. Revivir al Validator
echo ""
echo "[🚑] REVIVIENDO VALIDATOR..."
docker compose start validator
echo "[*] Validator reiniciado. Debería procesar todo lo acumulado rápidamente."
sleep 10

# 4. Reiniciar el Broker (Simular caída de RabbitMQ)
echo ""
echo "[☠️] REINICIANDO RABBITMQ BROKER..."
docker compose restart rabbitmq
echo "[*] Broker reiniciando. Los servicios deberían reconectarse automáticamente."

# 5. Mostrar logs finales
echo ""
echo "[*] Prueba finalizada. Mostrando logs para verificar reconexión (Ctrl+C para salir)..."
docker compose logs -f