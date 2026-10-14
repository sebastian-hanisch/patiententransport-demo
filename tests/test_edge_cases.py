"""Eckfälle: jeder Regler an seinen Grenzen, entartete Tage, Reihenfolge-Unabhängigkeit, Worst-Case am Maximum."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import ptd_constants as C
import ptd_evaluation as ev
from ptd_hospital import HOSPITAL as H
from ptd_simulation import n_qualified_from_percent, simulate

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("field,low,high", [
    ("rate", C.RATE_MIN, C.RATE_MAX), ("porters", C.PORTERS_MIN, C.PORTERS_MAX),
    ("qual", C.QUAL_MIN, C.QUAL_MAX), ("batch", C.BATCH_MIN, C.BATCH_MAX),
])
def test_every_slider_at_min_and_max(field, low, high):
    for value in (low, high):
        a = ev.analyse(ev.Settings(**{field: value}))
        assert set(a.stats) == set(C.RULES)
        assert all(s.n_orders == a.stats["fifo"].n_orders for s in a.stats.values())


def test_all_minima_and_all_maxima_together():
    lows = ev.Settings(C.RATE_MIN, C.PORTERS_MIN, C.QUAL_MIN, C.BATCH_MIN, "ohne Pausen", 0)
    highs = ev.Settings(C.RATE_MAX, C.PORTERS_MAX, C.QUAL_MAX, C.BATCH_MAX, "mit Pausen", C.SEED_MAX)
    for s in (lows, highs):
        a = ev.analyse(s)
        assert all(0.0 <= st.utilization <= 1.0 for st in a.stats.values())


def test_worst_case_at_the_slider_maximum_terminates_and_flags_incompleteness():
    # wenigste Träger bei höchster Dichte: die Last übersteigt die Kapazität; die Simulation endet an der Obergrenze, nichts hängt
    a = ev.analyse(ev.Settings(C.RATE_MAX, C.PORTERS_MIN, C.QUAL_MIN, C.DEFAULT_BATCH, "mit Pausen", 1))
    assert any(not s.complete for s in a.stats.values())
    for s in a.stats.values():
        assert s.classes[2].mean > C.SOLL[2]


def test_one_porter_one_qualified_and_no_orders():
    assert n_qualified_from_percent(1, 40) == 1 and n_qualified_from_percent(4, 40) == 2 and n_qualified_from_percent(8, 100) == 8
    sim = simulate(H, [], 1, 1, "fifo")
    assert sim.complete and sim.records == ()
    st = ev.rule_stat("fifo", sim)
    assert st.n_orders == 0 and st.empty_share == 0.0 and st.utilization == 0.0


def test_all_rules_leave_equal_orders_equal_in_the_count():
    a = ev.analyse(ev.Settings(seed=3))
    assert len({s.n_orders for s in a.stats.values()}) == 1


SNIPPET = (
    "import json, ptd_evaluation as ev\n"
    "a = ev.analyse(ev.Settings(seed=7))\n"
    "print(json.dumps({r: [round(c.mean, 9) for c in s.classes] + [round(s.utilization, 9)] for r, s in a.stats.items()}, sort_keys=True))\n"
)


def test_result_does_not_depend_on_the_hash_seed():
    outs = []
    for hash_seed in ("1", "2"):
        env = dict(os.environ, PYTHONHASHSEED=hash_seed, PYTHONPATH=str(ROOT))
        proc = subprocess.run([sys.executable, "-c", SNIPPET], capture_output=True, text=True, cwd=ROOT, env=env, timeout=120)
        assert proc.returncode == 0, proc.stderr
        outs.append(json.loads(proc.stdout))
    assert outs[0] == outs[1]
