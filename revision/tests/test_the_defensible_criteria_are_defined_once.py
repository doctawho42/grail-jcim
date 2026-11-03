"""The criteria the manuscript's grid shows are the criteria the manuscript defends, defined once.

Run: python -m pytest revision/tests/test_the_defensible_criteria_are_defined_once.py -q

A reviewer objected that a multiverse built partly on criteria known to be unreasonable inflates
an instability it then reports. The objection is right and the measurement says so: across all
five declared criteria the verdict moves at six of the nine budgets, and across the three that
answer "are these the same compound" it moves at one. So the manuscript's grid shows those three
and the Supporting Information keeps all five.

That split is a roster, and a roster written twice is the defect this project has met in eleven
files. The figure chooses which rows to draw and the number macros count how many budgets move
among them; if those two lists drift, the figure and the sentence beside it describe different
subsets and nothing says so. They are required here to be the same object, imported from one
place, and the count the macros publish is required to match what the figure drew.
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
ART = _artifact("criterion_sweep")

pytestmark = pytest.mark.skipif(not ART.exists(),
                                reason="criterion_sweep.json is not in this checkout")


def test_one_definition_of_defensible_reaches_both_the_figure_and_the_numbers():
    import paper2_numbers as nums
    import paper2_figures as figs
    a = getattr(nums, "DEFENSIBLE", None)
    b = getattr(figs, "DEFENSIBLE", None)
    assert a is not None, "paper2_numbers has no DEFENSIBLE to share"
    assert b is not None, "paper2_figures does not take the defensible set from anywhere"
    assert a is b or tuple(a) == tuple(b), (
        f"the figure draws {tuple(b)} and the numbers count {tuple(a)}, so the grid and the "
        f"sentence beside it are about different subsets")


def test_every_defensible_criterion_is_one_the_sweep_measured():
    import paper2_numbers as nums
    measured = set(json.loads(ART.read_text())["criteria"])
    unknown = [c for c in nums.DEFENSIBLE if c not in measured]
    assert not unknown, f"the defensible set names criteria the sweep never measured: {unknown}"
    assert len(nums.DEFENSIBLE) < len(measured), (
        "every measured criterion is called defensible, so the restriction is vacuous")


def test_the_manuscript_figure_draws_the_defensible_set_and_the_supplement_draws_all_five(tmp_path, monkeypatch):
    import paper2_figures as figs
    monkeypatch.setattr(figs, "OUT", tmp_path)
    main = figs.fig_criterion()
    assert tuple(main["criteria"]) == tuple(figs.DEFENSIBLE), (
        f"the manuscript's grid draws {main['criteria']} and the defensible set is "
        f"{tuple(figs.DEFENSIBLE)}")
    si = getattr(figs, "fig_si_criterion_all", None)
    assert si is not None, "no supplement figure keeps the criteria the manuscript drops"
    allfive = si()
    assert set(allfive["criteria"]) == set(json.loads(ART.read_text())["criteria"]), (
        "the supplement does not keep every declared criterion, so a criterion is dropped from "
        "the paper rather than moved out of the grid")


def test_the_published_movement_count_is_what_the_drawn_grid_shows(tmp_path, monkeypatch):
    """The number in the sentence and the shape in the figure have to be one measurement."""
    import paper2_figures as figs
    import paper2_numbers as nums
    monkeypatch.setattr(figs, "OUT", tmp_path)
    drawn = figs.fig_criterion()
    moved = sum(1 for col in zip(*drawn["grid"]) if len(set(col)) > 1)
    n = nums.build()
    assert n["crit.defensible_moved"] == moved, (
        f"the macros publish {n['crit.defensible_moved']} budgets whose verdict moves and the "
        f"figure draws {moved}")
