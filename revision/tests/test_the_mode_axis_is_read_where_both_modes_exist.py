"""Sweeping a comparator's own declared knob, where only part of the population has both settings.

MetaTox offers the submitter two modes and both were submitted. The reported column is the SMIRKS
mode over all 291 substrates of the comparison set; the default mode came back for 248 of them.
So the knob can be swept, but not on the declared population, and a sweep that quietly reads 248
substrates while the paper's other numbers read 291 would be comparing two things.

Three ways that goes wrong, and these pin all three. The population has to be the substrates every
arm in the sweep covers and nothing else, with its size reported rather than assumed. A verdict
has to be a verdict -- leads, trails or undecided -- and not a gap, because the paper claims a
lead only where an interval excludes zero. And a shift has to be a change of verdict, not a change
of gap: a lead that grows is not news, a lead that stops separating is.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "scripts" / "typed_edit" / "metatox_mode.py"


def _module():
    for p in (ROOT / "scripts", ROOT / "scripts" / "typed_edit"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location("metatox_mode_under_test", SRC)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# --- the population ---------------------------------------------------------------------------

def test_the_population_is_what_every_mode_covers_and_nothing_else():
    m = _module()
    a = {"s1": ["x"], "s2": ["x"], "s3": ["x"]}
    b = {"s1": ["y"], "s3": ["y"], "s9": ["y"]}
    assert m.common_population(a, b, ["s1", "s2", "s3", "s4"]) == ["s1", "s3"]


def test_a_population_no_mode_pair_covers_is_refused():
    m = _module()
    with pytest.raises(SystemExit):
        m.common_population({"s1": ["x"]}, {"s2": ["y"]}, ["s1", "s2"])


def test_a_substrate_present_with_an_empty_list_still_counts_as_covered():
    """An empty prediction is an answer -- the method returned nothing -- and dropping it would
    score the substrate against a population it was not measured on."""
    m = _module()
    assert m.common_population({"s1": []}, {"s1": ["y"]}, ["s1"]) == ["s1"]


# --- a verdict is a verdict -------------------------------------------------------------------

def test_a_verdict_is_read_from_the_interval_and_not_from_the_gap():
    m = _module()
    assert m.verdict({"gap": +0.05, "excludes_zero": True}) == "leads"
    assert m.verdict({"gap": -0.05, "excludes_zero": True}) == "trails"
    assert m.verdict({"gap": +0.05, "excludes_zero": False}) == "undecided"
    assert m.verdict({"gap": -0.05, "excludes_zero": False}) == "undecided"
    assert m.verdict({"gap": 0.0, "excludes_zero": False}) == "undecided"


# --- a shift is a change of verdict -----------------------------------------------------------

def test_a_lead_that_stops_separating_is_a_shift():
    m = _module()
    s = m.shifts({"30": {"gap": +0.05, "excludes_zero": True}},
                 {"30": {"gap": +0.04, "excludes_zero": False}})
    assert [x["k"] for x in s] == ["30"]
    assert s[0]["under_the_reported_mode"] == "leads"
    assert s[0]["under_the_other_mode"] == "undecided"


def test_a_lead_that_merely_grows_is_not_a_shift():
    m = _module()
    assert m.shifts({"30": {"gap": +0.05, "excludes_zero": True}},
                    {"30": {"gap": +0.40, "excludes_zero": True}}) == []


def test_a_verdict_that_reverses_is_reported_with_both_sides():
    m = _module()
    s = m.shifts({"1": {"gap": +0.05, "excludes_zero": True}},
                 {"1": {"gap": -0.07, "excludes_zero": True}})
    assert s[0]["under_the_reported_mode"] == "leads"
    assert s[0]["under_the_other_mode"] == "trails"


def test_a_budget_only_one_side_carries_is_refused_rather_than_skipped():
    """Comparing the budgets they happen to share would make the sweep's width depend on which
    cells were computed."""
    m = _module()
    with pytest.raises(SystemExit):
        m.shifts({"1": {"gap": 0.0, "excludes_zero": False}},
                 {"1": {"gap": 0.0, "excludes_zero": False},
                  "3": {"gap": 0.0, "excludes_zero": False}})
