"""
common — briques d'observabilité partagées par les trois services.

Ce module factorise tout ce qui concerne l'observabilité :
  - la configuration des logs structurés au format JSON (collectés par Alloy -> Loki) ;
  - la création des métriques Prometheus exposées sur /metrics ;
  - la réponse standard de l'endpoint /metrics.

VERSION CHAPITRE OPENTELEMETRY : le JsonFormatter injecte désormais le
trace_id (et le span_id) du contexte de trace courant dans chaque ligne de
log. C'est ce qui relie un log à sa trace : Loki peut alors, via un
derivedField, transformer ce trace_id en lien cliquable vers Tempo, et le
bouton de corrélation de Tempo peut isoler LES logs d'UNE requête précise
(filterByTraceID) au lieu de tous les logs du service sur une fenêtre de temps.
"""

import json
import logging
import sys

from opentelemetry import trace

from prometheus_client import (
    Counter,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)


def make_logger(service_name):
    """Construit un logger qui émet une ligne JSON par événement sur stdout.

    Chaque ligne contient au minimum l'horodatage, le niveau, le nom du
    service et le message. Les champs métier (order_id, amount) sont ajoutés
    quand ils sont fournis via extra={...} lors de l'appel au logger. Le
    trace_id du span courant est ajouté automatiquement s'il existe.
    """

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

            # Injection du contexte de trace OpenTelemetry.
            # get_current_span() renvoie le span actif dans le contexte courant
            # (celui que l'instrumentation automatique a ouvert pour la requête).
            # Si aucun span n'est actif (hors requête), le contexte est invalide
            # et l'on n'ajoute rien — le log reste valide, simplement sans trace_id.
            span = trace.get_current_span()
            ctx = span.get_span_context()
            if ctx.is_valid:
                # Tempo attend le trace_id sur 32 caracteres hexa, le span_id sur 16.
                entry["trace_id"] = format(ctx.trace_id, "032x")
                entry["span_id"] = format(ctx.span_id, "016x")

            return json.dumps(entry, ensure_ascii=False)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    logger = logging.getLogger(service_name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()      # évite les doublons si le module est rechargé
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def make_metrics(service_name):
    """Crée les deux métriques standard d'un service.

    - un compteur du nombre de requêtes, ventilé par statut (success / failed) ;
    - un histogramme de la durée de traitement, qui alimentera les quantiles
      de latence côté Prometheus.
    """
    requests = Counter(
        f"{service_name}_requests_total",
        "Nombre total de requetes traitees",
        ["status"],
    )
    latency = Histogram(
        f"{service_name}_request_duration_seconds",
        "Duree de traitement d'une requete en secondes",
    )
    return requests, latency


def metrics_response():
    """Renvoie l'exposition Prometheus, prête à être servie par Flask."""
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}
