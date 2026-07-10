"""Logique métier des 4 états de la bactérie."""

DELAI_SECONDES = 10


def etat_stable(volume: float, last_ts: int, now: int):
    # stable vivant, ouvert au changement : le volume ne bouge pas,
    # on peut partir vers hypertrophie ou atrophie.
    return volume, last_ts, ["hypertrophie", "atrophie"]


def etat_hypertrophie(volume: float, last_ts: int, now: int):
    # +10% toutes les 10 secondes. Depuis hypertrophie, seul retour
    # possible : stable.
    if now - last_ts >= DELAI_SECONDES:
        volume = volume * 1.10
        last_ts = now
    return volume, last_ts, ["stable"]


def etat_atrophie(volume: float, last_ts: int, now: int):
    # -5% toutes les 10 secondes. Retour vers stable toujours possible ;
    # vers impasse seulement si le volume est tombé à 0 ou moins.
    if now - last_ts >= DELAI_SECONDES:
        volume = volume * 0.95
        last_ts = now
    joignables = ["stable"]
    if volume <= 0:
        joignables.append("impasse")
    return volume, last_ts, joignables


def etat_impasse(volume: float, last_ts: int, now: int):
    # stable dans une impasse, sans aucune perspective d'évolution.
    return volume, last_ts, []


ETATS = {
    "stable": etat_stable,
    "hypertrophie": etat_hypertrophie,
    "atrophie": etat_atrophie,
    "impasse": etat_impasse,
}