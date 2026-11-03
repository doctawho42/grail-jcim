"""What a comparator's declared knob actually moves, measured as a partition that must sum.

Two GLORYxR settings produce identical cells in the matched-length control: same recall, same
slot count, same interval, to the digit. A reader's first reading of two identical rows is that
one file was loaded twice, and the honest answer is not an assurance but a measurement: the
setting moves the ORDER of a substrate's candidate list and not its contents, and the control
reads each comparator's whole list, so it cannot see the setting at all.

The claim is a partition -- identical, same set in another order, different set -- and a
partition that does not sum to the substrates compared is not a measurement of anything. That is
what these pin, together with the direction that makes the claim non-vacuous: the two files must
actually differ somewhere, or the finding is that someone shipped one file twice.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "scripts" / "typed_edit" / "setting_scope.py"


def _module():
    for p in (ROOT / "scripts", ROOT / "scripts" / "typed_edit"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location("setting_scope_under_test", SRC)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_the_partition_sums_to_the_substrates_compared():
    m = _module()
    a = {"p": ["x", "y"], "q": ["x", "y"], "r": ["x", "y"], "s": ["x"]}
    b = {"p": ["x", "y"], "q": ["y", "x"], "r": ["x", "z"], "s": ["x", "y"]}
    got = m.partition(a, b, ["p", "q", "r", "s"])
    assert got["compared"] == 4
    assert got["identical"] + got["same_set_other_order"] + got["different_set"] \
        + got["different_length"] == got["compared"]


def test_each_class_is_the_one_it_names():
    m = _module()
    a = {"p": ["x", "y"], "q": ["x", "y"], "r": ["x", "y"], "s": ["x"]}
    b = {"p": ["x", "y"], "q": ["y", "x"], "r": ["x", "z"], "s": ["x", "y"]}
    got = m.partition(a, b, ["p", "q", "r", "s"])
    assert got["identical"] == 1            # p
    assert got["same_set_other_order"] == 1  # q
    assert got["different_set"] == 1         # r, same length and a different member
    assert got["different_length"] == 1      # s


def test_a_substrate_only_one_side_covers_is_refused():
    """Comparing a list against a list that is not there would silently shrink the denominator."""
    m = _module()
    with pytest.raises(SystemExit):
        m.partition({"p": ["x"]}, {"q": ["x"]}, ["p", "q"])


def test_two_identical_files_are_reported_as_identical_not_as_a_finding():
    """The direction that makes the claim non-vacuous. If the two sides never differ, the result
    is that one file was shipped twice, and the producer has to be able to say so."""
    m = _module()
    a = {"p": ["x", "y"], "q": ["z"]}
    got = m.partition(a, dict(a), ["p", "q"])
    assert got["identical"] == 2
    assert got["same_set_other_order"] == 0
    assert got["the_two_sides_never_differ"] is True


def test_a_repeated_candidate_is_not_collapsed_by_the_set_comparison():
    """A list with a duplicate and a list without it are not the same list, and a comparison
    through sets alone would call them the same set in another order."""
    m = _module()
    got = m.partition({"p": ["x", "x", "y"]}, {"p": ["x", "y", "y"]}, ["p"])
    assert got["same_set_other_order"] == 0
    assert got["different_set"] == 1
