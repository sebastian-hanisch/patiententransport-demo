"""Orakel: Ereignissimulation gegen die minutengetaktete Referenz mit eigenen, naiven Regelschleifen (tests/reference_sim.py).

Kleine Tage (2 bis 3 Träger, kurzes Fenster), damit die Aufzählung der Zuordnungen in der Referenz schnell bleibt. Verglichen wird
je Auftrag Wartezeit und Träger, nicht nur eine Summe."""

import itertools

import numpy as np
import pytest
from reference_sim import _min_assignment, reference_simulate

import ptd_constants as C
import ptd_dispatch as D
from ptd_hospital import HOSPITAL as H
from ptd_orders import generate_orders, make_return, rate_to_scale
from ptd_simulation import simulate

SEEDS = range(12)


def _small_day(seed, scale=0.25, window=150):
    return generate_orders(H, seed, scale, window)


@pytest.mark.parametrize("rule", C.RULES)
def test_event_simulation_matches_the_minute_by_minute_reference(rule):
    mismatches = []
    for seed in SEEDS:
        orders = _small_day(seed)
        ref = reference_simulate(H.T, H.depot, orders, 3, 2, rule, batch_min=5, breaks=False)
        got = simulate(H, orders, 3, 2, rule, 5, breaks=False)
        mine = {r.oid: (r.wait, r.porter) for r in got.records}
        if mine != ref:
            mismatches.append(seed)
    assert not mismatches, (rule, mismatches)


def test_breaks_are_part_of_the_comparison():
    orders = generate_orders(H, 5, rate_to_scale(14), 480)          # Fenster reicht über 11:30
    for rule in ("fifo", "prio"):
        ref = reference_simulate(H.T, H.depot, orders, 3, 2, rule, breaks=True)
        got = simulate(H, orders, 3, 2, rule, 5, breaks=True)
        assert {r.oid: (r.wait, r.porter) for r in got.records} == ref


def test_hungarian_cost_is_minimal_against_enumeration():
    rng = np.random.default_rng(3)
    for _ in range(60):
        n_o, n_p = int(rng.integers(1, 5)), int(rng.integers(1, 5))
        T0 = np.array([[0, 3, 5], [3, 0, 4], [5, 4, 0]])
        orders = [type("O", (), dict(o=int(rng.integers(0, 3)), t=int(rng.integers(0, 20)), prio=int(rng.integers(0, 3)),
                                     kind="rollstuhl", oid=i))() for i in range(n_o)]
        pos = [int(rng.integers(0, 3)) for _ in range(n_p)]
        free_at = [int(rng.integers(0, 6)) for _ in range(n_p)]
        t = 10
        cands = list(range(n_p))
        pairs = D.hungarian_pairs(t, orders, cands, set(cands), pos, free_at, [True] * n_p, T0)

        def cost(o, p):
            return max(free_at[p] - t, 0) + T0[pos[p], o.o] - C.CLASS_WEIGHT[o.prio] * (t - o.t) + D.tie_break(o.oid, p)

        matrix = [[cost(o, p) for p in cands] for o in orders]
        best = sum(matrix[r][c] for r, c in _min_assignment(matrix))
        # nur Paare mit jetzt freiem Träger werden bestätigt; hier sind alle Träger Kandidaten und frei gemeldet
        assert sum(cost(o, p) for p, o in pairs) == pytest.approx(best)
        assert len(pairs) == min(n_o, n_p)


def test_reference_enumeration_itself_on_a_hand_example():
    # zwei Aufträge, zwei Träger: Kosten [[1, 4], [3, 2]] -> beste Zuordnung 0->0, 1->1 mit 3
    assert sorted(_min_assignment([[1, 4], [3, 2]])) == [(0, 0), (1, 1)]
    assert itertools is not None


def test_return_reporting_matches_the_documented_rule():
    # Rückholung erst nach der Fahrt plus Untersuchung: Meldung = Ende + Dauer
    orders = _small_day(2)
    got = simulate(H, orders, 3, 2, "fifo", 5, breaks=False)
    finish = {r.oid: r.finish for r in got.records if not r.is_return}
    for r in got.records:
        if r.is_return:
            parent = next(o for o in orders if o.oid == r.oid - 1_000_000)
            assert r.report == make_return(parent, finish[parent.oid]).t
