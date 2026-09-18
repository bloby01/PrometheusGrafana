"""
api — validation de la commande et verification du stock.

Recoit la commande depuis 'frontend' (POST /orders), verifie un stock
simule, puis demande le paiement au service 'worker'. Maillon central de
la chaine : son span s'intercale entre celui du frontend et celui du worker.

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
SERVICE = "api"

# URL du service worker, injectee par l'environnement.
WORKER_URL = os.environ.get("WORKER_URL", "http://localhost:8083")

# Stock simule : quantite disponible par article.
STOCK = {"clavier": 50, "souris": 80, "ecran": 12, "casque": 0}

logger = make_logger(SERVICE)
REQUESTS, LATENCY = make_metrics()

app = Flask(__name__)


@app.route("/orders", methods=["POST"])
def orders():
    data = request.get_json(silent=True) or {}
    order_id = data.get("order_id", "inconnu")
    cart = data.get("cart", [])

    with LATENCY.labels(service=SERVICE).time():
        # Verification de stock : un article absent ou epuise rejette la commande.
        for item in cart:
            if STOCK.get(item, 0) <= 0:
                REQUESTS.labels(service=SERVICE, status="out_of_stock").inc()
                logger.error(
                    "Article indisponible",
                    extra={"order_id": order_id},
                )
                return jsonify({"status": "out_of_stock", "item": item}), 409

        amount = len(cart) * 25  # montant simule
        logger.info(
            "Commande validee, demande de paiement",
            extra={"order_id": order_id, "amount": amount},
        )
        try:
            response = requests.post(
                f"{WORKER_URL}/payment",
                json={"order_id": order_id, "amount": amount},
                timeout=10,
            )
        except requests.RequestException:
            REQUESTS.labels(service=SERVICE, status="failed").inc()
            logger.error("Service worker injoignable", extra={"order_id": order_id})
            return jsonify({"status": "error", "order_id": order_id}), 503

    if response.status_code == 200:
        REQUESTS.labels(service=SERVICE, status="success").inc()
        return jsonify({"status": "ok", "order_id": order_id}), 200

    REQUESTS.labels(service=SERVICE, status="payment_failed").inc()
    logger.error("Paiement echoue", extra={"order_id": order_id})
    return jsonify({"status": "payment_failed", "order_id": order_id}), 502


@app.route("/metrics")
def metrics():
    return metrics_response()


@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8082)
