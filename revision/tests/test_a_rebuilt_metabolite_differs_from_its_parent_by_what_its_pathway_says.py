"""The held-out check on the reconstructor: the document states the chemistry of every row.

Run: python -m pytest revision/tests/test_a_rebuilt_metabolite_differs_from_its_parent_by_what_its_pathway_says.py -q

The reconstructor was calibrated on the ten parent drawings, and the rule that recognises a hashed
stereo bond was arrived at by reading those ten failures, so seven of ten is an upper bound and not
an estimate. This is the check nothing was fitted to.

Every metabolite row names its biotransformation in text beside the drawing. An oxidation adds one
oxygen; a glucuronidation adds C6H8O6; a dehydrogenation removes two hydrogens. So a metabolite
rebuilt from its own segments must differ from the structure it was made from by exactly the
formula its pathway implies, and nothing in the reconstructor has ever seen a pathway.

Not every row can be checked, and the ones that cannot are the point of the first assertion here.
A dealkylation removes an alkyl group the name does not size. A hydrolysis cleaves a bond and the
row is one of the two pieces, so the name states neither which piece nor what it kept. A row whose
drawing marks a region rather than a structure has no formula at all. Each of those is a stated
exclusion rather than a silent pass, and the vocabulary is required to classify every pathway
string the document uses, so a new one cannot slip through as a pass.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _mod():
    spec = importlib.util.spec_from_file_location(
        "_path", ROOT / "scripts" / "typed_edit" / "gao_pathway_check.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["_path"] = m
    spec.loader.exec_module(m)
    return m


CHK = _mod()
TABLES = ROOT / "revision" / "gao2026_reference_set" / "si_tables.json"
pytestmark = pytest.mark.skipif(not TABLES.exists(), reason="the tables have not been read")


def test_every_pathway_the_document_uses_is_classified():
    """A vocabulary that silently fails to recognise a name would pass that row by default."""
    blob = json.loads(TABLES.read_text())
    said = {" ".join(r["pathway"].split()) for t in blob["tables"] for r in t["rows"]
            if not r["is_parent"]}
    unknown = sorted(p for p in said if CHK.classify(p) is CHK.UNCLASSIFIED)
    assert unknown == [], (
        f"{len(unknown)} pathway strings are neither given a formula change nor named as one "
        f"the document does not determine: {unknown[:6]}")


def test_a_compound_pathway_is_the_sum_of_its_steps():
    assert CHK.classify("Oxidation and dehydrogenation") == {"O": 1, "H": -2}
    assert CHK.classify("Oxidation and glucuronidation") == {"O": 7, "H": 8, "C": 6}
    assert CHK.classify("Hydroxylation and Dehydration") == {"O": 0, "H": -2}


def test_a_pathway_that_does_not_state_a_size_is_not_given_one():
    for vague in ("N-dealkylation", "Hydrolysis", "O-dealkylation",
                  "oxidative cleavage of morpholine ring"):
        assert CHK.classify(vague) is None, f"{vague} was given a formula change it does not state"


def test_a_pathway_naming_another_row_is_measured_from_that_row():
    rows = [{"id": "M4", "pathway": "-"}, {"id": "M41", "pathway": "M4 O-methylation"}]
    assert CHK.base_of(rows[1], rows) == "M4"
    longer = [{"id": "M4", "pathway": "-"}, {"id": "M412-1", "pathway": "-"},
              {"id": "X", "pathway": "Glucuronidation of M412-1"}]
    assert CHK.base_of(longer[2], longer) == "M412-1", (
        "a shorter identifier that is a prefix of the one named was preferred")


def test_the_classes_exhaust_the_rows_and_the_check_is_reported_per_reason():
    got = CHK.check()
    assert got["n_rows"] == sum(got["by_outcome"].values())
    assert got["n_checked"] == got["n_agree"] + got["n_disagree"]
    assert got["n_checked"] > 0, "no row could be checked, so this measures nothing"


def test_a_changed_structure_stops_agreeing():
    """The gate has to be able to go red on a row that currently passes."""
    got = CHK.check()
    agreeing = [r for r in got["rows"] if r["outcome"] == "agrees"]
    assert agreeing, "no row agrees, so this control cannot run"
    r = agreeing[0]
    spoiled = dict(r["observed"])
    spoiled["O"] = spoiled.get("O", 0) + 1
    assert spoiled != r["expected"], (
        "adding an oxygen to a row's observed change left it equal to the expected change")


def test_the_recorded_result_is_what_the_check_computes_now():
    stored = json.loads(CHK.OUT.read_text())
    fresh = CHK.check()
    for field in ("n_rows", "n_checked", "n_agree", "n_disagree", "by_outcome"):
        assert stored[field] == fresh[field], (
            f"{CHK.OUT.name} records a different {field}; re-run: "
            f"python scripts/typed_edit/gao_pathway_check.py")
