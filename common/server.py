"""Serveur gRPC générique d'un pod état, paramétré par la variable ETAT."""
import os
import time
import logging
from concurrent import futures

import grpc
from prometheus_client import start_http_server, Counter

import bacterie_pb2
import bacterie_pb2_grpc
from logique_etats import ETATS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

ETAT_NOM = os.environ.get("ETAT", "stable")
GRPC_PORT = os.environ.get("GRPC_PORT", "50051")
METRICS_PORT = int(os.environ.get("METRICS_PORT", "8000"))

if ETAT_NOM not in ETATS:
    raise SystemExit(f"ETAT invalide: {ETAT_NOM}, doit être un de {list(ETATS)}")

FONCTION_ETAT = ETATS[ETAT_NOM]

COMPTEUR_TRAVERSEE = Counter(
    "etat_traversee_total",
    "Nombre de fois où cet état a été traversé par une bactérie",
    ["etat"],
)


class EtatBacterieServicer(bacterie_pb2_grpc.EtatBacterieServicer):
    def Entrer(self, request, context):
        now = int(time.time())
        volume, last_ts, joignables = FONCTION_ETAT(request.volume, request.last_transition_epoch, now)
        COMPTEUR_TRAVERSEE.labels(etat=ETAT_NOM).inc()
        log.info("id=%s etat=%s volume_in=%.4f volume_out=%.4f joignables=%s",
                  request.id, ETAT_NOM, request.volume, volume, joignables)
        return bacterie_pb2.BacterieResponse(
            volume=volume,
            etats_joignables=joignables,
            last_transition_epoch=last_ts,
            etat=ETAT_NOM,
        )


def serve():
    start_http_server(METRICS_PORT)
    log.info("Metrics Prometheus exposées sur :%s/metrics", METRICS_PORT)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    bacterie_pb2_grpc.add_EtatBacterieServicer_to_server(EtatBacterieServicer(), server)
    server.add_insecure_port(f"[::]:{GRPC_PORT}")
    server.start()
    log.info("Pod état '%s' démarré, gRPC sur :%s", ETAT_NOM, GRPC_PORT)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()