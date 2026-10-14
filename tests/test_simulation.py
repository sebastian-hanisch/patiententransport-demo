"""Simulation: Handrechnung auf dem Mini-Haus, Pausen, Rückholung, Erhaltungssätze auf echten Tagen."""

import ptd_constants as C
from ptd_hospital import HOSPITAL as H
from ptd_orders import RETURN_OFFSET, generate_orders, rate_to_scale
from ptd_simulation import n_qualified_from_percent, simulate


def test_one_order_by_hand(mini, make_order):
    # Träger bei A, Auftrag von B nach C im Rollstuhl um 0: Anfahrt 3, Ankunft 3, Wartezeit 3,
    # Ende 3 + 2 + Rollstuhl(B,C) = 5 + 2 = 12
    sim = simulate(mini, [make_order(1, 0, 1, 2)], n_porters=1, n_qualified=1, rule="fifo", breaks=False)
    (rec,) = sim.records
    assert (rec.approach, rec.arrive, rec.wait, rec.transport, rec.finish) == (3, 3, 3, 5, 12)
    assert sim.complete and sim.busy_minutes == 12


def test_second_order_waits_for_the_only_porter(mini, make_order):
    orders = [make_order(1, 0, 1, 2), make_order(2, 1, 1, 2)]
    sim = simulate(mini, orders, 1, 1, "fifo", breaks=False)
    r1, r2 = sorted(sim.records, key=lambda r: r.oid)
    # Träger ist bei C, wenn er um 12 frei wird: Anfahrt C->B 4, Ankunft 16, Wartezeit 16 - 1 = 15
    assert (r1.finish, r2.arrive, r2.wait) == (12, 16, 15)


def test_return_is_reported_after_the_examination(mini, make_order):
    out = make_order(1, 0, o=1, d=2, exam=20, ret=True)        # Hinfahrt B -> C, Untersuchung 20 min
    sim = simulate(mini, [out], 1, 1, "fifo", breaks=False)
    first = next(r for r in sim.records if not r.is_return)
    back = next(r for r in sim.records if r.is_return)
    assert first.finish == 12 and back.oid == 1 + RETURN_OFFSET
    assert back.report == first.finish + 20 == 32
    assert back.arrive == 32 + 0                                # Träger steht noch in C, Abholort ist C
    assert back.wait == 0


def test_break_delays_an_order_that_comes_during_it(mini, make_order):
    # Träger geht um 330 in die Pause (30 min); Auftrag um 335 ab A wartet bis 360: Anfahrt 0, Wartezeit 25
    sim = simulate(mini, [make_order(1, 335, o=0, d=1)], 1, 1, "fifo", breaks=True)
    (rec,) = sim.records
    assert (rec.arrive, rec.wait) == (360, 25)
    off = simulate(mini, [make_order(1, 335, o=0, d=1)], 1, 1, "fifo", breaks=False)
    assert off.records[0].wait == 0


def test_bed_waits_for_the_only_qualified_porter(mini, make_order):
    # Träger 0 (qualifiziert) fährt gerade; Träger 1 ist frei, darf aber kein Bett fahren: das Bett wartet
    busy = make_order(1, 0, 1, 2, kind="rollstuhl")
    bed = make_order(2, 1, 0, 1, kind="bett")
    sim = simulate(mini, [busy, bed], n_porters=2, n_qualified=1, rule="fifo", breaks=False)
    r_bed = next(r for r in sim.records if r.oid == 2)
    assert r_bed.porter == 0 and r_bed.arrive > 12


def test_no_orders_gives_an_empty_result(mini):
    sim = simulate(mini, [], 3, 2, "voraus", breaks=True)
    assert sim.records == () and sim.complete and sim.busy_minutes == 0


def test_unfinished_orders_are_counted_with_the_censored_wait(mini, make_order, monkeypatch):
    monkeypatch.setattr(C, "SIM_LIMIT", 10)
    orders = [make_order(i, 0, 1, 2) for i in range(5)]
    sim = simulate(mini, orders, 1, 1, "fifo", breaks=False)
    assert not sim.complete and len(sim.records) == 5
    censored = [r for r in sim.records if r.porter == -1]
    assert censored and all(r.wait == 10 for r in censored)


def test_conservation_and_no_double_booking_on_real_days():
    for seed in (3, 4, 5):
        orders = generate_orders(H, seed, rate_to_scale(22))
        nq = n_qualified_from_percent(6, 70)
        for rule in C.RULES:
            sim = simulate(H, orders, 6, nq, rule, breaks=True)
            assert sim.complete
            outbound = [r for r in sim.records if not r.is_return]
            assert sorted(r.oid for r in outbound) == [o.oid for o in orders], (seed, rule)
            returns = {r.oid - RETURN_OFFSET for r in sim.records if r.is_return}
            assert returns == {o.oid for o in orders if o.ret}, (seed, rule)
            by_porter = {}
            for r in sim.records:
                start = r.arrive - r.approach
                assert start >= r.report and r.wait == r.arrive - r.report >= 0
                by_porter.setdefault(r.porter, []).append((start, r.finish))
            for p, spans in by_porter.items():
                spans.sort()
                assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:])), (seed, rule, p)
            assert all(r.porter < 6 for r in sim.records)
