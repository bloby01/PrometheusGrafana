"""
frontend — point d'entree de la boutique.

Recoit la commande du client (POST /checkout avec un panier), puis
transmet la commande au service 'api'. C'est le premier maillon de la
chaine : c'est ici que naitra la trace qui suivra la commande jusqu'au
paiement.

Signaux d'observabilite exposes :
  - metriques Prometheus sur /metrics (labellisees par le service)
  - logs structures JSON sur stdout
  - traces : ajoutees par instrumentation automatique (voir le Dockerfile)
"""

import os

import requests
from flask import Flask, request, jsonify

from observability import make_logger, make_metrics, metrics_response

# Nom du service, defini une seule fois.
SERVICE = "frontend"

# URL du service api, injectee par l'environnement (valeur par defaut locale).
API_URL = os.environ.get("API_URL", "http://localhost:8082")

logger = make_logger(SERVICE)
REQUESTS, LATENCY = make_metrics()

app = Flask(__name__)


@app.route("/checkout", methods=["POST"])
def checkout():
    data = request.get_json(silent=True) or {}
    cart = data.get("cart", [])
    order_id = data.get("order_id", "inconnu")

    with LATENCY.labels(service=SERVICE).time():
        logger.info(
            "Commande recue du client",
            extra={"order_id": order_id},
        )
        try:
            # L'appel HTTP propage automatiquement le contexte de trace
            # (en-tete traceparent) une fois l'instrumentation activee.
            response = requests.post(
                f"{API_URL}/orders",
                json={"order_id": order_id, "cart": cart},
                timeout=10,
            )
        except requests.RequestException:
            REQUESTS.labels(service=SERVICE, status="failed").inc()
            logger.error("Service api injoignable", extra={"order_id": order_id})
            return jsonify({"status": "error", "order_id": order_id}), 503

    if response.status_code == 200:
        REQUESTS.labels(service=SERVICE, status="success").inc()
        return jsonify({"status": "confirmed", "order_id": order_id}), 200

    REQUESTS.labels(service=SERVICE, status="failed").inc()
    logger.error("Commande refusee en aval", extra={"order_id": order_id})
    return jsonify({"status": "rejected", "order_id": order_id}), 502


@app.route("/metrics")
def metrics():
    return metrics_response()


@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081)
