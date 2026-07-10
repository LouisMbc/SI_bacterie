"""Pod state-manager : persistance Redis + jauge Prometheus bacteries_par_etat."""
import os
import logging
from concurrent import futures

import grpc
import redis
from prometheus_client import start_http_server, Gauge

import state_store_pb2
import state_store_pb2_grpc

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
GRPC_PORT = os.environ.get("GRPC_PORT", "9090")
METRICS_PORT = int(os.environ.get("METRICS_PORT", "8000"))

ETATS_CONNUS = ["stable", "hypertrophie", "atrophie", "impasse"]

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

JAUGE_PAR_ETAT = Gauge(
    "bacteries_par_etat",
    "Nombre de bactéries actuellement dans chaque état",
    ["etat"],
)


def _cle(bacterie_id):
    return f"bacterie:{bacterie_id}"


def _recalculer_jauge():
    compteurs = {e: 0 for e in ETATS_CONNUS}
    for cle in r.scan_iter("bacterie:*"):
        etat = r.hget(cle, "etat")
        if etat in compteurs:
            compteurs[etat] += 1
    for etat, n in compteurs.items():
        JAUGE_PAR_ETAT.labels(etat=etat).set(n)
    return compteurs


class StateStoreServicer(state_store_pb2_grpc.StateStoreServicer):
    def Lire(self, request, context):
        cle = _cle(request.bacterie_id)
        data = r.hgetall(cle)
        if not data:
            data = {"etat": "stable", "volume": "1.0", "last_transition_epoch": "0"}
            r.hset(cle, mapping=data)
            _recalculer_jauge()
        return state_store_pb2.Situation(
            bacterie_id=request.bacterie_id,
            etat=data["etat"],
            volume=float(data["volume"]),
            last_transition_epoch=int(data["last_transition_epoch"]),
        )

    def Ecrire(self, request, context):
        cle = _cle(request.bacterie_id)
        r.hset(cle, mapping={
            "etat": request.etat,
            "volume": str(request.volume),
            "last_transition_epoch": str(request.last_transition_epoch),
        })
        _recalculer_jauge()
        log.info("écriture %s -> etat=%s volume=%.4f", request.bacterie_id, request.etat, request.volume)
        return state_store_pb2.Situation(
            bacterie_id=request.bacterie_id,
            etat=request.etat,
            volume=request.volume,
            last_transition_epoch=request.last_transition_epoch,
        )

    def CompterParEtat(self, request, context):
        compteurs = _recalculer_jauge()
        return state_store_pb2.Comptes(par_etat=compteurs)


def serve():
    start_http_server(METRICS_PORT)
    log.info("Metrics Prometheus exposées sur :%s/metrics", METRICS_PORT)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    state_store_pb2_grpc.add_StateStoreServicer_to_server(StateStoreServicer(), server)
    server.add_insecure_port(f"[::]:{GRPC_PORT}")
    server.start()
    log.info("state-manager démarré, gRPC sur :%s, redis=%s:%s", GRPC_PORT, REDIS_HOST, REDIS_PORT)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()