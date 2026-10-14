"""Kennzahlen, Verdikt-Logik und Sweeps.

Alles, was die App als Befund zeigt, wird hier aus der Simulation berechnet; Texte nennen nur Zahlen aus diesen Funktionen.
"""

from dataclasses import dataclass
from statistics import median

import numpy as np

import ptd_constants as C
from ptd_hospital import HOSPITAL
from ptd_orders import generate_orders, rate_to_scale
from ptd_simulation import SimResult, n_qualified_from_percent, simulate


@dataclass(frozen=True)
class Settings:
    rate: int = C.DEFAULT_RATE
    porters: int = C.DEFAULT_PORTERS
    qual: int = C.DEFAULT_QUAL
    batch: int = C.DEFAULT_BATCH
    breaks: str = C.DEFAULT_BREAKS
    seed: int = C.DEFAULT_SEED


@dataclass(frozen=True)
class ClassStat:
    n: int
    mean: float
    p90: float
    miss: float          # Anteil, der das Soll überschreitet (0 bis 1)


@dataclass(frozen=True)
class RuleStat:
    rule: str
    classes: tuple       # drei ClassStat
    utilization: float   # Fahrminuten / (Träger * Tag)
    empty_share: float   # Leerfahrten / (Leerfahrten + Fahrten mit Patient)
    weighted_wait: float # Summe Gewicht * Wartezeit
    n_orders: int
    complete: bool


@dataclass(frozen=True)
class Analysis:
    settings: Settings
    n_orders: int
    stats: dict          # Regel -> RuleStat
    queues: dict         # Regel -> Minuten-Raster der Warteschlange
    cost_weights: tuple


def class_stat(records, prio: int) -> ClassStat:
    w = np.array([r.wait for r in records if r.prio == prio], dtype=float)
    if len(w) == 0:
        return ClassStat(0, 0.0, 0.0, 0.0)
    return ClassStat(len(w), float(w.mean()), float(np.percentile(w, 90)), float((w > C.SOLL[prio]).mean()))


def rule_stat(rule: str, sim: SimResult) -> RuleStat:
    """Kennzahlen eines Tages; gezählt werden alle Hinfahrten, die vor 18:00 gemeldet wurden, samt ihren Rückholungen (für alle Regeln dieselben)."""
    recs = [r for r in sim.records if r.day_t < C.DAY_MINUTES]
    approach = sum(r.approach for r in recs)
    transport = sum(r.transport for r in recs)
    empty = approach / (approach + transport) if approach + transport else 0.0
    return RuleStat(
        rule=rule,
        classes=tuple(class_stat(recs, c) for c in range(3)),
        utilization=sim.busy_minutes / (sim.n_porters * C.DAY_MINUTES),
        empty_share=empty,
        weighted_wait=float(sum(C.CLASS_WEIGHT[r.prio] * r.wait for r in recs)),
        n_orders=len(recs),
        complete=sim.complete,
    )


def queue_grid(sim: SimResult, step: int = 5, end: int = C.DAY_MINUTES) -> tuple:
    """Länge der Warteschlange auf einem festen Raster (letzter Wert gilt bis zum nächsten Ereignis)."""
    times = np.array([q[0] for q in sim.queue])
    values = np.array([q[1] for q in sim.queue])
    grid = np.arange(0, end + 1, step)
    if len(times) == 0:
        return tuple(0 for _ in grid)
    idx = np.searchsorted(times, grid, side="right") - 1
    return tuple(int(values[max(i, 0)]) if i >= 0 else 0 for i in idx)


def run_day(settings: Settings, rules=C.RULES, orders=None):
    """Ein Tag, alle Regeln auf denselben Meldungen. Gibt (orders, {Regel: SimResult}) zurück."""
    if orders is None:
        orders = generate_orders(HOSPITAL, settings.seed, rate_to_scale(settings.rate))
    nq = n_qualified_from_percent(settings.porters, settings.qual)
    sims = {r: simulate(HOSPITAL, orders, settings.porters, nq, r, settings.batch, settings.breaks == "mit Pausen") for r in rules}
    return orders, sims


def analyse(settings: Settings) -> Analysis:
    orders, sims = run_day(settings)
    stats = {r: rule_stat(r, s) for r, s in sims.items()}
    queues = {r: queue_grid(s) for r, s in sims.items()}
    return Analysis(settings, len(orders), stats, queues, C.CLASS_WEIGHT)


def sweep_rate(base: Settings, rates=C.RATE_SWEEP, seeds=C.SWEEP_SEEDS, rules=C.RULES) -> list[dict]:
    """Je Dichte und Regel der Median über die festen Tage von: mittlere Wartezeit je Klasse, Verfehlquote je Klasse, Auslastung."""
    rows = []
    for rate in rates:
        per_rule = {r: [] for r in rules}
        for seed in seeds:
            s = Settings(rate, base.porters, base.qual, base.batch, base.breaks, seed)
            _, sims = run_day(s, rules)
            for r in rules:
                per_rule[r].append(rule_stat(r, sims[r]))
        row = {"rate": rate}
        for r in rules:
            vals = per_rule[r]
            row[r] = {
                "wait": tuple(median(v.classes[c].mean for v in vals) for c in range(3)),
                "miss": tuple(median(v.classes[c].miss for v in vals) for c in range(3)),
                "util": median(v.utilization for v in vals),
                "empty": median(v.empty_share for v in vals),
            }
        rows.append(row)
    return rows


