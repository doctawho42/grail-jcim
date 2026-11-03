"""The submission set built for the missing control carries the corpus form and nothing else.

Run: python -m pytest revision/tests/test_the_corpus_form_submission_is_the_corpus_form.py -q

MetaTox's column was obtained by submitting a re-tautomerised drawing of each substrate, because
the corpus stores amides as imidic acids and submitting that to someone else's service would
handicap it on a drawing no chemist would use. That was the right call for the comparator and it
leaves the comparison asymmetric: six arms met the substrate as the corpus stores it and one did
not, in the direction that favours this work, by an amount no sweep here bounds.

The control that would bound it is the one submission nobody has run: the same comparator on the
corpus form. This set is built for it, and the one way to get it wrong is to build it from the
same re-tautomerised strings the first submission used, which would make the control a repeat.
So every row is checked against the corpus string, and the rows are required to be exactly those
whose two forms differ -- re-running a substrate whose forms agree measures nothing and costs a
submission.

The join has to survive too. The corpus string is the key the scoring joins on, and the form
submitted the first time was required to share its tautomer-aware key; both are checked here, so
a returned prediction can be scored against the same annotation either way.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
OUT = ROOT / "revision/metatox_corpus_form"
SOURCES = (ROOT / "results/metatox_input/substrate_map.csv",
           ROOT / "revision/metatox_submission_1170/substrate_map.csv")

pytestmark = pytest.mark.skipif(not all(p.exists() for p in SOURCES),
                                reason="a MetaTox submission map is not in this checkout")


def _differing():
    """Every substrate whose submitted form was not the corpus form, from both submissions."""
    out = {}
    for p in SOURCES:
        for r in csv.DictReader(p.open()):
            if r["substrate_smiles"] != r["submission_smiles"]:
                out[r["substrate_smiles"]] = (p.name, r["id"], r["submission_smiles"])
    return out


def _built():
    f = OUT / "substrate_map.csv"
    if not f.exists():
        pytest.skip("the corpus-form submission set has not been built yet")
    return list(csv.DictReader(f.open()))


def test_every_row_submits_the_corpus_form():
    for r in _built():
        assert r["submission_smiles"] == r["corpus_smiles"], (
            f"{r['id']}: the submission string is not the corpus string, so running it would "
            f"repeat the submission this control exists to vary")


def test_the_set_is_exactly_the_substrates_whose_two_forms_differ():
    want = _differing()
    got = {r["corpus_smiles"] for r in _built()}
    missing = sorted(set(want) - got)
    extra = sorted(got - set(want))
    assert not missing, (
        f"{len(missing)} substrates were submitted in another form and are not in this set, so "
        f"the control would be partial: {missing[:3]}")
    assert not extra, (
        f"{len(extra)} substrates are in this set whose two forms already agree, so a submission "
        f"is spent on a run that cannot differ: {extra[:3]}")


def test_the_two_forms_are_the_same_molecule_under_the_scoring_key():
    from annotation_agreement import key_of
    bad = []
    for r in _built():
        a = key_of(r["corpus_smiles"], "inchikey_tautomer")
        b = key_of(r["previously_submitted_smiles"], "inchikey_tautomer")
        if a is None or a != b:
            bad.append((r["id"], a, b))
    assert not bad, (
        "the corpus form and the form submitted before are not the same molecule under the key "
        f"the scoring joins on, so a returned prediction could not be scored: {bad[:3]}")


def test_every_row_is_a_structure_a_service_can_read():
    from rdkit import Chem
    unreadable = [r["id"] for r in _built() if Chem.MolFromSmiles(r["corpus_smiles"]) is None]
    assert not unreadable, (
        "a row carries a corpus string RDKit cannot parse, so the submission file would carry a "
        f"structure the service will reject: {unreadable[:5]}")


def test_the_manifest_counts_what_the_files_carry():
    m = OUT / "manifest.json"
    if not m.exists():
        pytest.skip("no manifest")
    man = json.loads(m.read_text())
    rows = _built()
    assert man["n_substrates"] == len(rows), (
        f"the manifest says {man['n_substrates']} substrates and the map carries {len(rows)}")
    smi = (OUT / "substrates.smi").read_text().strip().splitlines()
    assert len(smi) == len(rows), (
        f"the SMILES file carries {len(smi)} lines against {len(rows)} rows, so one of the two "
        f"silently lost a substrate")
    for pop, n in man["by_population"].items():
        assert n == sum(1 for r in rows if r["population"] == pop), (
            f"the manifest's count for {pop} is not what the map carries")
