"""A producer that takes a population argument must not describe itself as the default one.

The deployment table accepts a pool spec, and two things in its report were written as if that
spec were always the comparison set: the string naming what defines the population, and a gate
that compares the computed MetaTox column against the one results/four_method_291.json commits.

Run on the whole evaluated split the artifact therefore said "n": 1170 and, two lines down,
"source": "the 291 of results/four_method_291.json"; and the gate reported
reproduces_four_method_291_metatox: false with a mismatch at every budget, which is the right
answer to a question nobody asked -- two different populations do not have the same recall -- and
reads as a failed check on the table beside it. Neither stopped the run.

What the gate can decide is limited by what the defining artifact stores: a substrate COUNT and no
substrate list. So applicability is decided on the count, which cannot tell one population of that
size from another, and the last test here pins that rather than leaving it to be discovered.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "scripts" / "typed_edit" / "deployment_table.py"
DECLARED = 291


def _module():
    for p in (ROOT / "scripts", ROOT / "scripts" / "typed_edit"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location("deployment_table_under_test", SRC)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_the_population_the_committed_file_defines_is_named_as_that_file():
    m = _module()
    got = m.population_source("results/widepools_implicit/w*.json", DECLARED, DECLARED)
    assert "four_method_291.json" in got


def test_another_population_is_named_by_the_spec_and_not_as_the_291():
    """The defect verbatim: an artifact whose n is 1170 saying its source is the 291."""
    m = _module()
    got = m.population_source("results/widepools_fulltest/w*.json", 1170, DECLARED)
    assert "widepools_fulltest" in got
    assert "291" not in got, got


def test_the_gate_applies_on_the_population_it_is_about_and_reports_a_mismatch_there():
    m = _module()
    v = m.four_method_verdict(DECLARED, DECLARED, ["MetaTox k=1: 0.1 vs committed 0.2"])
    assert v["applies"] is True
    assert v["reproduces_four_method_291_metatox"] is False
    assert v["mismatches"] == ["MetaTox k=1: 0.1 vs committed 0.2"]


def test_the_gate_passes_on_that_population_when_nothing_differs():
    m = _module()
    v = m.four_method_verdict(DECLARED, DECLARED, [])
    assert v["applies"] is True and v["reproduces_four_method_291_metatox"] is True


def test_the_gate_says_it_does_not_apply_rather_than_reporting_a_false_mismatch():
    m = _module()
    v = m.four_method_verdict(1170, DECLARED, ["MetaTox k=1: 0.4 vs committed 0.04"])
    assert v["applies"] is False
    assert v["reproduces_four_method_291_metatox"] is None
    assert v["mismatches"] == []
    assert v.get("why_not")


def test_what_the_count_cannot_see_is_pinned_rather_than_left_to_be_found():
    """The weakness of deciding on a count, stated as a test so it is not a surprise later.

    results/four_method_291.json records n_substrates and no substrate list, so a DIFFERENT
    population of the same size passes as the one the gate is about, and a real mismatch there
    would be reported as a fault of this table rather than of the population. Nothing available
    in that artifact closes this; the test exists so the gap is visible where the gate is read.
    """
    m = _module()
    v = m.four_method_verdict(DECLARED, DECLARED, ["MetaTox k=1: 0.9 vs committed 0.04"])
    assert v["applies"] is True
    assert v["reproduces_four_method_291_metatox"] is False
