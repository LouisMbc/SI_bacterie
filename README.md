# TP - Systèmes d'Information avancés ou critiques - Bactérie

## 1. Vue d'ensemble

La bactérie est modélisée comme une **machine à états** à 4 états, chaque
état étant un **pod Kubernetes autonome** exposant un service **gRPC**
unique : `EtatBacterie.Entrer(BacterieRequest) -> BacterieResponse`
(contrat défini dans `proto/bacterie.proto`).

Chaque pod d'état :
- reçoit `(id, volume, last_transition_epoch)` ;
- applique **sa propre règle** (voir `common/logique_etats.py`) ;
- renvoie le nouveau volume + la liste des états joignables depuis lui ;
- incrémente un compteur Prometheus `etat_traversee_total{etat=...}` à
  chaque appel (nombre de fois où il a été traversé).

Les 4 pods partagent **la même image Docker** (`services/Dockerfile`) : le
code métier est factorisé dans `common/logique_etats.py`, seule la
variable d'environnement `ETAT` change entre les 4 Deployments
(`k8s/10-etats.yaml`). Cela évite de dupliquer 4 fois un serveur gRPC
quasi identique, tout en gardant 4 pods réellement indépendants
(redémarrables/scalables séparément), ce qui respecte la contrainte
"chaque état = au moins un pod autonome".

## 2. Pourquoi gRPC ?

- Contrat fortement typé via Protobuf : impossible d'appeler `Entrer` avec
  un mauvais type de champ, contrairement à un JSON REST libre.
- HTTP/2 + binaire, adapté à des appels fréquents (toutes les 2s depuis la
  webapp).
- `etats_joignables` (repeated string) fait du pod d'état la **seule
  source de vérité** sur les transitions autorisées : la webapp relaie et
  revérifie, elle ne réimplémente pas la règle métier.

## 3. La page web (webapp/)

Client gRPC Flask, sans aucune règle métier :
- `GET /api/etat` : rappelle le pod de l'état courant (applique la
  croissance/décroissance si 10s se sont écoulées) et renvoie
  état + volume + boutons activables.
- `POST /api/transition {etat_cible}` : transition manuelle. La webapp
  revérifie côté serveur que `etat_cible` fait partie de
  `etats_joignables` avant d'appeler le pod cible.
- Le front (`templates/index.html`) poll `/api/etat` toutes les 2s.

## 4. Evolution : plusieurs bactéries + persistance en cas de pause

**Problème** : si la webapp garde l'état en RAM, un redémarrage/pause du
pod (ou un scaling à plusieurs replicas) perd l'état de toutes les
bactéries.

**Solution retenue** : un 5e service, `state-manager/`, dédié à la
persistance. Il expose un service gRPC (`proto/state_store.proto`) et
stocke chaque bactérie dans **Redis** sous la clé `bacterie:<id>`.

Avec ce changement, la webapp devient **stateless** (donc réplicable), et
l'`id` de bactérie permet de gérer N bactéries en parallèle. Testé en
pratique : suppression du pod webapp en cours d'exécution → état conservé
après recréation automatique du pod par Kubernetes.

## 5. Tableau de bord

`state-manager` recalcule à chaque écriture une jauge Prometheus
`bacteries_par_etat{etat=...}` en scannant Redis. Prometheus scrape cette
jauge et Grafana (provisionné automatiquement, `k8s/42-grafana.yaml`)
affiche un bargauge "nombre de bactéries par état" et un graphe des
traversées cumulées.

## 6. Test de performance

**Outil choisi : Locust** (`perf/locustfile.py`). Simule des utilisateurs
alternant lecture d'état (poids 3) et transition (poids 1), exerçant toute
la chaîne webapp -> pod d'état -> state-manager -> Redis. Les réponses
`409` (transition refusée par la machine à états) ne comptent pas comme
un échec.

Résultat obtenu (20 utilisateurs, 30s) : 448 requêtes, 0% d'échec,
latence médiane ~45ms, p99 ~100ms.

```bash
locust -f perf/locustfile.py --host=http://localhost:5000 \
    --headless -u 20 -r 5 -t 30s --csv=perf/resultats
```

## 7. Construire et déployer

```bash
python -m grpc_tools.protoc -I proto --python_out=common --grpc_python_out=common \
    proto/bacterie.proto proto/state_store.proto

docker build -f services/Dockerfile       -t bacterie-etat:latest .
docker build -f webapp/Dockerfile         -t bacterie-webapp:latest .
docker build -f state-manager/Dockerfile  -t bacterie-state-manager:latest .

kind load docker-image bacterie-etat:latest --name bacterie
kind load docker-image bacterie-webapp:latest --name bacterie
kind load docker-image bacterie-state-manager:latest --name bacterie

kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/10-etats.yaml
kubectl apply -f k8s/20-redis.yaml
kubectl apply -f k8s/21-state-manager.yaml
kubectl apply -f k8s/30-webapp.yaml
kubectl apply -f k8s/40-prometheus-config.yaml
kubectl apply -f k8s/41-prometheus.yaml
kubectl apply -f k8s/42-grafana.yaml

kubectl -n bacterie get pods
```
Accès (via `kubectl -n bacterie port-forward svc/<nom> <port>:<port>`) :
webapp `:5000` · prometheus `:9090` · grafana `:3000`.

## 8. Structure du dépôt

```bash
proto/            .proto (contrats gRPC)
common/           logique métier + stubs générés + serveur générique des 4 états
services/         Dockerfile générique des pods d'état
state-manager/    persistance Redis + jauge Prometheus (Evolution)
webapp/           page web = client gRPC (Flask)
k8s/              manifests Kubernetes
perf/             test de charge Locust
```