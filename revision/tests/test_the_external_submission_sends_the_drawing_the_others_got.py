"""The eleven substrates go out in the benchmark's own drawing, or the column is not comparable.

Run: python -m pytest revision/tests/test_the_external_submission_sends_the_drawing_the_others_got.py -q

Four models are already scored on this set by its authors, each having been handed the parent
structure as the benchmark's own input scripts write it. A column added to that table is only in
the same table if it met the same string. Re-drawing a substrate on the way out -- a tautomer
canonicalised, a salt stripped, a charge neutralised -- produces a number that looks like a sixth
column and is a measurement of something else, which is the failure this repository has already
recorded four times under a different name.

So the submission set is asserted to carry the eleven substrates unchanged: the same count, the
same identifiers, and a string that is character-for-character the one held here, not merely one
that parses to the same molecule. The SDF and the SMILES file are asserted to be the same
molecules as each other, because they are alternative uploads and a service given one must not
be answering about the other.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _mod():
    spec = importlib.util.spec_from_file_location(
        "_form", ROOT / "scripts" / "make_gao_metatox_form_input.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["_form"] = m
    spec.loader.exec_module(m)
    return m


FORM = _mod()
HELD = ROOT / "revision" / "gao2026_reference_set" / "substrates.csv"


def _held() -> dict:
    with HELD.open() as fh:
        return {r["drug"]: r for r in csv.DictReader(fh)}


@pytest.fixture(scope="module")
def built():
    FORM.main([])
    return json.loads((FORM.OUT / "manifest.json").read_text())


def test_the_submission_carries_every_substrate_and_no_other(built):
    held = _held()
    assert built["n_substrates"] == len(held) == 11
    lines = (FORM.OUT / "substrates.smi").read_text().splitlines()
    assert len(lines) == len(held)
    assert sorted(l.split("\t")[1] for l in lines) == sorted(held)


def test_the_string_sent_is_the_string_held_and_not_a_redrawing(built):
    """Character for character. A molecule that merely matches is a different experiment."""
    held = _held()
    for line in (FORM.OUT / "substrates.smi").read_text().splitlines():
        smiles, ident = line.split("\t")
        assert smiles == held[ident]["smiles"], (
            f"{ident} goes out in a drawing that is not the one the benchmark's own input "
            f"scripts pass, so its column would not belong in the benchmark's table")


def test_the_two_uploads_are_the_same_molecules(built):
    from rdkit import Chem
    smi = {l.split("\t")[1]: l.split("\t")[0]
           for l in (FORM.OUT / "substrates.smi").read_text().splitlines()}
    supplier = Chem.SDMolSupplier(str(FORM.OUT / "substrates.sdf"))
    seen = 0
    for mol in supplier:
        assert mol is not None, "a record in the SDF does not parse"
        ident = mol.GetProp("_Name")
        seen += 1
        assert Chem.MolToSmiles(mol) == Chem.MolToSmiles(Chem.MolFromSmiles(smi[ident])), (
            f"{ident} is a different molecule in the two files a service may be given")
    assert seen == len(smi)


def test_the_manifest_says_how_much_work_the_answer_has_to_cover(built):
    held = _held()
    want = {d: int(r["metabolites_published"]) for d, r in held.items()}
    assert built["published_metabolites"] == want
    assert sum(want.values()) == 97


def test_the_unconfirmed_name_pairing_travels_with_the_file(built):
    """The deposit calls one drug FCN-437c and the table calls it Fovinaciclib.

    It is the only unmatched name on either side and the pairing is an inference. A submission
    that carries it silently would have the co-author confirm nothing.
    """
    assert "FCN-437c" in json.dumps(built)
    assert "FCN-437c" in (FORM.OUT / "README.md").read_text()
