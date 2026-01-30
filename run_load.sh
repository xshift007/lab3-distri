#!/bin/bash
echo "--- Iniciando Carga Normal (1 evento/seg) ---"

# Forzamos las variables de entorno para una carga suave
export EVENT_RATE=1.0
export ENABLE_BURST=false

# Levantamos todo reconstruyendo por si hubo cambios
docker compose up --build