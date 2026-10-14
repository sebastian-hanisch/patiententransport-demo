"""Das synthetische Haus: Orte, Wegzeiten je Transportart. Reine Daten und eine Funktion, kein Zustand."""

from dataclasses import dataclass

import numpy as np

import ptd_constants as C

# Name, Gebäude, Etage, x (m), y (m). Gebäude 0: Haupthaus, 1: Bettenhaus, 2: Ambulanztrakt.
PLACES = (
    ("Aufnahme", 0, 0, 0, 0), ("Radiologie", 0, -1, 30, 10), ("MRT", 0, -1, 60, 10),
    ("OP", 0, 2, 20, 40), ("Labor", 0, 1, 50, 30), ("Ausgang", 0, 0, 10, -20),
    ("Notaufnahme", 2, 0, -80, 10), ("Dialyse", 1, 1, 150, 0),
    ("Station 1", 1, 2, 130, -20), ("Station 2", 1, 3, 140, -10), ("Station 3", 1, 4, 150, 0),
    ("Station 4", 1, 5, 160, 10), ("Station 5", 1, 6, 170, 20), ("Station 6", 1, 7, 180, 30),
)
BUILDING_NAME = {0: "Haupthaus", 1: "Bettenhaus", 2: "Ambulanztrakt"}
EXAM_MINUTES = {"Radiologie": 25, "MRT": 45, "Labor": 15, "Dialyse": 180, "OP": 120}   # mittlere Untersuchungsdauer je Ziel


@dataclass(frozen=True)
class Hospital:
    names: tuple
    building: tuple
    floor: tuple
    x: tuple
    y: tuple
    T: dict            # Transportart (leer, bett, rollstuhl, gehend) -> ganzzahlige Wegzeitmatrix in Minuten
    depot: int         # Ort, an dem alle Träger den Tag beginnen
    stations: tuple
    diagnostics: tuple
    exam: dict         # Ort -> mittlere Untersuchungsdauer in Minuten

    def index(self, name: str) -> int:
        return self.names.index(name)


def travel_matrix(places, speed: float) -> np.ndarray:
    """Wegzeit in ganzen Minuten (aufgerundet, mindestens 1): Manhattan-Weg / Tempo, Aufzug bei Etagenwechsel, Gebäudewechsel-Zuschlag."""
    n = len(places)
    T = np.zeros((n, n), dtype=int)
    for i, a in enumerate(places):
        for j, b in enumerate(places):
            if i == j:
                continue
            t = (abs(a[3] - b[3]) + abs(a[4] - b[4])) / speed
            if a[2] != b[2]:
                t += C.LIFT_BASE + C.LIFT_PER_FLOOR * abs(a[2] - b[2])
            if a[1] != b[1]:
                t += C.BUILDING_CHANGE
            T[i, j] = max(1, int(np.ceil(t)))
    return T


def build_hospital() -> Hospital:
    names = tuple(p[0] for p in PLACES)
    index = {n: i for i, n in enumerate(names)}
    return Hospital(
        names=names,
        building=tuple(p[1] for p in PLACES), floor=tuple(p[2] for p in PLACES),
        x=tuple(p[3] for p in PLACES), y=tuple(p[4] for p in PLACES),
        T={kind: travel_matrix(PLACES, speed) for kind, speed in C.SPEED.items()},
        depot=index["Aufnahme"],
        stations=tuple(index[f"Station {k}"] for k in range(1, 7)),
        diagnostics=tuple(index[n] for n in ("Radiologie", "MRT", "Labor", "Dialyse", "OP")),
        exam={index[n]: m for n, m in EXAM_MINUTES.items()},
    )


HOSPITAL = build_hospital()
