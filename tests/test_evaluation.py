"""Kennzahlen und Verdikte: reine Funktionen an handgesetzten Werten; jede Zahl im Text wird geprüft."""

import ptd_constants as C
import ptd_evaluation as ev
from ptd_simulation import Record, SimResult


def rec(prio, wait, approach=3, transport=5, report=0, oid=0, is_return=False, day_t=None):
    return Record(oid, prio, "rollstuhl", is_return, report, report + wait, wait, 0, approach, transport, report + wait + 9,
                  report if day_t is None else day_t)


def test_class_stat_by_hand():
    records = [rec(0, 4), rec(0, 12), rec(0, 8), rec(1, 25), rec(2, 30)]
    st = ev.class_stat(records, 0)
    assert (st.n, st.mean) == (3, 8.0)
    assert st.miss == 1 / 3                       # nur 12 > 10
    assert ev.class_stat(records, 1).miss == 1.0  # 25 > 20
    assert ev.class_stat(records, 2).miss == 0.0  # 30 <= 40
    empty = ev.class_stat(records, 0.5) if False else ev.class_stat([], 0)
    assert (empty.n, empty.mean, empty.p90, empty.miss) == (0, 0.0, 0.0, 0.0)


def test_rule_stat_counts_trips_whose_outbound_leg_was_reported_before_the_end_of_the_day():
    # zweite Fahrt: Rückholung, gemeldet nach 18:00, aber die Hinfahrt war um 17:50: zählt; dritte: Hinfahrt nach 18:00: zählt nicht
    recs = (rec(2, 10, report=100), rec(2, 20, report=C.DAY_MINUTES + 5, oid=1, is_return=True, day_t=C.DAY_MINUTES - 10),
            rec(2, 99, report=C.DAY_MINUTES + 5, oid=2))
    sim = SimResult(recs, ((0, 0),), busy_minutes=90.0, n_porters=2, complete=True)
    st = ev.rule_stat("fifo", sim)
    assert st.n_orders == 2 and st.classes[2].mean == 15.0
    assert st.utilization == 90.0 / (2 * C.DAY_MINUTES)
    assert st.empty_share == 3 / (3 + 5)
    assert st.weighted_wait == C.CLASS_WEIGHT[2] * 30


def test_queue_grid_holds_the_last_value():
    sim = SimResult((), ((0, 0), (7, 3), (12, 1)), 0.0, 1, True)
    grid = ev.queue_grid(sim, step=5, end=15)
    assert grid == (0, 0, 3, 1)                    # Minuten 0, 5, 10, 15


def make_analysis(fifo_n, prio_n, voraus_n, fifo_r, prio_r, voraus_r, util=0.86):
    def stat(n, r, rule):
        classes = (ev.ClassStat(8, n, n * 1.5, 0.0), ev.ClassStat(60, 5.0, 8.0, 0.0), ev.ClassStat(200, r, r * 2, 0.0))
        return ev.RuleStat(rule, classes, util, 0.3, 0.0, 268, True)

    stats = {r: stat(5.0, 6.0, r) for r in C.RULES}
    stats["fifo"], stats["prio"], stats["voraus"] = stat(fifo_n, fifo_r, "fifo"), stat(prio_n, prio_r, "prio"), stat(voraus_n, voraus_r, "voraus")
    return ev.Analysis(ev.Settings(), 240, stats, {}, C.CLASS_WEIGHT)


def test_verdict_core_all_four_branches_and_their_numbers():
    kind, text = ev.verdict_core(make_analysis(5.2, 5.0, 5.1, 4.0, 4.5, 4.1, util=0.5))
    assert kind == "info" and "50 %" in text and "5,0 bis 5,2 min" in text and "Routine 4,0 min" in text

    kind, text = ev.verdict_core(make_analysis(24.7, 6.4, 5.9, 25.5, 33.3, 9.3))
    assert kind == "success"
    for needle in ("24,7 min", "25,5 min", "6,4 min", "33,3 min", "5,9 min", "9,3 min"):
        assert needle in text

    kind, text = ev.verdict_core(make_analysis(24.7, 6.4, 5.9, 25.5, 33.3, 48.6))
    assert kind == "warning" and "48,6 min" in text and "33,3 min" in text

    kind, text = ev.verdict_core(make_analysis(85.0, 14.0, 12.0, 85.0, 109.0, 48.0))
    assert kind == "warning" and "Kapazität" in text and "14,0 min" in text and "85,0 min" in text

    kind, text = ev.verdict_core(make_analysis(8.0, 6.0, 6.5, 8.0, 9.0, 9.5, util=0.7))
    assert kind == "info" and "8,0 min unter FIFO" in text and "6,0 min unter Priorität" in text


def test_verdict_sweep_names_the_first_density_over_the_soll():
    rows = [{"rate": r, **{rule: {"wait": (w, 5.0, 8.0), "miss": (0.0, 0.0, 0.0), "util": 0.5 + r / 100, "empty": 0.3} for rule in C.RULES}}
            for r, w in ((12, 4.0), (16, 7.5), (20, 24.7))]
    kind, text = ev.verdict_sweep(rows)
    assert kind == "warning" and "ab 20 neuen Aufträgen" in text and "24,7 min" in text and "70 %" in text
    calm = [dict(r, **{"fifo": dict(r["fifo"], wait=(4.0, 5.0, 8.0))}) for r in rows]
    kind, text = ev.verdict_sweep(calm)
    assert kind == "info" and "bis 20 neue Aufträge" in text.replace("Bis 20", "bis 20")


def test_first_rate_above_returns_none_when_never_exceeded():
    rows = [{"rate": 12, "fifo": {"wait": (3.0, 3.0, 3.0)}}]
    assert ev.first_rate_above(rows, "fifo", 0, 10) is None
    assert ev.first_rate_above(rows, "fifo", 0, 2)["rate"] == 12


def test_formatting_uses_decimal_commas():
    assert ev.fmt(24.66) == "24,7" and ev.pct(0.861) == "86 %" and ev.fmt(7.0, 0) == "7"


def test_analysis_is_deterministic_and_covers_every_rule():
    s = ev.Settings(seed=5)
    a, b = ev.analyse(s), ev.analyse(s)
    assert a == b and set(a.stats) == set(C.RULES) and set(a.queues) == set(C.RULES)
    assert all(st.complete for st in a.stats.values())
    assert len({st.n_orders for st in a.stats.values()}) == 1       # alle Regeln fahren dieselben Aufträge


def test_sweep_uses_the_fixed_days_and_returns_one_row_per_density():
    rows = ev.sweep_rate(ev.Settings(), rates=(12, 24), seeds=C.SWEEP_SEEDS[:2], rules=("fifo", "prio"))
    assert [r["rate"] for r in rows] == [12, 24]
    for r in rows:
        assert set(r) == {"rate", "fifo", "prio"}
        assert len(r["fifo"]["wait"]) == 3 and 0 <= r["fifo"]["util"] <= 1
    assert rows[1]["fifo"]["wait"][0] >= rows[0]["fifo"]["wait"][0]   # dichter -> Notfall wartet nicht kürzer
