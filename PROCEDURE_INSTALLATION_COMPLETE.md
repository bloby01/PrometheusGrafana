# 🚀 Procédure d'installation complète - Monitoring Kubernetes avec Control Plane
# Formation Kubernetes - Grafana & Prometheus
# CMC SASU - itformation.fr

## 📋 Prérequis

- Cluster Kubernetes on-premises (3 masters, 3 workers)
- Accès SSH aux masters
- Helm 3.x installé
- kubectl configuré
- MetalLB configuré (pour les services LoadBalancer)
- Accès sudo sur les masters

## 🎯 Vue d'ensemble

Cette procédure permet de monitorer **100% du cluster** :
- ✅ Nodes (CPU, RAM, disque, réseau)
- ✅ Pods et conteneurs
- ✅ API Server
- ✅ etcd (avec certificats mTLS)
- ✅ kube-controller-manager
- ✅ kube-scheduler
- ✅ kube-proxy
- ✅ CoreDNS

**Temps d'installation : ~15 minutes**

---

## 📁 Fichiers nécessaires

Assurez-vous d'avoir ces fichiers dans `manifests/` :

```
manifests/
├── 06-helm-values.yaml                    # Configuration Helm complète
├── 11-etcd-servicemonitor-custom.yaml     # ServiceMonitor etcd avec mTLS
└── 01-installEtTestPrometheusGrafana.sh   # Script interactif
```

---

## 🔐 ÉTAPE 1 : Récupérer les certificats etcd

### Sur un des masters (via SSH)

```bash
# Se connecter au master1
ssh master1-k8s.mon.dom

# Récupérer les certificats etcd
sudo cat /etc/kubernetes/pki/etcd/ca.crt > /tmp/etcd-ca.crt
sudo cat /etc/kubernetes/pki/etcd/healthcheck-client.crt > /tmp/etcd-client.crt
sudo cat /etc/kubernetes/pki/etcd/healthcheck-client.key > /tmp/etcd-client.key

# Donner les droits de lecture
sudo chmod 644 /tmp/etcd-*.crt /tmp/etcd-*.key

# Se déconnecter
exit
```

### Sur votre machine locale

```bash
# Copier les certificats depuis le master
scp master1-k8s.mon.dom:/tmp/etcd-ca.crt .
scp master1-k8s.mon.dom:/tmp/etcd-client.crt .
scp master1-k8s.mon.dom:/tmp/etcd-client.key .

# Vérifier que les fichiers sont présents
ls -lh etcd-*.crt etcd-*.key
```

**Résultat attendu :**
```
-rw-r--r-- 1 user user 1.1K etcd-ca.crt
-rw-r--r-- 1 user user 1.2K etcd-client.crt
-rw------- 1 user user 1.7K etcd-client.key
```

---

## 🎬 ÉTAPE 2 : Créer le namespace et le secret

```bash
# Créer le namespace monitoring
kubectl create namespace monitoring

# Créer le secret avec les certificats etcd
kubectl create secret generic etcd-certs \
  --from-file=ca.crt=etcd-ca.crt \
  --from-file=client.crt=etcd-client.crt \
  --from-file=client.key=etcd-client.key \
  -n monitoring

# Vérifier que le secret est créé
kubectl get secret etcd-certs -n monitoring
```

**Résultat attendu :**
```
NAME         TYPE     DATA   AGE
etcd-certs   Opaque   3      5s
```

---

## 🚀 ÉTAPE 3 : Installer kube-prometheus-stack

### Option A : Via le script interactif (RECOMMANDÉ)

```bash
# Lancer le script
sh manifests/01-installEtTestPrometheusGrafana.sh

# Choisir l'option 1 : Installer kube-prometheus-stack
1

# Attendre la fin de l'installation (~2-3 minutes)
```

### Option B : Via Helm directement

```bash
# Ajouter le repository Helm
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Installer
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --values manifests/06-helm-values.yaml \
  --wait \
  --timeout 10m
```

**Sortie attendue :**
```
NAME: kube-prometheus-stack
NAMESPACE: monitoring
STATUS: deployed
```

---

## 📊 ÉTAPE 4 : Configurer le monitoring etcd

### Supprimer le ServiceMonitor par défaut (ne fonctionne pas)