def first_rate_above(rows: list[dict], rule: str, cls: int, limit: float):
    """Kleinste gemessene Dichte, bei der die mittlere Wartezeit der Klasse über `limit` liegt; None, wenn nie."""
    for row in rows:
        if row[rule]["wait"][cls] > limit:
            return row
    return None


# --- Verdikte (rein: Art, Text) ----------------------------------------------------------------------------------------------------------

def fmt(x: float, digits: int = 1) -> str:
    return f"{x:.{digits}f}".replace(".", ",")


def pct(x: float) -> str:
    return f"{100 * x:.0f} %".replace(".", ",")


def verdict_core(a: Analysis) -> tuple[str, str]:
    """Kernfrage 'Wie viel macht die Regel aus?' für diesen Tag, aus den Notfall- und Routine-Zahlen von FIFO, Priorität, Vorausschau."""
    fifo, prio, voraus = a.stats["fifo"], a.stats["prio"], a.stats["voraus"]
    soll_n = C.SOLL[0]
    nf, np_, nv = fifo.classes[0].mean, prio.classes[0].mean, voraus.classes[0].mean
    rf, rp, rv = fifo.classes[2].mean, prio.classes[2].mean, voraus.classes[2].mean
    spread = max(s.classes[0].mean for s in a.stats.values()) - min(s.classes[0].mean for s in a.stats.values())
    if nf <= soll_n and spread < 3.0:
        return "info", (f"Bei {pct(fifo.utilization)} Auslastung entscheidet die Regel kaum: Ein Notfall wartet im Mittel "
                        f"{fmt(min(s.classes[0].mean for s in a.stats.values()))} bis {fmt(max(s.classes[0].mean for s in a.stats.values()))} min "
                        f"(Soll {soll_n} min), Routine {fmt(rf)} min unter FIFO.")
    if nf > soll_n and np_ <= soll_n:
        if rv <= C.SOLL[2]:
            return "success", (f"Unter FIFO wartet ein Notfall {fmt(nf)} min (Soll {soll_n} min), Routine {fmt(rf)} min: FIFO kennt keine Dringlichkeit. "
                               f"Priorität holt den Notfall auf {fmt(np_)} min, schiebt Routine aber auf {fmt(rp)} min. "
                               f"Die Vorausschau hält Notfall bei {fmt(nv)} min und Routine bei {fmt(rv)} min (Soll {C.SOLL[2]} min).")
        return "warning", (f"Unter FIFO wartet ein Notfall {fmt(nf)} min (Soll {soll_n} min). Priorität holt ihn auf {fmt(np_)} min, "
                           f"Routine wartet dafür {fmt(rp)} min; auch die Vorausschau bringt Routine nur auf {fmt(rv)} min (Soll {C.SOLL[2]} min).")
    if nf > soll_n and np_ > soll_n:
        return "warning", (f"Hier reicht die Kapazität nicht: Selbst unter Priorität wartet ein Notfall {fmt(np_)} min (Soll {soll_n} min), "
                           f"unter FIFO {fmt(nf)} min. Zusätzliche Träger helfen mehr als jede Regel.")
    return "info", (f"Notfall liegt unter jeder Regel im Soll ({fmt(nf)} min unter FIFO, {fmt(np_)} min unter Priorität); "
                    f"Routine wartet {fmt(rf)} min unter FIFO und {fmt(rp)} min unter Priorität.")


def verdict_sweep(rows: list[dict]) -> tuple[str, str]:
    """Experiment Dichte: ab welcher Dichte FIFO das Notfall-Soll reißt und wie sich Priorität und Vorausschau dort verhalten."""
    hit = first_rate_above(rows, "fifo", 0, C.SOLL[0])
    last = rows[-1]
    if hit is None:
        return "info", (f"Bis {last['rate']} neue Aufträge je Stunde bleibt der Notfall unter FIFO im Soll "
                        f"(Median über {len(C.SWEEP_SEEDS)} Tage, {fmt(last['fifo']['wait'][0])} min bei {last['rate']} je Stunde).")
    return "warning", (f"Unter FIFO überschreitet der Notfall das Soll ab {hit['rate']} neuen Aufträgen je Stunde "
                       f"({fmt(hit['fifo']['wait'][0])} min bei {pct(hit['fifo']['util'])} Auslastung; Median über {len(C.SWEEP_SEEDS)} Tage). "
                       f"Dort liegt der Notfall unter Priorität bei {fmt(hit['prio']['wait'][0])} min und unter Vorausschau bei "
                       f"{fmt(hit['voraus']['wait'][0])} min; Routine wartet {fmt(hit['prio']['wait'][2])} min (Priorität) "
                       f"gegen {fmt(hit['voraus']['wait'][2])} min (Vorausschau).")
