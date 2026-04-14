FROM python:3.12-slim

WORKDIR /app

# System deps for numpy/scipy/psycopg
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create model cache dir
RUN mkdir -p /app/model_cache

EXPOSE 8000
