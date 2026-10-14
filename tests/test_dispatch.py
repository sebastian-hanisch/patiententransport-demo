"""Zuweisungsregeln einzeln an der Mini-Instanz (conftest.mini), Ergebnis von Hand gerechnet."""

import ptd_constants as C
import ptd_dispatch as D


def pairs_by_id(pairs):
    return sorted((p, o.oid) for p, o in pairs)


def test_nearest_idle_porter_wins(mini, make_order):
    T0 = mini.T["leer"]
    order = make_order(1, 0, o=1, d=2)               # Abholort B
    # Träger 0 steht bei A (Anfahrt 3), Träger 1 bei C (Anfahrt 4)
    assert D.nearest_compatible_idle(order, [0, 1], pos=[0, 2], qualified=[True, True], T0=T0) == 0


def test_beds_need_a_qualified_porter(mini, make_order):
    T0 = mini.T["leer"]
    bed = make_order(1, 0, o=1, d=2, kind="bett")
    assert D.nearest_compatible_idle(bed, [0, 1], pos=[0, 2], qualified=[False, True], T0=T0) == 1
    assert D.nearest_compatible_idle(bed, [0], pos=[0], qualified=[False], T0=T0) is None
    chair = make_order(2, 0, o=1, d=2, kind="rollstuhl")
    assert D.nearest_compatible_idle(chair, [0, 1], pos=[0, 2], qualified=[False, True], T0=T0) == 0


def test_fifo_prio_and_frist_pick_different_orders(mini, make_order):
    T0 = mini.T["leer"]
    old_routine = make_order(1, 0, 1, 2, prio=2)       # Frist 0 + 40 = 40
    old_urgent = make_order(2, 0, 1, 2, prio=1)        # Frist 0 + 20 = 20
    late_emergency = make_order(3, 15, 1, 2, prio=0)   # Frist 15 + 10 = 25
    waiting = [old_routine, old_urgent, late_emergency]
    kw = dict(t=20, idle=[0], pos=[0], free_at=[0], qualified=[True], T0=T0)
    assert pairs_by_id(D.choose("fifo", waiting=waiting, **kw)) == [(0, 1)]    # ältester, bei Gleichstand erster in der Liste
    assert pairs_by_id(D.choose("prio", waiting=waiting, **kw)) == [(0, 3)]    # Notfall zuerst
    assert pairs_by_id(D.choose("frist", waiting=waiting, **kw)) == [(0, 2)]   # früheste Frist: 20


def test_nearest_pair_rule_is_greedy_over_all_pairs(mini, make_order):
    T0 = mini.T["leer"]
    from_b = make_order(1, 0, o=1, d=0)
    from_c = make_order(2, 0, o=2, d=0)
    # Träger 0 bei A, Träger 1 bei C: Paar (1, from_c) kostet 0, danach (0, from_b) 3
    pairs = D.choose("nahe", t=5, waiting=[from_b, from_c], idle=[0, 1], pos=[0, 2], free_at=[0, 0], qualified=[True, True], T0=T0)
    assert pairs_by_id(pairs) == [(0, 1), (1, 2)]


def test_batch_only_assigns_on_the_tick_but_emergencies_at_once(mini, make_order):
    T0 = mini.T["leer"]
    routine = make_order(1, 0, 1, 2, prio=2)
    emergency = make_order(2, 3, 1, 2, prio=0)
    kw = dict(idle=[0, 1], pos=[0, 0], free_at=[0, 0], qualified=[True, True], T0=T0, batch_min=5)
    off_tick = D.choose("batch", t=7, waiting=[routine, emergency], **kw)
    assert pairs_by_id(off_tick) == [(0, 2)]                                   # nur der Notfall
    on_tick = D.choose("batch", t=10, waiting=[routine, emergency], **kw)
    assert sorted(o.oid for _, o in on_tick) == [1, 2] and len({p for p, _ in on_tick}) == 2


def test_lookahead_keeps_an_order_for_a_porter_who_frees_up_next_door(mini, make_order):
    T0 = mini.T["leer"]
    order = make_order(1, 0, o=1, d=2)                 # Abholort B
    # Träger 0 ist frei bei C (Anfahrt 4); Träger 1 wird in 1 min bei B frei (Kosten 1 + 0)
    kw = dict(t=10, waiting=[order], pos=[2, 1], free_at=[0, 11], qualified=[True, True], T0=T0, idle=[0])
    assert D.choose("fifo", **kw) == [(0, order)]
    assert D.choose("voraus", **kw) == []              # wartet auf Träger 1, schickt Träger 0 nicht los
    # Ohne den nahen, bald freien Träger fährt Träger 0 sofort
    kw2 = dict(kw, free_at=[0, 40])
    assert D.choose("voraus", **kw2) == [(0, order)]


def test_emergency_goes_first_under_lookahead_too(mini, make_order):
    T0 = mini.T["leer"]
    emergency = make_order(1, 0, o=1, d=2, prio=0)
    kw = dict(t=3, waiting=[emergency], pos=[2, 1], free_at=[0, 4], qualified=[True, True], T0=T0, idle=[0])
    assert D.choose("voraus", **kw) == [(0, emergency)]


def test_no_porter_or_order_twice_for_every_rule(mini, make_order):
    T0 = mini.T["leer"]
    waiting = [make_order(i, i, o=i % 3, d=(i + 1) % 3, kind=C.KINDS[i % 3], prio=i % 3) for i in range(8)]
    for rule in C.RULES:
        pairs = D.choose(rule, t=10, waiting=waiting, idle=[0, 1, 2], pos=[0, 1, 2], free_at=[0, 0, 0], qualified=[True, False, True], T0=T0)
        assert len({p for p, _ in pairs}) == len(pairs) and len({o.oid for _, o in pairs}) == len(pairs), rule
        assert all(D.compatible(o, p, [True, False, True]) for p, o in pairs), rule
