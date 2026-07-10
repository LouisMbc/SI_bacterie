"""Client gRPC vers le pod state-manager."""
import grpc
import state_store_pb2
import state_store_pb2_grpc


def lire(adresse, bacterie_id):
    with grpc.insecure_channel(adresse) as channel:
        stub = state_store_pb2_grpc.StateStoreStub(channel)
        rep = stub.Lire(state_store_pb2.LireRequest(bacterie_id=bacterie_id), timeout=3)
        return rep.etat, rep.volume, rep.last_transition_epoch


def ecrire(adresse, bacterie_id, etat, volume, last_ts):
    with grpc.insecure_channel(adresse) as channel:
        stub = state_store_pb2_grpc.StateStoreStub(channel)
        stub.Ecrire(
            state_store_pb2.EcrireRequest(
                bacterie_id=bacterie_id, etat=etat, volume=volume, last_transition_epoch=last_ts
            ),
            timeout=3,
        )