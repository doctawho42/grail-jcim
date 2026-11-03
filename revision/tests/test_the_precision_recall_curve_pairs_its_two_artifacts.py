"""The precision-recall curve pairs two artifacts, and says which arms it could not pair.

Run: python -m pytest revision/tests/test_the_precision_recall_curve_pairs_its_two_artifacts.py -q

A reviewer asked for the comparison in the form the field reads, which for a ranked list is
precision against recall. The data exists and no new run is needed: recall at every budget is in
the deployment table and precision at the same budgets is in the precision table. They are two
artifacts with two naming conventions and two arm lists -- the sweep carries nine arms and the
precision table seven -- so pairing them is exactly where an arm goes missing from a figure while
the text beside it still counts nine.

So the pairing is checked rather than assumed: every point is the two artifacts' own values at
one budget for one arm, the budgets are the same list on both sides, and an arm the figure cannot
pair is named in what the figure returns instead of being dropped.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# The artifact each display reads, asked of the code that reads it. These were named here by
# file, which is how the whole set broke the day the controls moved from the comparison set to
# the whole evaluated test set: the figures drew one population and the tests checked them
# against another, and every failure said "the value drawn is not the value measured" when both
# were correct for their own population.
def _artifact(stem):
    import sys as _s
    _s.path.insert(0, str(ROOT / "scripts"))
    _s.path.insert(0, str(ROOT / "scripts" / "typed_edit"))
    from _acs_table import HEADLINE, control_artifact

    return ROOT / "results" / control_artifact(stem, HEADLINE)


sys.path.insert(0, str(ROOT / "scripts"))
PREC = _artifact("precision_table")
DEP = _artifact("deployment_table")

pytestmark = pytest.mark.skipif(not (PREC.exists() and DEP.exists()),
                                reason="an input artifact is not in this checkout")


@pytest.fixture
def figs(tmp_path, monkeypatch):
    import paper2_figures as m
    monkeypatch.setattr(m, "OUT", tmp_path)
    return m


def test_every_point_is_the_two_artifacts_own_values(figs):
    drawn = figs.fig_pr()
    prec = json.loads(PREC.read_text())["precision_micro"]
    rec = json.loads(DEP.read_text())["recall_micro"]
    for arm, pts in drawn["points"].items():
        pslug, dslug = drawn["precision_key"][arm], drawn["recall_key"][arm]
        for k, (r, p) in pts.items():
            assert p == prec[pslug][str(k)], f"{arm} at k={k}: precision drawn is not measured"
            assert r == rec[str(k)][dslug], f"{arm} at k={k}: recall drawn is not measured"


def test_both_sides_are_swept_at_the_same_budgets(figs):
    drawn = figs.fig_pr()
    prec = json.loads(PREC.read_text())["precision_micro"]
    rec = json.loads(DEP.read_text())["recall_micro"]
    kp = sorted(map(int, prec[next(iter(prec))]))
    kr = sorted(map(int, rec))
    assert kp == kr, (
        f"precision is measured at {kp} and recall at {kr}, so a point would pair two budgets")
    for pts in drawn["points"].values():
        assert sorted(pts) == kp


def test_an_arm_the_figure_cannot_pair_is_named_and_not_dropped(figs):
    drawn = figs.fig_pr()
    rec = json.loads(DEP.read_text())["recall_micro"]
    sweep_arms = set(rec[next(iter(rec))])
    paired = {drawn["recall_key"][a] for a in drawn["points"]}
    assert paired | set(drawn["absent"]) == sweep_arms, (
        "an arm of the sweep is neither drawn nor named absent, so the figure shows fewer arms "
        f"than the comparison has and says nothing: "
        f"{sorted(sweep_arms - paired - set(drawn['absent']))}")
    assert drawn["absent"], (
        "no arm is reported absent; if the precision table has caught up with the sweep this "
        "test should be the thing that says so")


def test_the_curve_is_monotone_in_the_budget(figs):
    """Recall cannot fall as the budget widens, so a curve that doubles back is a pairing bug."""
    drawn = figs.fig_pr()
    for arm, pts in drawn["points"].items():
        ks = sorted(pts)
        rs = [pts[k][0] for k in ks]
        assert rs == sorted(rs), f"{arm}: recall falls as the budget widens, {rs}"
