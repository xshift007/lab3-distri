FROM python:3.9-slim

WORKDIR /app

# Variable para ver logs de Python inmediatamente en Docker
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Comando por defecto (puedes sobrescribirlo en docker-compose si quieres pasar --seed)
CMD ["python", "main.py"]