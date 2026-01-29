#!/bin/bash
echo "--- EJECUTANDO REPLAY DE EVENTOS ---"

# Verificamos si el contenedor audit está corriendo
if [ -z "$(docker compose ps -q audit)" ]; then
    echo "[!] Error: El sistema debe estar corriendo (usa run_load.sh primero)."
    exit 1
fi

# Ejecutamos el script interno
docker compose exec audit python replay.py