"""Jede Zahl aus README.md, nachgerechnet über dieselben Auswertungsfunktionen wie die App (Median über SWEEP_SEEDS)."""

import pytest

import ptd_constants as C
import ptd_evaluation as ev


@pytest.fixture(scope="module")
def sweep8():
    return {r["rate"]: r for r in ev.sweep_rate(ev.Settings())}


@pytest.fixture(scope="module")
def sweep12():
    return {r["rate"]: r for r in ev.sweep_rate(ev.Settings(porters=12), rates=(30,))}


def w(row, rule, cls):
    return round(row[rule]["wait"][cls], 1)


def miss(row, rule, cls):
    return round(100 * row[rule]["miss"][cls])


def test_quiet_day_all_rules_are_equal(sweep8):
    r = sweep8[12]
    assert round(100 * r["fifo"]["util"]) == 47
    waits = [r[rule]["wait"][c] for rule in C.RULES for c in range(3)]
    assert round(min(waits), 1) == 2.8 and round(max(waits), 1) == 5.1
    assert all(r[rule]["miss"][c] == 0.0 for rule in C.RULES for c in range(3))


def test_fifo_tips_between_70_and_85_percent(sweep8):
    r16, r20 = sweep8[16], sweep8[20]
    assert round(100 * r16["fifo"]["util"]) == 67 and w(r16, "fifo", 0) == 7.5 and miss(r16, "fifo", 0) == 8
    assert round(100 * r20["fifo"]["util"]) == 86
    assert w(r20, "fifo", 0) == 24.7 and miss(r20, "fifo", 0) == 76
    assert w(r20, "fifo", 2) == 24.5       # der Notfall wartet so lange wie Routine


def test_priority_moves_the_load_to_routine(sweep8):
    r = sweep8[20]
    assert w(r, "prio", 0) == 6.4 and miss(r, "prio", 0) == 0
    assert w(r, "prio", 2) == 32.0 and miss(r, "prio", 2) == 32      # Routine wartet länger als unter FIFO (24,5)
    assert w(r, "prio", 2) > w(r, "fifo", 2)


def test_lookahead_keeps_all_classes_near_the_soll_by_saving_empty_trips(sweep8):
    r = sweep8[20]
    assert (w(r, "voraus", 0), w(r, "voraus", 1), w(r, "voraus", 2)) == (5.9, 7.4, 9.1)
    assert miss(r, "voraus", 1) == 4 and miss(r, "voraus", 2) == 1
    assert round(100 * r["voraus"]["empty"]) == 29 and round(100 * r["fifo"]["empty"]) == 39
    assert round(100 * r["voraus"]["util"]) == 78 and round(100 * r["fifo"]["util"]) == 86


def test_batching_window_hurts(sweep8):
    r = sweep8[20]
    assert w(r, "batch", 2) == 41.2 and miss(r, "batch", 2) == 53
    assert w(r, "batch", 1) == 18.1 and miss(r, "batch", 1) == 42
    assert round(100 * r["batch"]["util"]) == 76


def test_nearest_order_starves_the_emergency_under_load(sweep8):
    r = sweep8[24]
    assert w(r, "nahe", 0) == 130.1 and w(r, "fifo", 0) == 85.3
    assert w(r, "nahe", 2) == 20.4 and w(r, "fifo", 2) == 83.0


def test_no_rule_holds_the_soll_at_the_capacity_limit(sweep8):
    r = sweep8[28]
    assert round(100 * r["fifo"]["util"]) == 90
    assert w(r, "voraus", 2) == 92.7 and miss(r, "voraus", 2) == 80


def test_the_pattern_holds_with_twelve_porters_at_the_same_utilization(sweep12):
    r = sweep12[30]
    assert round(100 * r["fifo"]["util"]) == 88
    assert w(r, "fifo", 0) == 31.0
    assert w(r, "prio", 2) == 40.2 and w(r, "voraus", 2) == 9.4


def test_first_density_over_the_soll_is_twenty(sweep8):
    rows = [sweep8[k] for k in sorted(sweep8)]
    assert ev.first_rate_above(rows, "fifo", 0, C.SOLL[0])["rate"] == 20


def test_the_order_mix_and_the_number_of_emergencies_per_day():
    from ptd_hospital import HOSPITAL
    from ptd_orders import generate_orders, rate_to_scale

    days = [generate_orders(HOSPITAL, s, rate_to_scale(C.DEFAULT_RATE)) for s in C.SWEEP_SEEDS]
    flat = [o for d in days for o in d]
    share = lambda p: round(100 * sum(1 for o in flat if o.prio == p) / len(flat))  # noqa: E731
    assert (share(0), share(1), share(2)) == (2, 26, 72)
    per_day = [sum(1 for o in d if o.prio == 0) for d in days]
    assert (min(per_day), max(per_day)) == (2, 9)
    assert round(sum(per_day) / len(days), 1) == 5.4
    assert round(len(flat) / len(days)) == 238


def test_nearest_order_is_the_best_rule_for_routine_at_the_standard_density(sweep8):
    r = sweep8[20]
    assert w(r, "nahe", 2) == 7.7
    assert w(r, "nahe", 2) < w(r, "voraus", 2)


def test_hindsight_price_of_ignorance_on_the_provable_instances():
    pytest.importorskip("ortools")
    import ptd_hindsight as HS
    from ptd_hospital import HOSPITAL
    from ptd_simulation import n_qualified_from_percent, qualified_flags

    nq = n_qualified_from_percent(C.HINDSIGHT_PORTERS, C.DEFAULT_QUAL)
    qualified = qualified_flags(C.HINDSIGHT_PORTERS, nq)
    n_all = n_small = 0
    sizes, opt_sum = [], 0.0
    online_sum = {r: 0.0 for r in C.RULES}
    at_opt = {r: 0 for r in C.RULES}
    for level in C.HINDSIGHT_LEVELS:
        for seed in C.HINDSIGHT_SEEDS:
            orders = HS.make_instance(HOSPITAL, level, seed)
            jobs = HS.make_jobs(orders)
            n_all += 1
            if not 0 < len(jobs) <= 16:
                continue
            res = HS.solve_hindsight(HOSPITAL, jobs, C.HINDSIGHT_PORTERS, qualified, time_limit=60, workers=4)
            assert res.status == "OPTIMAL", (level, seed, len(jobs))
            assert HS.verify_schedule(HOSPITAL, jobs, res, qualified) == []
            n_small += 1
            sizes.append(len(jobs))
            opt_sum += res.objective
            for r in C.RULES:
                cost = HS.online_weighted_wait(HOSPITAL, orders, C.HINDSIGHT_PORTERS, nq, r)
                assert cost >= res.objective - 1e-9, (level, seed, r)
                online_sum[r] += cost
                at_opt[r] += abs(cost - res.objective) < 1e-9
    assert n_all == 36 and n_small == 23
    assert round(sum(sizes) / len(sizes), 1) == 11.3
    ratio = {r: round(online_sum[r] / opt_sum, 2) for r in C.RULES}
    assert ratio == {"fifo": 1.19, "nahe": 1.13, "prio": 1.16, "frist": 1.16, "batch": 1.58, "voraus": 1.12}
    assert at_opt == {"fifo": 2, "nahe": 2, "prio": 2, "frist": 2, "batch": 0, "voraus": 3}