```bash
# Le chart crée automatiquement un ServiceMonitor etcd qui ne fonctionne pas
# On doit le supprimer et utiliser le nôtre
kubectl delete svc -n kube-system kube-prometheus-stack-kube-etcd --ignore-not-found
kubectl delete servicemonitor -n monitoring kube-prometheus-stack-kube-etcd --ignore-not-found
```

### Appliquer notre ServiceMonitor custom avec mTLS

```bash
# Créer le Service et ServiceMonitor etcd avec certificats
kubectl apply -f manifests/11-etcd-servicemonitor-custom.yaml
```

**Résultat attendu :**
```
service/etcd-metrics created
servicemonitor.monitoring.coreos.com/etcd-custom created
```

### Attendre le rechargement de Prometheus

```bash
# Attendre 30 secondes que Prometheus recharge sa config
sleep 30
```

---

## ✅ ÉTAPE 5 : Vérification complète

### Via le script interactif

```bash
# Lancer le script
sh manifests/01-installEtTestPrometheusGrafana.sh

# Choisir l'option 2 : Vérifier l'installation
2
```

**Résultat attendu :**
```
[INFO] Pods dans le namespace monitoring :
NAME                                          READY   STATUS    RESTARTS   AGE
alertmanager-...                              2/2     Running   0          2m
grafana-...                                   3/3     Running   0          2m
prometheus-...                                2/2     Running   0          2m
...

[INFO] Installation vérifiée avec succès !
```

### Vérification manuelle

```bash
# Vérifier que tous les pods sont Running
kubectl get pods -n monitoring

# Vérifier les services LoadBalancer
kubectl get svc -n monitoring | grep LoadBalancer
```

**Résultat attendu :**
```
kube-prometheus-stack-grafana      LoadBalancer   172.21.0.X   80:XXXXX/TCP
kube-prometheus-stack-prometheus   LoadBalancer   172.21.0.Y   9090:XXXXX/TCP
```

---

## 🔍 ÉTAPE 6 : Vérifier Prometheus Targets

### Récupérer l'IP de Prometheus

```bash
PROMETHEUS_IP=$(kubectl get svc -n monitoring kube-prometheus-stack-prometheus \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

echo "Prometheus accessible sur : http://$PROMETHEUS_IP:9090"
```

### Ouvrir Prometheus UI

```
Navigateur : http://<PROMETHEUS_IP>:9090
Aller dans : Status > Targets
```

### Vérifier que TOUS les composants sont UP

**Targets attendus (tous UP ✅) :**

```
✅ serviceMonitor/.../alertmanager/0          → 1/1 up
✅ serviceMonitor/.../apiserver/0             → 3/3 up
✅ serviceMonitor/.../coredns/0               → 2/2 up
✅ serviceMonitor/.../grafana/0               → 1/1 up
✅ serviceMonitor/.../kube-state-metrics/0    → 1/1 up
✅ serviceMonitor/.../kubelet/0 (nodes)       → 6/6 up
✅ serviceMonitor/.../kubelet/1 (cadvisor)    → 6/6 up
✅ serviceMonitor/.../kubelet/2 (probes)      → 6/6 up
✅ serviceMonitor/.../kubelet/3 (resource)    → 6/6 up
✅ serviceMonitor/.../node-exporter/0         → 6/6 up
✅ serviceMonitor/.../prometheus/0            → 1/1 up

✅ monitoring/etcd-custom/0                   → 3/3 up  ← etcd avec mTLS

✅ kube-controller-manager-localhost          → 3/3 up
✅ kube-scheduler-localhost                   → 3/3 up
✅ kube-proxy-localhost                       → 6/6 up
```

**Total : ~60 targets UP sur ~60 !** 🎉

---

## 📊 ÉTAPE 7 : Tester les métriques etcd

### Dans Prometheus Graph

```
Navigateur : http://<PROMETHEUS_IP>:9090
Aller dans : Graph
```

### Requêtes de test

```promql
# Test 1 : etcd a un leader
etcd_server_has_leader
# Résultat attendu : 1 pour chaque instance (3 résultats)

# Test 2 : Latence fsync etcd (doit être < 10ms en général)
histogram_quantile(0.99, rate(etcd_disk_wal_fsync_duration_seconds_bucket[5m]))
# Résultat attendu : Valeur en secondes (ex: 0.005 = 5ms)

# Test 3 : Taille de la base etcd
etcd_mvcc_db_total_size_in_bytes / 1024 / 1024
# Résultat attendu : Taille en Mo (devrait être < 2000 Mo)

# Test 4 : Controller Manager
workqueue_depth{job="kube-controller-manager"}
# Résultat attendu : Valeurs numériques

# Test 5 : Scheduler
scheduler_pending_pods{job="kube-scheduler"}
# Résultat attendu : Nombre de pods en attente
```

