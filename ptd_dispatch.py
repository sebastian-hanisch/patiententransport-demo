"""Zuweisungsregeln: je Regel eine reine Funktion ohne Zustand (DEMO-PLAYBOOK §1b).

Eingaben: Zeit `t`, Liste der wartenden Aufträge, freie Träger `idle`, Position `pos`, Frei-Zeit `free_at`, Qualifikation `qualified`
und die Leerfahrt-Wegzeitmatrix `T0`. Ausgabe: Liste von (Träger, Auftrag). Kein Träger und kein Auftrag kommt doppelt vor.
Ungarisch-Zuordnung über scipy (lazy importiert), damit der Kaltstart kurz bleibt.
"""

import ptd_constants as C

BIG = 1e6


def compatible(order, porter: int, qualified) -> bool:
    """Ein Bett-Auftrag braucht einen Träger mit Bett-Qualifikation; alle anderen Aufträge kann jeder fahren."""
    return order.kind != "bett" or bool(qualified[porter])


def nearest_compatible_idle(order, idle, pos, qualified, T0):
    """Der freie, zum Auftrag passende Träger mit der kürzesten Anfahrt (bei Gleichstand der kleinere Index); None, wenn keiner passt."""
    best, best_t = None, None
    for p in idle:
        if not compatible(order, p, qualified):
            continue
        a = T0[pos[p], order.o]
        if best_t is None or a < best_t:
            best, best_t = p, a
    return best


def assign_in_order(ordered_orders, idle, pos, qualified, T0):
    """Aufträge in der gegebenen Reihenfolge; jeder bekommt den nächsten passenden freien Träger."""
    idle = list(idle)
    pairs = []
    for order in ordered_orders:
        if not idle:
            break
        p = nearest_compatible_idle(order, idle, pos, qualified, T0)
        if p is not None:
            pairs.append((p, order))
            idle.remove(p)
    return pairs


def greedy_nearest_pairs(waiting, idle, pos, qualified, T0):
    """Wiederholt das (Träger, Auftrag)-Paar mit der kürzesten Anfahrt aus allen passenden Paaren."""
    idle, left, pairs = list(idle), list(waiting), []
    while idle and left:
        best = None
        for order in left:
            for p in idle:
                if not compatible(order, p, qualified):
                    continue
                a = T0[pos[p], order.o]
                if best is None or a < best[0]:
                    best = (a, p, order)
        if best is None:
            break
        _, p, order = best
        pairs.append((p, order))
        idle.remove(p)
        left.remove(order)
    return pairs


def tie_break(oid: int, porter: int) -> float:
    """Winziger, fester Aufschlag je (Auftrag, Träger): gleich teure Zuordnungen werden eindeutig und unabhängig von der scipy-Version.

    Höchstens 1e-6 je Paar; die Kosten sind ganze Minuten, die Aufschläge können also nie eine echte Rangfolge drehen."""
    return 1e-6 * (((oid + 3) * (porter + 5) * 2654435761) % 1009) / 1009   # Produkt, nicht Summe: sonst bleiben Vertauschungen gleich teuer


def hungarian_pairs(t, orders, candidates, idle, pos, free_at, qualified, T0):
    """Kostenminimale Zuordnung; Kosten = Wartezeit bis der Träger frei ist + Anfahrt - Klassengewicht * Alter des Auftrags.

    Bestätigt werden nur Paare mit einem jetzt freien Träger; Aufträge, die einem bald freien Träger zugedacht sind, warten weiter."""
    import numpy as np
    from scipy.optimize import linear_sum_assignment

    if not orders or not candidates:
        return []
    cand = np.array(candidates)
    oid = np.array([o.oid for o in orders], dtype=np.int64)
    origin = np.array([o.o for o in orders])
    age_weight = np.array([C.CLASS_WEIGHT[o.prio] * (t - o.t) for o in orders])
    needs_bed = np.array([o.kind == "bett" for o in orders])
    can_bed = np.array([bool(qualified[p]) for p in candidates])
    avail = np.maximum(np.array([free_at[p] for p in candidates]) - t, 0)
    where = np.array([pos[p] for p in candidates])
    ties = 1e-6 * (((oid[:, None] + 3) * (cand[None, :] + 5) * 2654435761) % 1009) / 1009   # = tie_break(oid, porter)
    cost = avail[None, :] + np.asarray(T0)[where[None, :], origin[:, None]] - age_weight[:, None] + ties
    cost = np.where(needs_bed[:, None] & ~can_bed[None, :], BIG, cost)
    rows, cols = linear_sum_assignment(cost)
    idle_set = set(idle)
    return [(candidates[j], orders[i]) for i, j in zip(rows, cols) if cost[i, j] < BIG / 2 and candidates[j] in idle_set]


def urgent_first(waiting, idle, pos, qualified, T0):
    """Notfälle sofort nach Meldezeit; gibt (Paare, übrige freie Träger, übrige Aufträge) zurück."""
    urgent = sorted((o for o in waiting if o.prio == 0), key=lambda o: o.t)
    pairs = assign_in_order(urgent, idle, pos, qualified, T0)
    used_p = {p for p, _ in pairs}
    used_o = {id(o) for _, o in pairs}
    return pairs, [p for p in idle if p not in used_p], [o for o in waiting if id(o) not in used_o]


def choose_fifo(t, waiting, idle, pos, free_at, qualified, T0, batch_min):
    return assign_in_order(sorted(waiting, key=lambda o: o.t), idle, pos, qualified, T0)


def choose_nahe(t, waiting, idle, pos, free_at, qualified, T0, batch_min):
    return greedy_nearest_pairs(waiting, idle, pos, qualified, T0)


def choose_prio(t, waiting, idle, pos, free_at, qualified, T0, batch_min):
    return assign_in_order(sorted(waiting, key=lambda o: (o.prio, o.t)), idle, pos, qualified, T0)


def choose_frist(t, waiting, idle, pos, free_at, qualified, T0, batch_min):
    return assign_in_order(sorted(waiting, key=lambda o: o.t + C.SOLL[o.prio]), idle, pos, qualified, T0)


def choose_batch(t, waiting, idle, pos, free_at, qualified, T0, batch_min):
    pairs, idle_left, rest = urgent_first(waiting, idle, pos, qualified, T0)
    if t % batch_min != 0 or not idle_left:
        return pairs
    return pairs + hungarian_pairs(t, rest, idle_left, idle_left, pos, free_at, qualified, T0)


def choose_voraus(t, waiting, idle, pos, free_at, qualified, T0, batch_min):
    pairs, idle_left, rest = urgent_first(waiting, idle, pos, qualified, T0)
    if not idle_left or not rest:
        return pairs
    idle_set = set(idle_left)
    soon = [p for p in range(len(pos)) if p in idle_set or (p not in {q for q, _ in pairs} and 0 < free_at[p] - t <= C.LOOKAHEAD_MIN)]
    return pairs + hungarian_pairs(t, rest, soon, idle_left, pos, free_at, qualified, T0)


CHOOSERS = {"fifo": choose_fifo, "nahe": choose_nahe, "prio": choose_prio, "frist": choose_frist,
            "batch": choose_batch, "voraus": choose_voraus}


def choose(rule, t, waiting, idle, pos, free_at, qualified, T0, batch_min=C.DEFAULT_BATCH):
    return CHOOSERS[rule](t, waiting, idle, pos, free_at, qualified, T0, batch_min)
