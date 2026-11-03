"""A hand-drawn reference set is only worth anything if it is the published one.

Run: python -m pytest revision/tests/test_the_external_reference_set_is_the_published_one.py -q

The strongest limitation this work states is that no measurement in it is external: every figure
is on one corpus, assembled here, whose selection cannot be recovered. The radiolabelled human
ADME sets of Gao and co-workers would answer it, and the reason they have not is that their known
metabolites are published as drawings. Drawings can be redrawn. Ninety-seven structures across
eleven drugs is two or three days of work, and what comes out is a machine-readable reference set
the field does not have.

The risk in a hand-drawn set is the obvious one, so the counts are fixed before a pen touches
anything: the paper publishes how many metabolites each drug has, and the worksheet is built with
exactly that many empty rows per drug. A sheet that comes back with a row too few or too many
fails here rather than becoming a recall figure. The substrates are not drawn at all; they are
read out of the authors' own deposited input scripts, so the molecule each sheet is about is
theirs and not our reading of a figure.

These tests drive the builder and the validator on fixtures, including a sheet that is wrong in
each of the ways a hand-filled sheet goes wrong.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

DEPOSIT = ROOT / "artifacts" / "external" / "gao2026"


@pytest.fixture
def M():
    import external_reference_set as m
    return m


def test_every_published_drug_has_a_substrate_from_the_authors_own_input(M):
    if not DEPOSIT.exists():
        pytest.skip("the deposit is not in this checkout")
    spec = M.build_spec()
    assert len(spec) == 11, sorted(spec)
    for name, row in spec.items():
        assert row["substrate"], f"{name}: no parent SMILES was recovered from the deposit"
        assert row["source_file"].endswith(".py"), row
        assert row["metabolites_published"] >= 1, row
    assert sum(r["metabolites_published"] for r in spec.values()) == 97


def test_the_one_name_that_differs_is_recorded_as_an_alias_and_not_merged_in_silence(M):
    if not DEPOSIT.exists():
        pytest.skip("the deposit is not in this checkout")
    spec = M.build_spec()
    aliased = {n: r for n, r in spec.items() if r.get("deposit_name") != n}
    assert aliased, ("the deposit and the published table agree on every name, so the alias this "
                     "module carries is now unnecessary and should be removed")
    for n, r in aliased.items():
        assert r.get("alias_reason"), f"{n} is matched to {r['deposit_name']} with no reason given"


def test_a_sheet_with_the_wrong_number_of_rows_is_refused(M, tmp_path):
    spec = {"DrugA": {"substrate": "CCO", "metabolites_published": 2,
                      "deposit_name": "DrugA", "source_file": "DrugA.py"}}
    good = "drug,index,smiles,note\nDrugA,1,CCO O,\nDrugA,2,OCCO,\n".replace("CCO O", "CC=O")
    short = "drug,index,smiles,note\nDrugA,1,CC=O,\n"
    long = good + "DrugA,3,OCCCO,\n"
    assert M.validate_sheet(good, spec)["ok"], M.validate_sheet(good, spec)
    for bad, why in ((short, "too few"), (long, "too many")):
        r = M.validate_sheet(bad, spec)
        assert not r["ok"], why
        assert any("DrugA" in p for p in r["problems"]), r


def test_the_other_ways_a_hand_filled_sheet_goes_wrong(M):
    spec = {"DrugA": {"substrate": "CCO", "metabolites_published": 2,
                      "deposit_name": "DrugA", "source_file": "DrugA.py"}}
    cases = {
        "a structure that does not parse": "drug,index,smiles,note\nDrugA,1,CC=O,\nDrugA,2,C1CC,\n",
        "the same structure twice": "drug,index,smiles,note\nDrugA,1,CC=O,\nDrugA,2,CC=O,\n",
        "a metabolite equal to its substrate": "drug,index,smiles,note\nDrugA,1,CC=O,\nDrugA,2,CCO,\n",
        "a drug the specification does not name": "drug,index,smiles,note\nDrugA,1,CC=O,\nDrugA,2,OCCO,\nDrugB,1,CCC,\n",
        "an empty cell left unfilled": "drug,index,smiles,note\nDrugA,1,CC=O,\nDrugA,2,,\n",
    }
    for why, text in cases.items():
        r = M.validate_sheet(text, spec)
        assert not r["ok"], f"the validator accepted {why}"
        assert r["problems"], why


def test_the_validator_reports_what_changed_so_a_drawing_error_is_visible(M):
    """A metabolite whose formula is unchanged from its substrate is usually a mis-drawn ring."""
    spec = {"DrugA": {"substrate": "CCO", "metabolites_published": 1,
                      "deposit_name": "DrugA", "source_file": "DrugA.py"}}
    r = M.validate_sheet("drug,index,smiles,note\nDrugA,1,CC=O,\n", spec)
    assert r["ok"], r
    d = r["rows"][0]
    assert d["formula_delta"], d
    assert d["inchikey"], d
