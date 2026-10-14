"""Gemeinsame Fixtures: das Mini-Haus, an dem jede Einheit von Hand geprüft wird (DEMO-PLAYBOOK §1b)."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ptd_hospital import Hospital  # noqa: E402
from ptd_orders import Order  # noqa: E402


@pytest.fixture
def mini():
    """Drei Orte A (Depot, Index 0), B, C. Handgesetzte Wegzeiten (Minuten):

    leer:      A-B 3, A-C 5, B-C 4          Rollstuhl: A-B 4, A-C 6, B-C 5
    Bett:      A-B 5, A-C 7, B-C 6          gehend:    A-B 6, A-C 8, B-C 7
    """
    def sym(ab, ac, bc):
        return np.array([[0, ab, ac], [ab, 0, bc], [ac, bc, 0]], dtype=int)

    return Hospital(
        names=("A", "B", "C"), building=(0, 0, 0), floor=(0, 0, 0), x=(0, 10, 20), y=(0, 0, 0),
        T={"leer": sym(3, 5, 4), "rollstuhl": sym(4, 6, 5), "bett": sym(5, 7, 6), "gehend": sym(6, 8, 7)},
        depot=0, stations=(1, 2), diagnostics=(1, 2), exam={1: 20, 2: 30},
    )


@pytest.fixture
def make_order():
    def _make(oid, t, o, d, kind="rollstuhl", prio=2, exam=0, ret=False, ret_prio=2):
        return Order(oid, t, o, d, kind, prio, exam, ret, ret_prio)
    return _make
