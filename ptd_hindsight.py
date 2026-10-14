"""Hindsight-Schranke: das beste Offline-Ergebnis bei voller Kenntnis aller Aufträge (CP-SAT).

Ein Träger darf erst nach der Meldung losfahren (kein Vorwegbewegen): das misst den Preis der Unkenntnis künftiger Meldungen, nicht den
eines Hellsehers. Zielgröße: Summe Klassengewicht * (Ankunft - Meldung). Jede Nebenbedingungsfamilie ist eine eigene Funktion
(DEMO-PLAYBOOK §1b); `build_model` ruft nur der Reihe nach auf. ortools wird erst beim Lösen importiert.
"""

import os
from dataclasses import dataclass

import ptd_constants as C
from ptd_hospital import Hospital
from ptd_orders import Order, generate_orders, rate_to_scale
from ptd_simulation import n_qualified_from_percent, simulate

HORIZON = 900


@dataclass(frozen=True)
class Job:
    o: int
    d: int
    kind: str
    prio: int
    rep: int | None      # feste Meldezeit; None bei Rückholungen (hängt vom Vorgänger ab)
    pred: int | None     # Index des Hinfahrt-Jobs
    exam: int


@dataclass(frozen=True)
class HindsightResult:
    status: str                  # OPTIMAL, FEASIBLE, INFEASIBLE oder UNKNOWN (Namen des Lösers)
    objective: float | None      # beste gefundene gewichtete Wartezeit
    bound: float | None          # untere Schranke des Lösers (gültig auch ohne Optimalitätsbeweis)
    starts: tuple                # Ankunftszeit je Job
    routes: tuple                # je Träger die Job-Indizes in Fahrtreihenfolge
    n_jobs: int


def make_jobs(orders) -> list[Job]:
    """Aufträge -> Jobs; jede Rückholung ist ein eigener Job direkt nach ihrer Hinfahrt."""
    jobs: list[Job] = []
    for o in orders:
        jobs.append(Job(o.o, o.d, o.kind, o.prio, o.t, None, 0))
        if o.ret:
            back = "rollstuhl" if o.kind == "gehend" else o.kind
            jobs.append(Job(o.d, o.o, back, o.ret_prio, None, len(jobs) - 1, o.exam))
    return jobs


def ride_minutes(h: Hospital, job: Job) -> int:
    """Von der Ankunft am Abholort bis zum Ende der Übergabe am Ziel."""
    return 2 * C.HANDOVER + int(h.T[job.kind][job.o, job.d])


def add_start_times(model, h, jobs):
    """Ankunftszeit s_j und Meldezeit rep_j je Job; Rückholmeldung = Ankunft der Hinfahrt + Fahrt + Untersuchung."""
    s = [model.NewIntVar(0, HORIZON, f"s{j}") for j in range(len(jobs))]
    rep = []
    for j, job in enumerate(jobs):
        if job.pred is None:
            rep.append(job.rep)
        else:
            r = model.NewIntVar(0, HORIZON, f"rep{j}")
            model.Add(r == s[job.pred] + ride_minutes(h, jobs[job.pred]) + job.exam)
            rep.append(r)
        model.Add(s[j] >= rep[j])
    return s, rep


def add_porter_route(model, h, jobs, s, rep, p, may_carry_beds):
    """Eine Route je Träger als Kreis über Depot (Knoten 0) und Jobs: Start-, Folge- und Endbögen mit Zeitbedingungen.

    Gibt (skip, arcs) zurück: skip[j] = 1, wenn der Träger Job j nicht fährt; arcs = {(a, b): Literal}."""
    T0 = h.T["leer"]
    n = len(jobs)
    skip = [model.NewBoolVar(f"skip{p}_{j}") for j in range(n)]
    lits, arcs = [], {}

    def arc(a, b):
        lit = model.NewBoolVar(f"a{p}_{a}_{b}")
        arcs[(a, b)] = lit
        lits.append((a, b, lit))
        return lit

    for j, job in enumerate(jobs):
        lits.append((j + 1, j + 1, skip[j]))
        if job.kind == "bett" and not may_carry_beds:
            model.Add(skip[j] == 1)
            continue
        first = arc(0, j + 1)
        lead = int(T0[h.depot, job.o])
        model.Add(s[j] >= rep[j] + lead).OnlyEnforceIf(first)
        arc(j + 1, 0)
    for j, a in enumerate(jobs):
        if a.kind == "bett" and not may_carry_beds:
            continue
        for k, b in enumerate(jobs):
            if k == j or (b.kind == "bett" and not may_carry_beds) or a.pred == k:
                continue
            lit = arc(j + 1, k + 1)
            lead = int(T0[a.d, b.o])
            model.Add(s[k] >= s[j] + ride_minutes(h, a) + lead).OnlyEnforceIf(lit)
            model.Add(s[k] >= rep[k] + lead).OnlyEnforceIf(lit)
    lits.append((0, 0, model.NewBoolVar(f"idle{p}")))
    model.AddCircuit(lits)
    return skip, arcs


def add_each_job_once(model, skips, n_jobs):
    for j in range(n_jobs):
        model.Add(sum(1 - skip[j] for skip in skips) == 1)


def add_symmetry_breaking(model, skips, jobs, qualified):
    """Gleichartige Träger (gleiche Qualifikation) werden in der Reihenfolge ihres kleinsten Jobs benutzt."""
    for p in range(1, len(skips)):
        q = max((r for r in range(p) if bool(qualified[r]) == bool(qualified[p])), default=None)
        if q is None:
            continue
        for j, job in enumerate(jobs):
            if job.kind == "bett" and not qualified[p]:
                continue
            model.Add(1 - skips[p][j] <= sum(1 - skips[q][k] for k in range(j)))


