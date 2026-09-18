# worker — image du service (boutique observabilite).
FROM python:3.12-slim

WORKDIR /app

# Dependances (couche mise en cache tant que requirements.txt ne change pas).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Module commun d'observabilite, puis code du service.
COPY common/observability.py .
COPY worker/app.py .

EXPOSE 8083

# Instrumentation OpenTelemetry AUTOMATIQUE des traces (sans toucher au code) :
# opentelemetry-instrument enveloppe le lancement de l'application.
CMD ["opentelemetry-instrument", "python", "app.py"]