**Si toutes ces requêtes retournent des données → Monitoring 100% fonctionnel !** ✅

---

## 🎨 ÉTAPE 8 : Accéder à Grafana

### Récupérer l'IP et le mot de passe

```bash
# IP de Grafana
GRAFANA_IP=$(kubectl get svc -n monitoring kube-prometheus-stack-grafana \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

# Mot de passe admin
GRAFANA_PASSWORD=$(kubectl get secret -n monitoring kube-prometheus-stack-grafana \
  -o jsonpath="{.data.admin-password}" | base64 --decode)

echo "Grafana : http://$GRAFANA_IP"
echo "Login   : admin"
echo "Password: $GRAFANA_PASSWORD"
```

### Se connecter à Grafana

```
Navigateur : http://<GRAFANA_IP>
Login      : admin
Password   : <mot de passe affiché ci-dessus>
```

### Vérifier les dashboards

**Dashboards pré-installés :**
1. Alertmanager / Overview
2. CoreDNS
3. etcd
4. Grafana Overview
5. Kubernetes / API server
6. Kubernetes / Compute Resources / Cluster
7. Kubernetes / Compute Resources / Namespace (Pods)
8. Kubernetes / Compute Resources / Namespace (Workloads)
9. Kubernetes / Compute Resources / Node (Pods)
10. Kubernetes / Compute Resources / Pod
11. Kubernetes / Compute Resources / Workload
12. Kubernetes / Controller Manager
13. Kubernetes / Kubelet
14. Kubernetes / Networking / Cluster
15. Kubernetes / Networking / Namespace (Pods)
16. Kubernetes / Networking / Namespace (Workload)
17. Kubernetes / Networking / Pod
18. Kubernetes / Networking / Workload
19. Kubernetes / Proxy
20. Kubernetes / Scheduler
21. Node Exporter / Nodes
22. Prometheus

**Ouvrir par exemple :** "Kubernetes / Compute Resources / Cluster"
- Devrait afficher CPU, RAM, réseau de tout le cluster
- Toutes les métriques doivent être présentes

---

## 🧪 ÉTAPE 9 : Tests avec l'application demo (OPTIONNEL)

### Via le script interactif

```bash
sh manifests/01-installEtTestPrometheusGrafana.sh

# Option 6 : Déployer l'application demo
6

# Option 7 : Tester l'endpoint /metrics
7

# Option 8 : Créer le ServiceMonitor
8

# Option 9 : Vérifier le scraping
9
```

### Tester les alertes (OPTIONNEL)

```bash
# Option 10 : Créer les PrometheusRule
10

# Option 12 : Simuler des erreurs (6 minutes)
12

# Attendre 6 minutes...

# Option 13 : Vérifier l'état des alertes
13
```

---

## 🧹 Nettoyage (si nécessaire)

### Nettoyage complet via le script

```bash
sh manifests/01-installEtTestPrometheusGrafana.sh

# Option 99 : Nettoyage complet
99

# Confirmer : y
```

### Nettoyage manuel

```bash
# Désinstaller le chart
helm uninstall kube-prometheus-stack -n monitoring

# Supprimer le ServiceMonitor custom
kubectl delete -f manifests/11-etcd-servicemonitor-custom.yaml

# Nettoyer les PVC
kubectl get pvc -n monitoring -o name | \
  xargs -I {} kubectl patch {} -n monitoring -p '{"metadata":{"finalizers":null}}' --type=merge
kubectl delete pvc --all -n monitoring

# Supprimer le secret etcd
kubectl delete secret etcd-certs -n monitoring

# Supprimer le namespace
kubectl delete namespace monitoring

# Nettoyer les certificats locaux
rm -f etcd-*.crt etcd-*.key
```

---

## ✅ Checklist finale

