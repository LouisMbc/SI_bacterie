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

STATE_MANAGER_ADDR = os.environ.get("STATE_MANAGER_ADDR")

_memoire_locale = {"etat": "stable", "volume": 1.0, "last_ts": int(time.time())}


def _appeler_etat(nom_etat, volume, last_ts):
    adresse = ADRESSES_ETATS[nom_etat]
    with grpc.insecure_channel(adresse) as channel:
        stub = bacterie_pb2_grpc.EtatBacterieStub(channel)
        return stub.Entrer(
            bacterie_pb2.BacterieRequest(id=BACTERIE_ID, volume=volume, last_transition_epoch=last_ts),
            timeout=3,
        )


def _lire_situation():
    if STATE_MANAGER_ADDR:
        import state_client
        return state_client.lire(STATE_MANAGER_ADDR, BACTERIE_ID)
    return _memoire_locale["etat"], _memoire_locale["volume"], _memoire_locale["last_ts"]


def _ecrire_situation(etat, volume, last_ts):
    if STATE_MANAGER_ADDR:
        import state_client
        state_client.ecrire(STATE_MANAGER_ADDR, BACTERIE_ID, etat, volume, last_ts)
    else:
        _memoire_locale.update(etat=etat, volume=volume, last_ts=last_ts)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/etat")
def api_etat():
    etat, volume, last_ts = _lire_situation()
    try:
        rep = _appeler_etat(etat, volume, last_ts)
    except grpc.RpcError as e:
        return jsonify(erreur=f"pod '{etat}' injoignable: {e.details()}"), 503

    _ecrire_situation(etat, rep.volume, rep.last_transition_epoch)
    return jsonify(etat=etat, volume=round(rep.volume, 5), etats_joignables=list(rep.etats_joignables))


@app.route("/api/transition", methods=["POST"])
def api_transition():
    cible = request.json.get("etat_cible")
    etat, volume, last_ts = _lire_situation()

    if cible not in ADRESSES_ETATS:
        return jsonify(erreur="état cible inconnu"), 400

    rep_courant = _appeler_etat(etat, volume, last_ts)
    if cible not in rep_courant.etats_joignables:
        return jsonify(erreur=f"transition '{etat}' -> '{cible}' interdite"), 409

    rep_cible = _appeler_etat(cible, rep_courant.volume, rep_courant.last_transition_epoch)
    _ecrire_situation(cible, rep_cible.volume, rep_cible.last_transition_epoch)

    return jsonify(etat=cible, volume=round(rep_cible.volume, 5), etats_joignables=list(rep_cible.etats_joignables))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))