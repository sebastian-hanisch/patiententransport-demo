"""Orakel-Referenz: minutengetaktete Simulation mit eigenen, bewusst einfachen Regel-Implementierungen.

Anderer Rechenweg als `ptd_simulation` (Ereignissprünge) und `ptd_dispatch` (reine Regelfunktionen): jede Minute wird durchlaufen, jede
Regel steht hier als naive Schleife. Nur das Haus (Wegzeiten) und die Aufträge werden geteilt. Nicht Teil der Laufzeit der App.
"""

import itertools

SOLL = (10, 20, 40)
WEIGHT = (8, 3, 1)
HANDOVER = 2
BREAK_START, BREAK_LEN, BREAK_STAGGER, BREAK_SLOTS = 330, 30, 20, 4
LOOKAHEAD = 8


def _min_assignment(cost):
    """Kostenminimale Zuordnung (jede Zeile höchstens einer Spalte, so viele Paare wie möglich) durch vollständige Aufzählung."""
    n_rows, n_cols = len(cost), len(cost[0])
    k = min(n_rows, n_cols)
    best, best_pairs = None, None
    for rows in itertools.combinations(range(n_rows), k):
        for cols in itertools.permutations(range(n_cols), k):
            total = sum(cost[r][c] for r, c in zip(rows, cols))
            if best is None or total < best - 1e-12:
                best, best_pairs = total, list(zip(rows, cols))
    return best_pairs or []


def reference_simulate(T, depot, orders, n_porters, n_qualified, rule, batch_min=5, breaks=True, limit=1800):
    """Gibt {oid: (Wartezeit, Träger)} zurück."""
    T0 = T["leer"]
    pos = [depot] * n_porters
    free = [0] * n_porters
    on_break = [not breaks] * n_porters
    break_at = [BREAK_START + BREAK_STAGGER * (p % BREAK_SLOTS) for p in range(n_porters)]
    ok = [p < n_qualified for p in range(n_porters)]
    pending = sorted(orders, key=lambda o: (o.t, o.oid))
    returns, waiting, result = [], [], {}

    def can(order, p):
        return order.kind != "bett" or ok[p]

    def nearest(order, idle):
        c = [p for p in idle if can(order, p)]
        return min(c, key=lambda p: (T0[pos[p]][order.o], p)) if c else None

    def in_order(seq, idle):
        idle, out = list(idle), []
        for order in seq:
            p = nearest(order, idle)
            if p is not None:
                out.append((p, order))
                idle.remove(p)
        return out

    def hungarian(t, orders_, cands, idle):
        if not orders_ or not cands:
            return []
        def eps(oid, p):
            return 1e-6 * (((oid + 3) * (p + 5) * 2654435761) % 1009) / 1009

        cost = [[(max(free[p] - t, 0) + T0[pos[p]][o.o] - WEIGHT[o.prio] * (t - o.t) + eps(o.oid, p)) if can(o, p) else 1e9
                 for p in cands] for o in orders_]
        return [(cands[c], orders_[r]) for r, c in _min_assignment(cost) if cost[r][c] < 1e8 and cands[c] in idle]

    for t in range(limit + 1):
        while pending and pending[0].t <= t:
            waiting.append(pending.pop(0))
        due = [r for r in returns if r.t <= t]
        returns = [r for r in returns if r.t > t]
        waiting.extend(due)
        for p in range(n_porters):
            if not on_break[p] and t >= break_at[p] and free[p] <= t:
                on_break[p], free[p] = True, t + BREAK_LEN
        idle = [p for p in range(n_porters) if free[p] <= t]
        pairs = []
        if waiting and idle:
            if rule == "fifo":
                pairs = in_order(sorted(waiting, key=lambda o: o.t), idle)
            elif rule == "prio":
                pairs = in_order(sorted(waiting, key=lambda o: (o.prio, o.t)), idle)
            elif rule == "frist":
                pairs = in_order(sorted(waiting, key=lambda o: o.t + SOLL[o.prio]), idle)
            elif rule == "nahe":
                left, free_p = list(waiting), list(idle)
                while left and free_p:
                    cand = [(T0[pos[p]][o.o], p, i) for i, o in enumerate(left) for p in free_p if can(o, p)]
                    if not cand:
                        break
                    _, p, i = min(cand, key=lambda c: (c[0], c[2], c[1]))
                    pairs.append((p, left.pop(i)))
                    free_p.remove(p)
            else:
                urgent = sorted((o for o in waiting if o.prio == 0), key=lambda o: o.t)
                pairs = in_order(urgent, idle)
                used = {p for p, _ in pairs}
                left_idle = [p for p in idle if p not in used]
                rest = [o for o in waiting if o.prio != 0]
                if rule == "batch" and t % batch_min == 0 and left_idle:
                    pairs += hungarian(t, rest, left_idle, set(left_idle))
                elif rule == "voraus" and left_idle:
                    cands = [p for p in range(n_porters) if p not in used and (p in left_idle or 0 < free[p] - t <= LOOKAHEAD)]
                    pairs += hungarian(t, rest, cands, set(left_idle))
        taken = set()
        for p, order in pairs:
            arrive = t + T0[pos[p]][order.o]
            result[order.oid] = (arrive - order.t, p)
            finish = arrive + HANDOVER + T[order.kind][order.o][order.d] + HANDOVER
            free[p], pos[p] = finish, order.d
            taken.add(order.oid)
            if order.ret:
                kind = "rollstuhl" if order.kind == "gehend" else order.kind
                returns.append(type(order)(order.oid + 1_000_000, int(finish + order.exam), order.d, order.o, kind, order.ret_prio,
                                           0, False, order.ret_prio, True))
        waiting = [o for o in waiting if o.oid not in taken]
        if not pending and not returns and not waiting and all(f <= t for f in free):
            break
    return result
