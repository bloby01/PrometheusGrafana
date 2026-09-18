"""
common — briques d'observabilité partagées par les trois services.

Ce module factorise tout ce qui concerne l'observabilité :
  - la configuration des logs structurés au format JSON (collectés par Alloy -> Loki) ;
  - la création des métriques Prometheus exposées sur /metrics ;
  - la réponse standard de l'endpoint /metrics.

Les métriques sont GÉNÉRIQUES : un nom commun (http_requests_total,
http_request_duration_seconds) et le service exprimé comme LABEL. Une seule
requete, groupee ou filtree par le label `service`, vaut ainsi pour tous les
services — et pour tout service ajoute plus tard. Le service est passe
explicitement a chaque appel dans les app.py.

Note : ce module NE renseigne PAS le trace_id dans les logs. La correlation
log -> trace par identifiant sera ajoutee plus tard, en exploitation, par un
enrichissement de ce fichier (voir le chapitre Correlation) — cas realiste
d'une application livree sans lien logs/traces, que l'on enrichit sans
reconstruire l'image.
"""

import json
import logging
import sys

from prometheus_client import (
    Counter,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)


def make_logger(service_name):
    """Construit un logger qui émet une ligne JSON par événement sur stdout."""

    class JsonFormatter(logging.Formatter):
        def format(self, record):
            entry = {
                "timestamp": self.formatTime(record),
                "level": record.levelname,
                "service": service_name,
                "message": record.getMessage(),
            }
            for field in ("order_id", "amount"):
                if hasattr(record, field):
                    entry[field] = getattr(record, field)
            return json.dumps(entry, ensure_ascii=False)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    logger = logging.getLogger(service_name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def make_metrics():
    """Crée les deux métriques GÉNÉRIQUES, partagées par tous les services.

    - http_requests_total : compteur de requetes, labels `service` et `status` ;
    - http_request_duration_seconds : histogramme de duree, label `service`.

    Le service est passe a l'usage, ex. :
        REQUESTS.labels(service="worker", status="failed").inc()
        with LATENCY.labels(service="worker").time(): ...
    """
    requests = Counter(
        "http_requests_total",
        "Nombre total de requetes traitees",
        ["service", "status"],
    )
    latency = Histogram(
        "http_request_duration_seconds",
        "Duree de traitement d'une requete en secondes",
        ["service"],
    )
    return requests, latency


def metrics_response():
    """Renvoie l'exposition Prometheus, prête à être servie par Flask."""
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}