def add_objective(model, jobs, s, rep):
    model.Minimize(sum(C.CLASS_WEIGHT[job.prio] * (s[j] - rep[j]) for j, job in enumerate(jobs)))


def build_model(h, jobs, n_porters, qualified):
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    s, rep = add_start_times(model, h, jobs)
    skips, all_arcs = [], []
    for p in range(n_porters):
        skip, arcs = add_porter_route(model, h, jobs, s, rep, p, bool(qualified[p]))
        skips.append(skip)
        all_arcs.append(arcs)
    add_each_job_once(model, skips, len(jobs))
    add_symmetry_breaking(model, skips, jobs, qualified)
    add_objective(model, jobs, s, rep)
    return model, s, all_arcs


def extract_routes(solver, all_arcs, n_jobs):
    """Routen je Träger aus den gesetzten Bögen (Kreis ab Depot)."""
    routes = []
    for arcs in all_arcs:
        succ = {a: b for (a, b), lit in arcs.items() if solver.Value(lit)}
        route, cur = [], succ.get(0)
        while cur not in (None, 0) and len(route) <= n_jobs:
            route.append(cur - 1)
            cur = succ.get(cur)
        routes.append(tuple(route))
    return tuple(routes)


def solve_hindsight(h, jobs, n_porters, qualified, time_limit=C.HINDSIGHT_TIME_LIMIT, workers=None) -> HindsightResult:
    from ortools.sat.python import cp_model

    model, s, all_arcs = build_model(h, jobs, n_porters, qualified)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit)
    solver.parameters.num_workers = workers or min(8, os.cpu_count() or 1)
    solver.parameters.random_seed = 1
    status = solver.Solve(model)
    name = solver.StatusName(status)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return HindsightResult(name, None, None, (), (), len(jobs))
    starts = tuple(int(solver.Value(v)) for v in s)
    return HindsightResult(name, float(solver.ObjectiveValue()), float(solver.BestObjectiveBound()), starts,
                           extract_routes(solver, all_arcs, len(jobs)), len(jobs))


def report_times(h, jobs, starts) -> list[int]:
    """Meldezeit je Job aus den Ankunftszeiten (Rückholungen: nach der Hinfahrt)."""
    return [job.rep if job.pred is None else starts[job.pred] + ride_minutes(h, jobs[job.pred]) + job.exam for job in jobs]


def verify_schedule(h, jobs, result: HindsightResult, qualified) -> list[str]:
    """Unabhängiger Prüfer: jede verletzte Regel als Text; leere Liste = Zeitplan ist zulässig und hat den gemeldeten Zielwert."""
    problems = []
    n = len(jobs)
    seen = sorted(j for route in result.routes for j in route)
    if seen != list(range(n)):
        problems.append("nicht jeder Job genau einmal gefahren")
        return problems
    rep = report_times(h, jobs, result.starts)
    T0 = h.T["leer"]
    for p, route in enumerate(result.routes):
        pos, free = h.depot, 0
        for j in route:
            job = jobs[j]
            if job.kind == "bett" and not qualified[p]:
                problems.append(f"Träger {p + 1} fährt ein Bett ohne Qualifikation (Job {j})")
            earliest = max(rep[j], free) + int(T0[pos, job.o])
            if result.starts[j] < earliest:
                problems.append(f"Job {j}: Ankunft {result.starts[j]} vor frühestmöglich {earliest}")
            pos, free = job.d, result.starts[j] + ride_minutes(h, job)
    if result.objective is not None:
        value = sum(C.CLASS_WEIGHT[job.prio] * (result.starts[j] - rep[j]) for j, job in enumerate(jobs))
        if abs(value - result.objective) > 1e-6:
            problems.append(f"Zielwert {result.objective} stimmt nicht mit der Nachrechnung {value} überein")
    return problems


def make_instance(h: Hospital, level: str, seed: int):
    """Kleine Spitzeninstanz: 3 Träger, kurzes Fenster, konstante Spitzendichte."""
    window, m = C.HINDSIGHT_LEVELS[level]
    return generate_orders(h, seed, m, window, profile=(C.PEAK_PROFILE_LEVEL,) * 12)


def online_weighted_wait(h, orders, n_porters, n_qualified, rule, batch_min=C.DEFAULT_BATCH) -> float:
    """Gewichtete Wartezeit einer Online-Regel auf denselben Aufträgen (ohne Pausen: das Fenster endet vor 11:30)."""
    sim = simulate(h, orders, n_porters, n_qualified, rule, batch_min, breaks=False)
    return float(sum(C.CLASS_WEIGHT[r.prio] * r.wait for r in sim.records))


def compare_rules(h, orders, n_porters, qual_percent, time_limit=C.HINDSIGHT_TIME_LIMIT, batch_min=C.DEFAULT_BATCH):
    """Schranke und alle Regeln auf einer Instanz. Gibt (HindsightResult, {Regel: gewichtete Wartezeit}, Jobs) zurück."""
    from ptd_simulation import qualified_flags

    nq = n_qualified_from_percent(n_porters, qual_percent)
    jobs = make_jobs(orders)
    res = solve_hindsight(h, jobs, n_porters, qualified_flags(n_porters, nq), time_limit)
    online = {r: online_weighted_wait(h, orders, n_porters, nq, r, batch_min) for r in C.RULES}
    return res, online, jobs
