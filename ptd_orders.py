"""Aufträge: Meldungen über den Tag und die Rückholung. Zufall nur über einen übergebenen Seed."""

from dataclasses import dataclass, replace

import numpy as np

import ptd_constants as C
from ptd_hospital import Hospital

RETURN_OFFSET = 1_000_000


@dataclass(frozen=True)
class Order:
    oid: int
    t: int               # Meldezeit in Minuten ab 06:00
    o: int               # Abholort (Index im Haus)
    d: int               # Zielort
    kind: str            # bett, rollstuhl, gehend
    prio: int            # 0 Notfall, 1 dringend, 2 Routine
    exam: int = 0        # Minuten bis zur Rückholmeldung nach der Ankunft (0: keine Rückholung)
    ret: bool = False    # hat eine Rückholung
    ret_prio: int = 2
    is_return: bool = False
    parent_t: int = 0     # Meldezeit der Hinfahrt (nur bei Rückholungen), damit der Tag für alle Regeln dieselben Aufträge zählt


def rate_to_scale(rate_per_hour: float) -> float:
    """Neue Aufträge je Stunde im Mittel -> Dichte-Faktor m der Meldeprozesse (m = 1: BASE_RATE bei Profilmittel 1)."""
    return rate_per_hour / (C.BASE_RATE * float(np.mean(C.PROFILE)))


def _draw_one(h: Hospital, rng: np.random.Generator, oid: int, t: int, ret_prio: int) -> Order:
    """Ein Auftrag nach Auftragsmix: 55 % Diagnostik mit Rückholung, 10 % Notaufnahme, 5 % Verlegung, 15 % Entlassung, 15 % Aufnahme."""
    u = rng.random()
    station = int(rng.choice(h.stations))
    ed = h.index("Notaufnahme")
    if u < 0.55:
        d = int(rng.choice(h.diagnostics))
        kind = str(rng.choice(C.KINDS, p=[0.35, 0.40, 0.25]))
        is_op = d == h.index("OP")
        prio = int(rng.choice(3, p=[0.02, 0.5, 0.48] if is_op else [0.01, 0.24, 0.75]))
        if is_op:
            kind = "bett"
        exam = max(1, int(rng.lognormal(np.log(h.exam.get(d, 20)), 0.3)))
        return Order(oid, t, station, d, kind, prio, exam, True, ret_prio)
    if u < 0.65:
        kind = str(rng.choice(C.KINDS, p=[0.5, 0.35, 0.15]))
        prio = int(rng.choice(3, p=[0.25, 0.5, 0.25]))
        return Order(oid, t, ed, station, kind, prio)
    if u < 0.70:
        d = int(rng.choice([s for s in h.stations if s != station]))
        prio = int(rng.choice(3, p=[0.0, 0.3, 0.7]))
        return Order(oid, t, station, d, "bett", prio)
    if u < 0.85:
        kind = str(rng.choice(["rollstuhl", "gehend"], p=[0.6, 0.4]))
        return Order(oid, t, station, h.index("Ausgang"), kind, 2)
    kind = str(rng.choice(C.KINDS, p=[0.15, 0.55, 0.30]))
    prio = int(rng.choice(3, p=[0.0, 0.15, 0.85]))
    return Order(oid, t, h.depot, station, kind, prio)


def generate_orders(h: Hospital, seed: int, scale: float, window: int = C.DAY_MINUTES, profile=C.PROFILE) -> list[Order]:
    """Meldungen im Fenster [0, window): Poisson je Minute mit stündlichem Profil; deterministisch aus (seed, scale, window)."""
    rng = np.random.default_rng(seed)
    orders: list[Order] = []
    for t in range(window):
        lam = C.BASE_RATE * scale * profile[min(t // 60, len(profile) - 1)] / 60.0
        for _ in range(int(rng.poisson(lam))):
            oid = len(orders)
            orders.append(_draw_one(h, rng, oid, t, 1 if oid % 7 == 0 else 2))
    return orders


def make_return(order: Order, finish: int) -> Order:
    """Die Rückholung entsteht erst nach der Untersuchung: Meldung bei Ankunftsende plus Untersuchungsdauer, Gegenrichtung."""
    kind = "rollstuhl" if order.kind == "gehend" else order.kind
    return replace(order, oid=order.oid + RETURN_OFFSET, t=int(finish + order.exam), o=order.d, d=order.o, kind=kind,
                   prio=order.ret_prio, exam=0, ret=False, is_return=True, parent_t=order.t)
