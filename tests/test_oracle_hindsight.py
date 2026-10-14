"""Orakel: die CP-SAT-Schranke gegen vollständige Aufzählung aller Zuordnungen und Reihenfolgen auf Mini-Instanzen.

Das Orakel rechnet früheste Startzeiten je Reihenfolge (Fixpunkt über Träger- und Rückhol-Vorgänger), ohne CP-SAT. Dazu: Handbeispiel,
Prüfer erkennt verletzte Zeitpläne, keine Online-Regel schlägt das bewiesene Optimum."""

import itertools

import pytest

pytest.importorskip("ortools")

import ptd_constants as C  # noqa: E402
import ptd_hindsight as HS  # noqa: E402
from ptd_hospital import HOSPITAL as H  # noqa: E402
from ptd_orders import generate_orders  # noqa: E402
from ptd_simulation import n_qualified_from_percent, qualified_flags  # noqa: E402


def brute_force(h, jobs, n_porters, qualified):
    n = len(jobs)
    T0 = h.T["leer"]
    best = None
    for assign in itertools.product(range(n_porters), repeat=n):
        if any(jobs[j].kind == "bett" and not qualified[assign[j]] for j in range(n)):
            continue
        groups = [[j for j in range(n) if assign[j] == p] for p in range(n_porters)]
        for perms in itertools.product(*[itertools.permutations(g) for g in groups]):
            s = [None] * n
            for _ in range(n + 1):
                changed = False
                for seq in perms:
                    prev, pos = None, h.depot
                    for j in seq:
                        job = jobs[j]
                        if job.pred is None:
                            rep = job.rep
                        elif s[job.pred] is None:
                            break
                        else:
                            rep = s[job.pred] + HS.ride_minutes(h, jobs[job.pred]) + job.exam
                        if prev is not None and s[prev] is None:
                            break
                        free = 0 if prev is None else s[prev] + HS.ride_minutes(h, jobs[prev])
                        val = max(rep, free) + int(T0[pos, job.o])
                        if s[j] != val:
                            s[j], changed = val, True
                        prev, pos = j, job.d
                if not changed:
                    break
            if any(v is None for v in s):
                continue
            cost = 0
            for j, job in enumerate(jobs):
                rep = job.rep if job.pred is None else s[job.pred] + HS.ride_minutes(h, jobs[job.pred]) + job.exam
                cost += C.CLASS_WEIGHT[job.prio] * (s[j] - rep)
            best = cost if best is None else min(best, cost)
    return best


def mini_jobs(seed):
    orders = generate_orders(H, 500 + seed, 0.12, 40)[:3]
    jobs = HS.make_jobs(orders)[:5]
    return [j for j in jobs if j.pred is None or j.pred < len(jobs)]


def test_hand_example_two_orders_one_porter(mini, make_order):
    # Träger bei A. o1: B -> C (t 0), o2: C -> B (t 0), beide Routine (Gewicht 1).
    # o1 zuerst: Ankunft 3 (Wartezeit 3), Ende 3 + 2 + 5 + 2 = 12 bei C; o2: Ankunft 12 (Wartezeit 12): Summe 15.
    # o2 zuerst: Ankunft 5, Ende 5 + 4 + 5 = 14 bei B; o1: Ankunft 14: Summe 5 + 14 = 19.
    orders = [make_order(1, 0, 1, 2), make_order(2, 0, 2, 1)]
    jobs = HS.make_jobs(orders)
    res = HS.solve_hindsight(mini, jobs, 1, [True], time_limit=10, workers=2)
    assert res.status == "OPTIMAL" and res.objective == 15 and res.bound == 15
    assert res.routes == ((0, 1),) and HS.verify_schedule(mini, jobs, res, [True]) == []
    assert brute_force(mini, jobs, 1, [True]) == 15


def test_cp_sat_equals_enumeration_on_mini_instances():
    qualified = [True, False]
    checked = 0
    for seed in range(45):
        jobs = mini_jobs(seed)
        if len(jobs) < 2:
            continue
        expected = brute_force(H, jobs, 2, qualified)
        res = HS.solve_hindsight(H, jobs, 2, qualified, time_limit=20, workers=4)
        assert res.status == "OPTIMAL", seed
        assert res.objective == pytest.approx(expected), (seed, len(jobs))
        assert HS.verify_schedule(H, jobs, res, qualified) == [], seed
        checked += 1
    assert checked >= 15


def test_no_online_rule_beats_the_proven_optimum():
    nq = n_qualified_from_percent(3, 85)
    for seed in range(6):
        orders = HS.make_instance(H, "locker (60 min, m 0,15)", 2000 + seed)
        jobs = HS.make_jobs(orders)
        if not 2 <= len(jobs) <= 14:
            continue
        res = HS.solve_hindsight(H, jobs, 3, qualified_flags(3, nq), time_limit=20, workers=4)
        if res.status != "OPTIMAL":
            continue
        for rule in C.RULES:
            assert HS.online_weighted_wait(H, orders, 3, nq, rule) >= res.objective - 1e-9, (seed, rule)


def test_verifier_catches_corrupted_schedules():
    qualified = [True, True, False]
    orders = HS.make_instance(H, "locker (60 min, m 0,15)", 2001)
    jobs = HS.make_jobs(orders)
    res = HS.solve_hindsight(H, jobs, 3, qualified, time_limit=20, workers=4)
    assert HS.verify_schedule(H, jobs, res, qualified) == []
    j = next(i for i, job in enumerate(jobs) if job.pred is None)
    early = list(res.starts)
    early[j] = jobs[j].rep - 1                                    # vor der Meldung angekommen
    bad = HS.HindsightResult(res.status, res.objective, res.bound, tuple(early), res.routes, res.n_jobs)
    assert any("vor frühestmöglich" in p for p in HS.verify_schedule(H, jobs, bad, qualified))
    missing = HS.HindsightResult(res.status, res.objective, res.bound, res.starts,
                                 tuple(route[:-1] for route in res.routes), res.n_jobs)
    assert HS.verify_schedule(H, jobs, missing, qualified)
    lie = HS.HindsightResult(res.status, res.objective + 5, res.bound, res.starts, res.routes, res.n_jobs)
    assert any("Zielwert" in p for p in HS.verify_schedule(H, jobs, lie, qualified))
