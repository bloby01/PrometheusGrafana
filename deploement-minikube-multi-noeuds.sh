#!/bin/sh
# =============================================================================
# base.sh — reconstruction complete de la maquette d'observabilite
# =============================================================================
# Cree un cluster Minikube 3 noeuds, deploie la boutique, la stack de metriques
# (Prometheus/Grafana), le stockage objet (SeaweedFS), les logs (Loki), les
# traces (Tempo) et le collecteur unifie (Alloy), puis genere du trafic.
#
# Usage : sh base.sh
# =============================================================================

set -e

echo "============================================================"
echo " 1. Creation du cluster Minikube (3 noeuds, CNI flannel)"
echo "============================================================"
minikube start --nodes 3 --cni flannel --cpus 2 --memory 6144

echo "============================================================"
echo " 2. Recuperation des fichiers du cours"
echo "============================================================"
if [ ! -d PrometheusGrafana ]; then
  git clone https://github.com/bloby01/PrometheusGrafana
fi
cd PrometheusGrafana

echo "============================================================"
echo " 3. Namespaces"
echo "============================================================"
minikube kubectl -- apply -f manifests/01-namespaces.yaml

echo "============================================================"
echo " 4. Stockage local (provisioner) — AVANT tout ce qui persiste"
echo "============================================================"
minikube kubectl -- apply -f manifests/10-local-path-provisioner.yaml
sleep 3
echo "--- StorageClasses ---"
minikube kubectl -- get sc

echo "============================================================"
echo " 5. Deploiement de la boutique"
echo "============================================================"
minikube kubectl -- apply -f manifests/20-boutique-frontend.yaml
minikube kubectl -- apply -f manifests/21-boutique-api.yaml
minikube kubectl -- apply -f manifests/22-boutique-worker.yaml
echo "--- Attente du demarrage des pods de la boutique ---"
minikube kubectl -- wait --for=condition=ready pod -l app=frontend -n production --timeout=120s
minikube kubectl -- wait --for=condition=ready pod -l app=api -n production --timeout=120s
minikube kubectl -- wait --for=condition=ready pod -l app=worker -n production --timeout=120s
echo "--- Pods production ---"
minikube kubectl -- get pods -n production

echo "============================================================"
echo " 6. Stack de metriques (kube-prometheus-stack)"
echo "============================================================"
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm install kube-prometheus-stack \
  prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --values manifests/06-helm-values.yaml
echo "--- Attente de Prometheus et Grafana ---"
minikube kubectl -- wait --for=condition=ready pod \
  -l app.kubernetes.io/name=grafana -n monitoring --timeout=180s || true
sleep 15
echo "--- Pods monitoring ---"
minikube kubectl -- get pods -n monitoring

echo "============================================================"
echo " 7. ServiceMonitor de la boutique (apres l'operateur)"
echo "============================================================"
minikube kubectl -- apply -f manifests/23-boutique-frontend-servicemonitor.yaml
minikube kubectl -- apply -f manifests/24-boutique-api-servicemonitor.yaml
minikube kubectl -- apply -f manifests/25-boutique-worker-servicemonitor.yaml

echo "============================================================"
echo " 8. Stockage objet (SeaweedFS) + bucket loki"
echo "============================================================"
minikube kubectl -- apply -f manifests/30-seaweedfs.yaml
echo "--- Attente de SeaweedFS ---"
minikube kubectl -- wait --for=condition=ready pod \
  -l app=seaweedfs -n monitoring --timeout=120s
sleep 5
echo "--- Job de creation du bucket loki ---"
minikube kubectl -- logs -n monitoring job/seaweedfs-create-bucket || true

echo "============================================================"
echo " 9. Logs (Loki, mode microservices)"
echo "============================================================"
helm repo add grafana-community https://grafana-community.github.io/helm-charts
helm repo update
helm install loki grafana-community/loki -n monitoring -f manifests/31-loki-values.yaml
sleep 20
echo "--- Pods Loki ---"
minikube kubectl -- get pods -n monitoring -l app.kubernetes.io/name=loki

echo "============================================================"
echo " 10. Traces — bucket tempo + Tempo (mode distribue)"
echo "============================================================"
minikube kubectl -- apply -f manifests/40-tempo-bucket.yaml
sleep 5
echo "--- Job de creation du bucket tempo ---"
minikube kubectl -- logs -n monitoring job/seaweedfs-create-bucket-tempo || true
helm install tempo grafana-community/tempo-distributed -n monitoring -f manifests/41-tempo-values.yaml
sleep 20
echo "--- Pods Tempo ---"
minikube kubectl -- get pods -n monitoring -l app.kubernetes.io/name=tempo

echo "============================================================"
echo " 11. Collecteur unifie (Alloy : logs + traces)"
echo "============================================================"
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
helm install alloy grafana/alloy -n monitoring -f manifests/32-alloy-values.yaml
sleep 10
echo "--- Pods Alloy (un par noeud) ---"
minikube kubectl -- get pods -n monitoring -l app.kubernetes.io/name=alloy

echo "============================================================"
echo " 12. Generation de trafic sur la boutique"
echo "============================================================"
# Port-forward temporaire vers le frontend, en tache de fond.
minikube kubectl -- port-forward -n production svc/frontend 8081:8081 &
PF_PID=$!
sleep 4
echo "--- Envoi de 50 commandes ---"
for i in $(seq 1 50); do
  curl -s -X POST http://localhost:8081/checkout \
    -H "Content-Type: application/json" \
    -d "{\"order_id\":\"cmd-$i\",\"cart\":[\"clavier\"]}" > /dev/null
done
echo "--- Trafic envoye ---"
# On arrete le port-forward temporaire.
kill $PF_PID 2>/dev/null || true

echo "============================================================"
echo " Maquette prete. Vue d'ensemble :"
echo "============================================================"
minikube kubectl -- get pods -n monitoring
echo ""
minikube kubectl -- get pods -n production
echo ""
echo "Acces Grafana :"
echo "  minikube kubectl -- port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80"
echo "  puis http://localhost:3000  (admin / admin)"
