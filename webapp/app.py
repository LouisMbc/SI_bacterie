"""Page web de pilotage de la bactérie = client gRPC, sans règle métier."""
import os
import time
import uuid
import logging

import grpc
from flask import Flask, render_template, jsonify, request, session

import bacterie_pb2
import bacterie_pb2_grpc
import state_store_pb2
import state_store_pb2_grpc

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "cle-secrete-dev-tp")

ADRESSES_ETATS = {
    "stable": os.environ.get("STABLE_ADDR", "localhost:50051"),
    "hypertrophie": os.environ.get("HYPERTROPHIE_ADDR", "localhost:50052"),
    "atrophie": os.environ.get("ATROPHIE_ADDR", "localhost:50053"),
    "impasse": os.environ.get("IMPASSE_ADDR", "localhost:50054"),
}

STATE_MANAGER_ADDR = os.environ.get("STATE_MANAGER_ADDR")

_memoire_locale = {}  # utilisé seulement si STATE_MANAGER_ADDR absent


def _bacterie_id_courant():
    """Chaque visiteur a son propre id de bactérie, stocké dans son cookie
    de session. C'est ce qui permet à plusieurs bactéries d'exister en
    parallèle dans le cluster."""
    if "bacterie_id" not in session:
        session["bacterie_id"] = str(uuid.uuid4())[:8]
    return session["bacterie_id"]


def _appeler_etat(nom_etat, volume, last_ts):
    adresse = ADRESSES_ETATS[nom_etat]
    with grpc.insecure_channel(adresse) as channel:
        stub = bacterie_pb2_grpc.EtatBacterieStub(channel)
        return stub.Entrer(
            bacterie_pb2.BacterieRequest(id=_bacterie_id_courant(), volume=volume, last_transition_epoch=last_ts),
            timeout=3,
        )


def _lire_situation(bacterie_id):
    if STATE_MANAGER_ADDR:
        with grpc.insecure_channel(STATE_MANAGER_ADDR) as channel:
            stub = state_store_pb2_grpc.StateStoreStub(channel)
            rep = stub.Lire(state_store_pb2.LireRequest(bacterie_id=bacterie_id), timeout=3)
            return rep.etat, rep.volume, rep.last_transition_epoch
    d = _memoire_locale.setdefault(bacterie_id, {"etat": "stable", "volume": 1.0, "last_ts": int(time.time())})
    return d["etat"], d["volume"], d["last_ts"]


def _ecrire_situation(bacterie_id, etat, volume, last_ts):
    if STATE_MANAGER_ADDR:
        with grpc.insecure_channel(STATE_MANAGER_ADDR) as channel:
            stub = state_store_pb2_grpc.StateStoreStub(channel)
            stub.Ecrire(state_store_pb2.EcrireRequest(
                bacterie_id=bacterie_id, etat=etat, volume=volume, last_transition_epoch=last_ts
            ), timeout=3)
    else:
        _memoire_locale[bacterie_id] = {"etat": etat, "volume": volume, "last_ts": last_ts}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/etat")
def api_etat():
    bid = _bacterie_id_courant()
    etat, volume, last_ts = _lire_situation(bid)
    try:
        rep = _appeler_etat(etat, volume, last_ts)
    except grpc.RpcError as e:
        return jsonify(erreur=f"pod '{etat}' injoignable: {e.details()}"), 503

    _ecrire_situation(bid, etat, rep.volume, rep.last_transition_epoch)
    return jsonify(
        bacterie_id=bid,
        etat=etat,
        volume=round(rep.volume, 5),
        etats_joignables=list(rep.etats_joignables),
    )


@app.route("/api/transition", methods=["POST"])
def api_transition():
    bid = _bacterie_id_courant()
    cible = request.json.get("etat_cible")
    etat, volume, last_ts = _lire_situation(bid)

    if cible not in ADRESSES_ETATS:
        return jsonify(erreur="état cible inconnu"), 400

    rep_courant = _appeler_etat(etat, volume, last_ts)
    if cible not in rep_courant.etats_joignables:
        return jsonify(erreur=f"transition '{etat}' -> '{cible}' interdite"), 409

    rep_cible = _appeler_etat(cible, rep_courant.volume, rep_courant.last_transition_epoch)
    _ecrire_situation(bid, cible, rep_cible.volume, rep_cible.last_transition_epoch)

    return jsonify(
        bacterie_id=bid,
        etat=cible,
        volume=round(rep_cible.volume, 5),
        etats_joignables=list(rep_cible.etats_joignables),
    )


@app.route("/api/toutes")
def api_toutes():
    """Liste TOUTES les bactéries du cluster (pas juste celle du visiteur
    courant) — démontre le multi-bactéries demandé par l'énoncé."""
    if not STATE_MANAGER_ADDR:
        return jsonify(erreur="state-manager non configuré"), 501
    with grpc.insecure_channel(STATE_MANAGER_ADDR) as channel:
        stub = state_store_pb2_grpc.StateStoreStub(channel)
        rep = stub.Lister(state_store_pb2.Vide(), timeout=3)
    return jsonify(bacteries=[
        {"id": s.bacterie_id, "etat": s.etat, "volume": round(s.volume, 5)}
        for s in rep.situations
    ])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))