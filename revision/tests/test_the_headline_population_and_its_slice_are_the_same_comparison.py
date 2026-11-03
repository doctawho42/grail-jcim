"""The headline comparison and the comparison-set slice must be the same comparison.

Run: python -m pytest revision/tests/test_the_headline_population_and_its_slice_are_the_same_comparison.py -q

The headline moves onto the whole evaluated test set, and the 291-substrate comparison set stays
as the slice the controls were computed on. That only means anything if the two are the same
comparison read on two populations: the same arms, the same budgets, the same aggregation, the
same parent-drop convention. If the wider table quietly carried a different arm list or a coarser
budget grid, "the wide-budget results hold on the larger population" would be comparing two
different experiments and reporting the comparison as a robustness check.

The move was nearly not made at all, which is why this is a test and not a comment. Two artifacts
in this tree said the whole-split comparison could not carry the exhaustive arm -- a typed note in
one, and a docstring in the Supporting Information generator saying the whole-test axis sweeps
five budgets "not the nine the deployment table does". Both were true when written. By the time a
reviewer asked for the headline to move, results/deployment_table_1170.json carried nine arms over
nine budgets with no comparator absent, and the two stale sentences were the only thing standing
between the reviewer's request and the table that answers it.

The last test is the one that earns its place: a verdict that changes between the two populations
has to be counted, because the honest way to report a move like this is to say how many cells it
costs as well as how many it gains.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SLICE = ROOT / "results/deployment_table.json"
WHOLE = ROOT / "results/deployment_table_1170.json"

pytestmark = pytest.mark.skipif(not (SLICE.exists() and WHOLE.exists()),
                                reason="one of the two deployment tables is not in this checkout")


def _load():
    return json.loads(SLICE.read_text()), json.loads(WHOLE.read_text())


def test_both_populations_carry_the_same_arms():
    a, b = _load()
    ka, kb = next(iter(a["recall_micro"])), next(iter(b["recall_micro"]))
    assert set(a["recall_micro"][ka]) == set(b["recall_micro"][kb]), (
        "the two populations are scored over different arms, so one is not a reading of the "
        "other: slice has " + ", ".join(sorted(set(a["recall_micro"][ka]) - set(b["recall_micro"][kb])))
        + "; whole has " + ", ".join(sorted(set(b["recall_micro"][kb]) - set(a["recall_micro"][ka]))))


def test_both_populations_carry_the_same_budgets():
    a, b = _load()
    assert sorted(map(int, a["recall_micro"])) == sorted(map(int, b["recall_micro"])), (
        "the budget grids differ, so a lead at a budget on one population has no counterpart on "
        "the other and the move cannot be followed cell by cell")
    assert sorted(map(int, a["contrasts"])) == sorted(map(int, b["contrasts"]))


def test_the_wider_population_leaves_no_comparator_out():
    _, b = _load()
    assert b.get("comparators_absent") == [], (
        "a comparator is absent from the headline population: " + str(b.get("comparators_absent")))
    for name, cov in b["comparator_coverage"].items():
        assert cov["of_population"] == b["population"]["n"], (
            f"{name} is scored over {cov['of_population']} substrates and the population is "
            f"{b['population']['n']}")


def test_both_populations_are_aggregated_the_same_way():
    a, b = _load()
    for field in ("aggregation", "convention", "seed", "n_boot"):
        assert a.get(field) == b.get(field), (
            f"the two tables differ in {field}: {a.get(field)!r} against {b.get(field)!r}, so "
            f"a difference between them is not only the population")


def test_every_verdict_that_changes_between_the_populations_is_counted():
    """What the move costs, not only what it buys."""
    a, b = _load()
    moved, gained, lost = [], [], []
    for k in a["contrasts"]:
        for pair, ca in a["contrasts"][k].items():
            cb = b["contrasts"].get(k, {}).get(pair)
            if cb is None or "unavailable" in ca or "unavailable" in cb:
                continue
            sa = (ca["excludes_zero"], ca["gap"] > 0)
            sb = (cb["excludes_zero"], cb["gap"] > 0)
            if sa == sb:
                continue
            moved.append((k, pair, sa, sb))
            ours = pair.split(" - ")[0] in ("whole bank", "trained budget")
            good = sb[0] and sb[1] and ours
            (gained if good else lost).append((k, pair))
    assert moved, (
        "not one verdict changes between a 291-substrate population and a 1170-substrate one, "
        "which would mean the two tables are the same numbers and this check is vacuous")
    print(f"\n  verdicts that change when the headline moves: {len(moved)}; "
          f"{len(gained)} become a separating lead for this work, {len(lost)} do not")
    for k, pair, sa, sb in sorted(moved, key=lambda x: (x[1], int(x[0]))):
        print(f"    k={k:<3} {pair:<42} {sa} -> {sb}")