- [ ] Certificats etcd récupérés depuis un master
- [ ] Secret `etcd-certs` créé dans namespace `monitoring`
- [ ] kube-prometheus-stack installé via Helm
- [ ] ServiceMonitor etcd custom appliqué
- [ ] Tous les pods Running dans namespace `monitoring`
- [ ] Services Grafana et Prometheus en LoadBalancer avec IPs
- [ ] Prometheus Targets : ~60/60 UP
- [ ] Métriques etcd accessibles (etcd_server_has_leader = 1)
- [ ] Métriques controller-manager accessibles
- [ ] Métriques scheduler accessibles
- [ ] Métriques kube-proxy accessibles
- [ ] Grafana accessible avec dashboards fonctionnels
- [ ] Toutes les requêtes PromQL de test retournent des données

**Si tous les points sont cochés → Installation réussie à 100% ! 🎉**

---

## 📚 Pour vos stagiaires

### Points clés à expliquer

1. **Architecture du monitoring**
   - Prometheus Operator : Gère les instances Prometheus
   - ServiceMonitor : Découverte automatique des targets
   - PrometheusRule : Définition des alertes

2. **Monitoring du control plane**
   - etcd : Base de données distribuée, nécessite mTLS
   - controller-manager / scheduler : Écoutent sur localhost
   - Solution : additionalScrapeConfigs pour scraper via le node

3. **Sécurité**
   - Certificats mTLS pour etcd (authentification mutuelle)
   - insecureSkipVerify pour certificats auto-signés (dev/test)
   - En production : utiliser un CA interne reconnu

4. **Troubleshooting**
   - Vérifier les logs : `kubectl logs -n monitoring <pod>`
   - Vérifier les targets : Prometheus UI > Status > Targets
   - Vérifier les ServiceMonitor : `kubectl get servicemonitor -n monitoring`

---

## 🐛 Troubleshooting

### Problème : etcd DOWN - "certificate required"

**Solution :** Vérifier que le secret existe et est bien référencé
```bash
kubectl get secret etcd-certs -n monitoring
kubectl get servicemonitor etcd-custom -n monitoring -o yaml | grep -A 10 tlsConfig
```

### Problème : controller-manager / scheduler DOWN

**Cause :** Composants écoutent sur 127.0.0.1

**Vérification :**
```bash
kubectl exec -n kube-system <pod-name> -- netstat -tlnp | grep 10257
```

**Solution :** Le fichier values.yaml utilise `additionalScrapeConfigs` pour contourner ce problème.

### Problème : Grafana "No data"

**Cause :** Datasource mal configurée

**Solution :**
1. Configuration > Data sources > Prometheus
2. Vérifier URL : `http://kube-prometheus-stack-prometheus.monitoring.svc:9090`
3. Save & test
4. Forcer refresh des dashboards

### Problème : Service LoadBalancer en "Pending"

**Cause :** MetalLB non configuré ou pool d'IPs épuisé

**Solution :**
```bash
# Vérifier MetalLB
kubectl get pods -n metallb-system

# Vérifier la config IP pool
kubectl get ipaddresspool -n metallb-system
```

---

## 📝 Notes importantes

### Certificats etcd

Les certificats etcd sont **générés automatiquement** par kubeadm lors de l'installation du cluster. On les **réutilise**, on ne crée pas de nouveau CSR.

Localisation : `/etc/kubernetes/pki/etcd/`

### Persistence des données

- Prometheus : 15 jours de rétention, 20Gi de stockage (NFS)
- Alertmanager : 120h de rétention, 10Gi de stockage
- Grafana : 10Gi de stockage pour dashboards et config

### Ressources allouées

- Prometheus : 500m CPU, 2Gi RAM (limite 2 CPU, 4Gi RAM)
- Grafana : 250m CPU, 512Mi RAM (limite 500m CPU, 1Gi RAM)
- Alertmanager : 100m CPU, 128Mi RAM

---

## 🎓 Exercices pour les stagiaires

1. **Créer une alerte personnalisée**
   - Alerte si la latence etcd > 50ms pendant 5 minutes

2. **Créer un dashboard personnalisé**
   - Dashboard montrant uniquement les métriques du control plane

3. **Déployer une application avec métriques**
   - Utiliser l'application demo fournie
   - Créer un ServiceMonitor
   - Visualiser les métriques dans Grafana

4. **Simuler une panne**
   - Arrêter un pod etcd
   - Observer les alertes
   - Vérifier le failover

---

**Formation Kubernetes - Monitoring complet**
**CMC SASU - itformation.fr**
**Version : 1.0 - Février 2026**
