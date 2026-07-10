"""
Test de charge Locust. Simule des utilisateurs qui lisent l'état
(GET /api/etat) et déclenchent des transitions (POST /api/transition),
exerçant toute la chaîne webapp -> pod d'état -> state-manager -> Redis.
"""
import random
from locust import HttpUser, task, between

TRANSITIONS_POSSIBLES = ["hypertrophie", "atrophie", "stable"]


class UtilisateurBacterie(HttpUser):
    wait_time = between(0.5, 2)

    @task(3)
    def consulter_etat(self):
        self.client.get("/api/etat", name="/api/etat")

    @task(1)
    def declencher_transition(self):
        cible = random.choice(TRANSITIONS_POSSIBLES)
        with self.client.post(
            "/api/transition", json={"etat_cible": cible},
            name="/api/transition", catch_response=True,
        ) as resp:
            # Un 409 (transition refusée par la machine à états) est un
            # comportement normal, pas un échec de perf.
            if resp.status_code in (200, 409):
                resp.success()
            else:
                resp.failure(f"status={resp.status_code}")