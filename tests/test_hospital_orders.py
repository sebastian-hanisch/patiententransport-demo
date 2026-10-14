"""Haus und Aufträge: Wegzeiten gegen Handrechnung und Ordnung der Tempi; Aufträge deterministisch und gültig."""

import numpy as np

import ptd_constants as C
from ptd_hospital import HOSPITAL as H
from ptd_orders import RETURN_OFFSET, Order, generate_orders, make_return, rate_to_scale


def test_travel_times_against_hand_calculation():
    # Aufnahme -> Radiologie: 40 m / 85 = 0,47 + Aufzug 1,2 + 0,3 * 1 = 1,97 -> 2 min
    assert H.T["leer"][H.index("Aufnahme"), H.index("Radiologie")] == 2
    # Aufnahme -> Station 1: 150 m / 85 = 1,76 + Aufzug 1,2 + 0,6 + Gebäudewechsel 1,5 = 5,06 -> 6 min
    assert H.T["leer"][H.index("Aufnahme"), H.index("Station 1")] == 6
    # gleiche Etage und gleiches Gebäude: Radiologie -> MRT 30 m / 85 = 0,35 -> mindestens 1 min
    assert H.T["leer"][H.index("Radiologie"), H.index("MRT")] == 1


def test_matrices_are_symmetric_with_zero_diagonal_and_ordered_by_speed():
    for kind, T in H.T.items():
        assert (T == T.T).all(), kind
        assert (np.diag(T) == 0).all()
        off = T[~np.eye(len(T), dtype=bool)]
        assert (off >= 1).all()
    assert (H.T["gehend"] >= H.T["bett"]).all() and (H.T["bett"] >= H.T["rollstuhl"]).all() and (H.T["rollstuhl"] >= H.T["leer"]).all()


def test_rate_to_scale_inverts_the_base_rate():
    assert rate_to_scale(C.BASE_RATE * float(np.mean(C.PROFILE))) == 1.0


def test_orders_are_deterministic_and_valid():
    a = generate_orders(H, 7, rate_to_scale(20))
    b = generate_orders(H, 7, rate_to_scale(20))
    assert a == b and len(a) > 100
    assert [o.oid for o in a] == list(range(len(a)))
    assert all(0 <= o.t < C.DAY_MINUTES for o in a)
    assert all(o.o != o.d for o in a)
    assert all(o.kind in C.KINDS and o.prio in (0, 1, 2) for o in a)
    assert generate_orders(H, 8, rate_to_scale(20)) != a


def test_returns_only_follow_a_trip_to_the_diagnostics_and_beds_stay_beds():
    for o in generate_orders(H, 11, rate_to_scale(26)):
        if o.ret:
            assert o.d in H.diagnostics and o.exam >= 1
        else:
            assert o.exam == 0


def test_make_return_reverses_the_trip_and_waits_for_the_examination():
    o = Order(5, 100, 8, 1, "gehend", 2, exam=25, ret=True, ret_prio=1)
    back = make_return(o, finish=130)
    assert (back.o, back.d, back.t) == (1, 8, 155)
    assert back.kind == "rollstuhl" and back.prio == 1 and back.is_return and not back.ret
    assert back.oid == 5 + RETURN_OFFSET
    assert make_return(Order(6, 0, 8, 3, "bett", 2, exam=10, ret=True), 20).kind == "bett"


def test_the_mix_is_roughly_the_documented_one():
    orders = [o for seed in range(30) for o in generate_orders(H, seed, rate_to_scale(20))]
    n = len(orders)
    share = lambda f: sum(1 for o in orders if f(o)) / n  # noqa: E731
    assert 0.50 < share(lambda o: o.ret) < 0.60
    assert 0.01 < share(lambda o: o.prio == 0) < 0.04
    assert 0.70 < share(lambda o: o.prio == 2) < 0.85
