"""A reported formula separates two metabolites only when they do not share one.

Run: python -m pytest revision/tests/test_the_formula_gate_decides_only_where_formulas_are_unique.py -q

The protocol proposed for reading the external set's drawings leans on a check that does not go
through any recogniser: the molecular formula of the structure read back must equal the formula the
source prints for that metabolite. The strength of that check is not a property of the recogniser
and cannot be measured by scoring one. It is a property of the reference set: where two metabolites
of the same parent carry the same formula, a reader who swaps them passes the gate, and the gate
was asserted to be stronger than any model consensus before anyone had counted those pairs.

So the counting is asserted here. The population is per parent, because a drawing sits in one
parent's panel and a formula shared between two parents was never separating them; a listing that
repeats one metabolite is collapsed first, so a duplicate row cannot be read as a collision; the
two classes exhaust the references; and a pair added to the real set moves the number, which is
what keeps the measurement falsifiable rather than decorative.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _mod():
    spec = importlib.util.spec_from_file_location("_ocsr", ROOT / "scripts" / "ocsr_calibration.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["_ocsr"] = m
    spec.loader.exec_module(m)
    return m


OCSR = _mod()

# Three metabolites of one parent with three formulas, and nothing shared.
DISTINCT = [{"parent": "p", "smiles": s} for s in ("CCO", "CCCO", "CC(=O)O")]
# Ortho and para cresol: one parent, one formula, two structures the gate cannot separate.
ISOMERS = [{"parent": "p", "smiles": s} for s in ("Cc1ccccc1O", "Cc1ccc(O)cc1")]


def test_a_set_whose_formulas_are_unique_is_entirely_pinned():
    got = OCSR.formula_degeneracy(DISTINCT)
    assert got["n_references"] == 3
    assert got["pinned"] == 3 and got["undecided"] == 0
    assert got["rate_pinned"] == 1.0
    assert got["worst"]["n"] == 1


def test_two_isomers_under_one_parent_are_both_undecided():
    got = OCSR.formula_degeneracy(ISOMERS)
    assert got["n_references"] == 2
    assert got["pinned"] == 0 and got["undecided"] == 2, (
        "a formula shared by two metabolites of one parent left one of them pinned, so the "
        "grouping is not per parent or not by formula")
    assert got["worst"]["n"] == 2 and got["worst"]["parent"] == "p"


def test_the_same_formula_under_two_parents_separates_nothing_and_counts_as_nothing():
    split = [{"parent": "a", "smiles": "Cc1ccccc1O"}, {"parent": "b", "smiles": "Cc1ccc(O)cc1"}]
    got = OCSR.formula_degeneracy(split)
    assert got["undecided"] == 0, (
        "two metabolites of different parents were counted as a collision; the gate is applied "
        "inside one parent's panel and never had to tell those two apart")


def test_a_repeated_listing_is_collapsed_and_not_read_as_a_collision():
    twice = [{"parent": "p", "smiles": "CCO"}, {"parent": "p", "smiles": "CCO"}]
    got = OCSR.formula_degeneracy(twice)
    assert got["n_rows"] == 2 and got["n_references"] == 1
    assert got["undecided"] == 0, "one metabolite listed twice was counted as two that collide"


def test_the_two_classes_exhaust_the_real_references():
    got = OCSR.formula_degeneracy()
    assert got["n_references"] == got["pinned"] + got["undecided"]
    assert got["n_references"] > 100, f"only {got['n_references']} references were read"
    assert sum(int(k) * v for k, v in got["groups_by_size"].items()) == got["n_references"]
    assert got["population"], "the artifact does not say which set it measured"


def test_adding_a_pair_to_the_real_set_moves_the_number():
    base = OCSR.formula_degeneracy()
    first = OCSR.references()[0]["parent"]
    spiked = OCSR.references() + [{"parent": first, "smiles": s} for s in
                                  ("Cc1ccccc1O", "Cc1ccc(O)cc1")]
    got = OCSR.formula_degeneracy(spiked)
    assert got["undecided"] >= base["undecided"] + 2, (
        f"two colliding metabolites were added to the set and the undecided count went from "
        f"{base['undecided']} to {got['undecided']}, so the measurement does not read its input")


def test_a_collision_across_two_parents_moves_the_pooled_count_and_not_the_other():
    """The pooled count is reported beside the per-parent one, so it has to be able to differ.

    On the set this repository holds the two come out equal, because no two parent drugs share a
    metabolite formula. That is a measurement about this set, not a property of the code, and an
    artifact field nothing can move is a field a reader should not be shown. So the case where
    they differ is constructed here.
    """
    split = [{"parent": "a", "smiles": "Cc1ccccc1O"}, {"parent": "b", "smiles": "Cc1ccc(O)cc1"}]
    got = OCSR.formula_degeneracy(split)
    assert got["undecided"] == 0 and got["pooled_undecided"] == 2


def test_pooling_across_parents_can_only_raise_the_count():
    got = OCSR.formula_degeneracy()
    assert got["pooled_undecided"] >= got["undecided"], (
        "pooling the parents together separated metabolites that their own parent could not, "
        "which no grouping can do")


def test_every_parent_in_the_set_has_the_name_the_source_prints():
    names = OCSR.parent_names()
    parents = {r["parent"] for r in OCSR.references()}
    missing = sorted(p for p in parents if not names.get(p))
    assert not missing, f"{len(missing)} of {len(parents)} parents have no drug name in the source"


def test_a_degenerate_group_is_reported_under_a_drug_name_and_not_only_a_structure():
    """The extremum this measurement turns on has to carry the label it belongs to.

    A largest group reported as a parent SMILES is a number whose subject a reader cannot
    identify, which is how a margin gets attributed to the wrong thing.
    """
    got = OCSR.formula_degeneracy()
    assert got["worst"]["drug"], "the largest formula group names no drug"
    nameless = [g for g in got["collisions"] if not g.get("drug")]
    assert not nameless, f"{len(nameless)} of {len(got['collisions'])} groups name no drug"


def test_the_committed_measurement_is_what_the_producer_computes_now():
    """The artifact in the tree has to be the one this code produces, or it is a stale citation.

    It is carried in the repository because it is about the reference set and not about a machine,
    which is only true while it matches a fresh run. An artifact nobody re-derives is how an input
    gets corrected and its consumer keeps printing the old number.
    """
    import json

    stored = json.loads(OCSR.DEGEN.read_text())
    fresh = OCSR.formula_degeneracy()
    for field in ("n_rows", "n_references", "n_parents", "pinned", "undecided", "rate_pinned",
                  "groups_by_size", "worst", "pooled_undecided", "unparsed", "collisions"):
        assert stored[field] == fresh[field], (
            f"{OCSR.DEGEN.name} carries a different {field} from what the producer computes now; "
            f"re-run: python scripts/ocsr_calibration.py degeneracy")
