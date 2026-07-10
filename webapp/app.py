"""Page web de pilotage de la bactérie = client gRPC, sans règle métier."""
import os
import time
import logging

import grpc
from flask import Flask, render_template, jsonify, request

import bacterie_pb2
import bacterie_pb2_grpc

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)

BACTERIE_ID = "bacterie-1"

ADRESSES_ETATS = {
    "stable": os.environ.get("STABLE_ADDR", "localhost:50051"),
    "hypertrophie": os.environ.get("HYPERTROPHIE_ADDR", "localhost:50052"),
    "atrophie": os.environ.get("ATROPHIE_ADDR", "localhost:50053"),
    "impasse": os.environ.get("IMPASSE_ADDR", "localhost:50054"),
}

# Mémoire locale simple pour l'instant (une seule bactérie, un seul process).
_memoire = {"etat": "stable", "volume": 1.0, "last_ts": int(time.time())}


def _appeler_etat(nom_etat, volume, last_ts):
    adresse = ADRESSES_ETATS[nom_etat]
    with grpc.insecure_channel(adresse) as channel:
        stub = bacterie_pb2_grpc.EtatBacterieStub(channel)
        return stub.Entrer(
            bacterie_pb2.BacterieRequest(id=BACTERIE_ID, volume=volume, last_transition_epoch=last_ts),
            timeout=3,
        )


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/etat")
def api_etat():
    etat = _memoire["etat"]
    try:
        rep = _appeler_etat(etat, _memoire["volume"], _memoire["last_ts"])
    except grpc.RpcError as e:
        return jsonify(erreur=f"pod '{etat}' injoignable: {e.details()}"), 503

    _memoire["volume"] = rep.volume
    _memoire["last_ts"] = rep.last_transition_epoch
    return jsonify(etat=etat, volume=round(rep.volume, 5), etats_joignables=list(rep.etats_joignables))


@app.route("/api/transition", methods=["POST"])
def api_transition():
    cible = request.json.get("etat_cible")
    if cible not in ADRESSES_ETATS:
        return jsonify(erreur="état cible inconnu"), 400

    rep_courant = _appeler_etat(_memoire["etat"], _memoire["volume"], _memoire["last_ts"])
    if cible not in rep_courant.etats_joignables:
        return jsonify(erreur=f"transition '{_memoire['etat']}' -> '{cible}' interdite"), 409

    rep_cible = _appeler_etat(cible, rep_courant.volume, rep_courant.last_transition_epoch)
    _memoire["etat"] = cible
    _memoire["volume"] = rep_cible.volume
    _memoire["last_ts"] = rep_cible.last_transition_epoch

    return jsonify(etat=cible, volume=round(rep_cible.volume, 5), etats_joignables=list(rep_cible.etats_joignables))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))