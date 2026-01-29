#!/bin/bash
echo "--- [!!!] INICIANDO MODO BURST/RÁFAGA [!!!] ---"
echo "--- Tasa: 50 eventos/seg + Picos aleatorios ---"

# Sobrescribimos las variables para generar caos de tráfico
export EVENT_RATE=50.0
export ENABLE_BURST=true

# Levantamos
docker compose up --build