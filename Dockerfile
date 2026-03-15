# Real-Time Anomaly Detection — production image for Fly.io
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Fly.io sets PORT=8080 via fly.toml [env]; default for local docker run
ENV PORT=8000
EXPOSE 8000 8080

CMD ["python", "run.py"]
