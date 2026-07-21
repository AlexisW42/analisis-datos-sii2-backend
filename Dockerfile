# Imagen base ligera
FROM python:3.12-slim

# Evita que Python genere .pyc y fuerza output sin buffer (útil para logs)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencias del sistema necesarias para psycopg2 (si usas la versión no binaria)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiamos primero requirements para aprovechar la cache de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el resto del código
COPY . .

# Render inyecta la variable PORT dinámicamente, no la fijes tú mismo
EXPOSE 8000

# Usamos $PORT en tiempo de ejecución
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port $PORT"]