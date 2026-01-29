FROM python:3.9-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Flask usa el puerto 5000 por defecto
EXPOSE 5000

CMD ["python", "main.py"]