#!/bin/bash

# Función para imprimir bonito
print_header() {
    echo ""
    echo "========================================================"
    echo "   $1"
    echo "========================================================"
    echo ""
}

print_header "INICIANDO DEMO COMPLETA DEL SISTEMA PUB/SUB"
echo "1. Levantando infraestructura base (Docker Compose)..."
docker compose down -v
# Iniciamos con carga baja
export EVENT_RATE=1.0
export ENABLE_BURST=false
docker compose up -d --build

echo "[OK] Sistema levantado. Esperando 10s para estabilización..."
sleep 10

print_header "FASE 1: CARGA NORMAL (Observabilidad)"
echo "El sistema está procesando 1 evento/seg."
echo "Puedes verificar el Dashboard en http://localhost:5000"
echo "Esperando 15 segundos..."
sleep 15

print_header "FASE 2: BURST MODE (Backpressure)"
echo "Simulando pico de tráfico (50 eventos/seg)..."
# Inyectamos variables en caliente reiniciando solo el publisher
export EVENT_RATE=50.0
export ENABLE_BURST=true
docker compose up -d publisher
echo "Observa cómo suben las colas en RabbitMQ (http://localhost:15672)"
sleep 15

print_header "FASE 3: CHAOS TESTING (Tolerancia a Fallas)"
echo "Simulando caída del servicio VALIDATOR..."
docker compose stop validator
echo "El Publisher sigue enviando, los mensajes se acumulan en RabbitMQ..."
sleep 10
echo "Reviviendo VALIDATOR..."
docker compose start validator
echo "El sistema debería recuperar el retraso (Lag) rápidamente."
sleep 10

print_header "FASE 4: VERIFICACIÓN DE AUDITORÍA"
echo "Verificando logs guardados..."
if [ -f "data/audit_log.jsonl" ]; then
    lines=$(wc -l < data/audit_log.jsonl)
    echo "[OK] Archivo de auditoría encontrado con $lines eventos procesados."
else
    echo "[ERROR] No se encontró el archivo de auditoría."
fi

print_header "DEMO FINALIZADA"
echo "El sistema sigue corriendo. Para detenerlo usa: docker compose down"