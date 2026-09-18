"""
worker — traitement du paiement.

Recoit une demande de paiement depuis 'api' (POST /payment) et simule un
echange avec une banque : la plupart des paiements sont rapides, mais une
partie est volontairement lente, et un sur dix echoue. C'est ce service qui
fournit la matiere a diagnostiquer (trace lente, log d'erreur, latence qui
grimpe) au fil du cours.

Signaux d'observabilite exposes :
  - metriques Prometheus sur /metrics (http_requests_total, http_request_duration_seconds,
    labellisees par le service)
  - logs structures JSON sur stdout
  - traces : ajoutees par instrumentation automatique (voir le Dockerfile)
"""

import random
import time

from flask import Flask, request, jsonify

from observability import make_logger, make_metrics, metrics_response

# Nom du service, defini une seule fois et reutilise pour le logger et le
# label `service` des metriques.
SERVICE = "worker"

# Probabilites de simulation, regroupees en tete pour etre faciles a ajuster
# en demonstration.
PROBA_LENT = 0.2        # part des paiements volontairement lents
PROBA_ECHEC = 0.1       # part des paiements refuses

logger = make_logger(SERVICE)
REQUESTS, LATENCY = make_metrics()

app = Flask(__name__)


@app.route("/payment", methods=["POST"])
def payment():
    data = request.get_json(silent=True) or {}
    order_id = data.get("order_id", "inconnu")
    amount = data.get("amount", 0)

    with LATENCY.labels(service=SERVICE).time():
        # Latence variable : banque rapide la plupart du temps, lente parfois.
        if random.random() < PROBA_LENT:
            time.sleep(random.uniform(1.0, 3.0))
        else:
            time.sleep(random.uniform(0.05, 0.3))

        # Echec occasionnel : la banque refuse le paiement.
        if random.random() < PROBA_ECHEC:
            REQUESTS.labels(service=SERVICE, status="failed").inc()
            logger.error(
                "Paiement refuse par la banque",
                extra={"order_id": order_id, "amount": amount},
            )
            return jsonify({"status": "failed", "order_id": order_id}), 502

    REQUESTS.labels(service=SERVICE, status="success").inc()
    logger.info(
        "Paiement accepte",
        extra={"order_id": order_id, "amount": amount},
    )
    return jsonify({"status": "success", "order_id": order_id}), 200


@app.route("/metrics")
def metrics():
    return metrics_response()


@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8083)
