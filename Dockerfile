FROM python:3.11-slim

LABEL maintainer="TCM System Team"
LABEL version="2.0.0"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/shared/ ./shared/
COPY backend/pattern_miner/ ./pattern_miner/
COPY backend/drug_discoverer/ ./drug_discoverer/
COPY backend/graph_api/ ./graph_api/
COPY backend/formula_loader/ ./formula_loader/
COPY backend/gateway.py ./gateway.py
COPY backend/algorithm_config.json ./algorithm_config.json
COPY backend/data/ ./data/

COPY deploy/gunicorn_conf.py ./gunicorn_conf.py

RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

CMD ["gunicorn", "-c", "gunicorn_conf.py", "gateway:app"]
