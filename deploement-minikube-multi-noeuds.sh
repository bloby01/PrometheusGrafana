#!/bin/sh
minikube start --nodes 3 --cni flannel --cpus 2 --memory 6144
git clone https://github.com/bloby01/PrometheusGrafana
cd PrometheusGrafana
minikube kubectl -- apply -f manifests/01-namespaces.yaml
minikube kubectl -- apply -f manifests/20-boutique-frontend.yaml
minikube kubectl -- apply -f manifests/21-boutique-api.yaml
minikube kubectl -- apply -f manifests/22-boutique-worker.yaml
sleep 10
minikube kubectl -- get pods -n production


minikube kubectl -- apply -f manifests/10-local-path-provisioner.yaml
sleep 2
minikube kubectl -- get sc
sleep 1
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm install kube-prometheus-stack \
  prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --values manifests/06-helm-values.yaml
sleep 20
minikube kubectl -- get pods -n monitoring


minikube kubectl -- apply -f manifests/23-boutique-frontend-servicemonitor.yaml
minikube kubectl -- apply -f manifests/24-boutique-api-servicemonitor.yaml
minikube kubectl -- apply -f manifests/25-boutique-worker-servicemonitor.yaml
for i in $(seq 1 50); do
  curl -s -X POST http://localhost:8081/checkout \
    -H "Content-Type: application/json" \
    -d "{\"order_id\":\"cmd-$i\",\"cart\":[\"clavier\"]}" > /dev/null
done


minikube kubectl -- apply -f manifests/30-seaweedfs.yaml
minikube kubectl -- get pods -n monitoring -l app=seaweedfs
minikube kubectl -- logs -n monitoring job/seaweedfs-create-bucket
helm repo add grafana-community https://grafana-community.github.io/helm-charts
helm repo update
helm install loki grafana-community/loki -n monitoring -f manifests/31-loki-values.yaml
sleep 20
minikube kubectl -- get pods -n monitoring -l app.kubernetes.io/name=loki
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
helm install alloy grafana/alloy -n monitoring -f manifests/32-alloy-values.yaml
minikube kubectl -- get pods -n monitoring -l app.kubernetes.io/name=alloy



