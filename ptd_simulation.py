"""Ereignisgesteuerte Simulation eines Tages: Meldungen, Zuweisung durch eine Regel, Fahrten, Rückholungen, Pausen.

Zustandsübergänge in kleinen Einheiten (`start_trip`, `apply_breaks`, `next_event_time`); `simulate` ruft nur der Reihe nach auf.
Die Zeit springt von Ereignis zu Ereignis. Wo eine Regel mit der Zeit anders entscheiden kann (Vorausschau: Alter wächst; Sammelfenster:
Takt), läuft sie minutenweise bzw. im Takt weiter, solange ein Träger frei ist und ein Auftrag wartet.
"""

import heapq
from dataclasses import dataclass

import ptd_constants as C
import ptd_dispatch as D
from ptd_hospital import Hospital
from ptd_orders import Order, make_return


@dataclass(frozen=True)
class Record:
    oid: int
    prio: int
    kind: str
    is_return: bool
    report: int          # Meldezeit
    arrive: int          # Ankunft des Trägers am Abholort
    wait: int            # arrive - report
    porter: int
    approach: int        # Leerfahrt zum Abholort
    transport: int       # Fahrt mit Patient
    finish: int          # Ende der Übergabe am Ziel
    day_t: int = 0       # Meldezeit der Hinfahrt: bestimmt, ob der Auftrag zum Tag zählt (bei Rückholungen die der Hinfahrt)


@dataclass(frozen=True)
class SimResult:
    records: tuple
    queue: tuple         # (Minute, wartende Aufträge) nach jeder Entscheidung
    busy_minutes: float  # Summe der Fahrtminuten innerhalb des Tages
    n_porters: int
    complete: bool       # alle Aufträge vor der Zeitobergrenze erledigt


def qualified_flags(n_porters: int, n_qualified: int) -> list[bool]:
    """Die ersten n_qualified Träger dürfen Betten fahren."""
    return [p < n_qualified for p in range(n_porters)]


def n_qualified_from_percent(n_porters: int, percent: int) -> int:
    """Mindestens ein Träger mit Bett-Qualifikation, höchstens alle; ab .5 wird aufgerundet (ganzzahlig gerechnet, kein Banker-Runden)."""
    return min(n_porters, max(1, (2 * n_porters * percent + 100) // 200))


def break_times(n_porters: int) -> list[int]:
    return [C.BREAK_START + C.BREAK_STAGGER * (p % C.BREAK_SLOTS) for p in range(n_porters)]


def start_trip(h: Hospital, porter: int, order: Order, t: int, pos, free_at):
    """Träger fährt zum Abholort, übergibt, fährt mit Patient zum Ziel, übergibt. Setzt pos und free_at; gibt den Record zurück."""
    approach = int(h.T["leer"][pos[porter], order.o])
    arrive = t + approach
    transport = int(h.T[order.kind][order.o, order.d])
    finish = arrive + C.HANDOVER + transport + C.HANDOVER
    free_at[porter] = finish
    pos[porter] = order.d
    return Record(order.oid, order.prio, order.kind, order.is_return, order.t, arrive, arrive - order.t, porter, approach, transport, finish,
                  order.parent_t if order.is_return else order.t)


def apply_breaks(t, free_at, on_break, break_at):
    """Ein freier Träger geht in die Pause, sobald seine Pausenzeit erreicht ist (erste freie Minute danach)."""
    for p in range(len(free_at)):
        if not on_break[p] and t >= break_at[p] and free_at[p] <= t:
            on_break[p] = True
            free_at[p] = t + C.BREAK_LEN


def busy_in_day(arrive: int, finish: int, t_assign: int) -> int:
    """Minuten der Fahrt, die in den Tag (0 bis DAY_MINUTES) fallen."""
    return max(0, min(finish, C.DAY_MINUTES) - max(t_assign, 0))


def next_event_time(t, arrivals, ai, returns, free_at, on_break, break_at, breaks, waiting, idle_exists, rule, batch_min):
    """Nächste Zeit, zu der sich etwas ändern kann; None, wenn nichts mehr kommt."""
    cands = []
    if ai < len(arrivals):
        cands.append(arrivals[ai].t)
    if returns:
        cands.append(returns[0][0])
    for p in range(len(free_at)):
        if free_at[p] > t:
            cands.append(free_at[p])
        if breaks and not on_break[p]:
            cands.append(max(break_at[p], free_at[p]))
    if waiting and idle_exists:
        if rule == "voraus":
            cands.append(t + 1)
        elif rule == "batch":
            cands.append(t + batch_min - t % batch_min)
    cands = [c for c in cands if c > t]
    return min(cands) if cands else None


def simulate(h: Hospital, orders, n_porters: int, n_qualified: int, rule: str, batch_min: int = C.DEFAULT_BATCH,
             breaks: bool = True) -> SimResult:
    arrivals = sorted(orders, key=lambda o: (o.t, o.oid))
    T0 = h.T["leer"]
    pos = [h.depot] * n_porters
    free_at = [0] * n_porters
    qualified = qualified_flags(n_porters, n_qualified)
    break_at = break_times(n_porters)
    on_break = [not breaks] * n_porters
    waiting, returns, records, queue = [], [], [], []
    seq = 0
    ai, t, busy, complete = 0, 0, 0, True
    while True:
        while ai < len(arrivals) and arrivals[ai].t <= t:
            waiting.append(arrivals[ai])
            ai += 1
        while returns and returns[0][0] <= t:
            waiting.append(heapq.heappop(returns)[2])
        apply_breaks(t, free_at, on_break, break_at)
        idle = [p for p in range(n_porters) if free_at[p] <= t]
        if waiting and idle:
            pairs = D.choose(rule, t, waiting, idle, pos, free_at, qualified, T0, batch_min)
            assigned = set()
            for p, order in pairs:
                rec = start_trip(h, p, order, t, pos, free_at)
                records.append(rec)
                busy += busy_in_day(rec.arrive, rec.finish, t)
                assigned.add(id(order))
                if order.ret:
                    back = make_return(order, rec.finish)
                    seq += 1
                    heapq.heappush(returns, (back.t, seq, back))
            waiting = [o for o in waiting if id(o) not in assigned]
        queue.append((t, len(waiting)))
        idle_exists = any(free_at[p] <= t for p in range(n_porters))
        nxt = next_event_time(t, arrivals, ai, returns, free_at, on_break, break_at, breaks, waiting, idle_exists, rule, batch_min)
        if nxt is None:
            break
        if nxt > C.SIM_LIMIT:
            complete = False
            break
        t = nxt
    for order in waiting:   # nicht mehr erledigt: als abgeschnitten zählen, Wartezeit mindestens bis zur Obergrenze
        records.append(Record(order.oid, order.prio, order.kind, order.is_return, order.t, C.SIM_LIMIT, max(C.SIM_LIMIT - order.t, 0),
                              -1, 0, 0, C.SIM_LIMIT, order.parent_t if order.is_return else order.t))
    return SimResult(tuple(records), tuple(queue), float(busy), n_porters, complete and not waiting)
