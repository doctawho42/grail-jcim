"""A worked example prints a row for every metabolite its substrate is annotated with.

Run: python -m pytest revision/tests/test_a_worked_example_accounts_for_every_metabolite_it_has.py -q

The worked-example table is built from a map of reference key to chemical name, typed by hand
because a name is chemistry a person supplies and no key derives it. That makes it the one place
in this paper where a row can go missing without the generator noticing: drop a key from the map
and the table prints one fewer metabolite, with no gap where it was.

The risk is not hypothetical for this table in particular. The example exists to show what the
deployed mode returns, and the metabolite most likely to be dropped is the one the mode does not
find -- which is exactly the row a reader needs. A second example was added after a reviewer
observed that the first shows the deployed mode recovering none of the four metabolites on the
drawing a chemist would submit; a table that quietly lost the misses of the second would answer
the reviewer by hiding the same thing again.

So the map is checked against the artifact: every annotated reference of every substrate the
table names has a row, the names are distinct, and no name is left over for a key the substrate
does not carry.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture
def mod():
    import paper2_tables_more as m
    return m


def _examples(mod):
    """Every worked example the table carries, as (label, interactive artifact, exhaustive one)."""
    ex = getattr(mod, "CASE_EXAMPLES", None)
    if ex is None:
        pytest.skip("the table carries one example and CASE_EXAMPLES does not exist yet")
    return ex


def test_every_annotated_metabolite_of_every_example_has_a_name(mod):
    for label, spec in _examples(mod).items():
        inter = json.loads((ROOT / "results" / spec["interactive"]).read_text())
        refs = set(inter["reference_keys"]) if "reference_keys" in inter else None
        if refs is None:
            refs = {c["key"] for c in inter["candidates"] if c["is_reference"]}
            refs |= set(inter.get("references_not_in_pool") or [])
        missing = [k for k in refs if k not in spec["names"]]
        assert not missing, (
            f"{label}: the artifact carries annotated metabolites the table has no name for, so "
            f"they print no row: {sorted(missing)}")
        assert len(refs) == inter["n_references"], (
            f"{label}: {len(refs)} keys recovered against n_references={inter['n_references']}")


def test_no_name_is_left_over_for_a_metabolite_the_substrate_does_not_carry(mod):
    for label, spec in _examples(mod).items():
        inter = json.loads((ROOT / "results" / spec["interactive"]).read_text())
        refs = {c["key"] for c in inter["candidates"] if c["is_reference"]}
        refs |= set(inter.get("references_not_in_pool") or [])
        extra = [k for k in spec["names"] if k not in refs]
        assert not extra, (
            f"{label}: the table names a metabolite the artifact does not carry, so a row is "
            f"printed for chemistry this substrate is not annotated with: {sorted(extra)}")
        assert len(set(spec["names"].values())) == len(spec["names"]), (
            f"{label}: two metabolites share a name, so a reader cannot tell the rows apart")


def test_the_two_arms_of_an_example_are_the_same_substrate_at_two_rule_budgets(mod):
    for label, spec in _examples(mod).items():
        inter = json.loads((ROOT / "results" / spec["interactive"]).read_text())
        exh = json.loads((ROOT / "results" / spec["exhaustive"]).read_text())
        assert inter["substrate"] == exh["substrate"], (
            f"{label}: the two arms were run on different substrates")
        assert inter["configuration"]["rule_budget"] < exh["configuration"]["rule_budget"], (
            f"{label}: the arm labelled exhaustive does not have the larger rule budget")
        for field in ("pool_cap", "match", "substrate_presentation", "ranking"):
            assert inter["configuration"][field] == exh["configuration"][field], (
                f"{label}: the two arms differ in {field}, so the contrast is not the budget")


def test_the_table_prints_a_row_for_every_name(mod):
    tex = mod.case_study()
    for label, spec in _examples(mod).items():
        for key, name in spec["names"].items():
            assert name in tex, f"{label}: no row for {name}"
