"""A transcription step is an instrument, and this one has to be measured on a known case first.

Run: python -m pytest revision/tests/test_the_transcription_instrument_is_measured_before_it_is_trusted.py -q

The external set's structures exist only as drawings, so something has to read them. Whatever
does, machine or chemist, is an instrument whose error rate decides what the external number
means, and this repository's own history is of probes that answered confidently and wrongly. So
the calibration is scored against an answer key on published metabolites already held here, and
the properties asserted below are the ones that make the score mean something:

a perfect submission scores one at every criterion, so a zero elsewhere is about the recogniser;
replacing one structure drops the rate and names the row, so the score reads its input;
a stereochemistry-only error is right under the default criterion and wrong under the strictest,
which is the asymmetry that decides how much a misread costs this work;
a submission about images the key does not hold is refused rather than scored;
and the key is not inside the directory the recogniser is given.
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
    spec = importlib.util.spec_from_file_location("_ocsr", ROOT / "scripts" / "ocsr_calibration.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["_ocsr"] = m
    spec.loader.exec_module(m)
    return m


OCSR = _mod()
pytestmark = pytest.mark.skipif(not OCSR.KEY.exists(),
                                reason="the calibration key is not in this checkout")


def _key() -> dict:
    return json.loads(OCSR.KEY.read_text())["key"]


def _submit(tmp_path: Path, rows: dict) -> Path:
    p = tmp_path / "submission.csv"
    with p.open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["image", "smiles"])
        for name, smiles in sorted(rows.items()):
            w.writerow([f"{name}.png", smiles])
    return p


def test_a_perfect_submission_scores_one_everywhere(tmp_path):
    key = _key()
    out = OCSR.score(_submit(tmp_path, {n: v["smiles"] for n, v in key.items()}),
                     out=tmp_path / "scored.json")
    assert out["n_answered"] == len(key)
    for c, v in out["by_criterion"].items():
        assert v["rate"] == 1.0, f"{c} scores {v['rate']} on the key itself"
    assert out["misread"] == []


def test_one_wrong_structure_moves_the_rate_and_is_named(tmp_path):
    key = _key()
    rows = {n: v["smiles"] for n, v in key.items()}
    victim = sorted(rows)[0]
    rows[victim] = "c1ccccc1"  # benzene, which none of these metabolites is
    out = OCSR.score(_submit(tmp_path, rows), out=tmp_path / "scored.json")
    assert out["by_criterion"]["inchikey_tautomer"]["rate"] < 1.0
    assert [m["image"] for m in out["misread"]] == [victim]
    assert out["misread"][0]["formula_agrees"] is False


def test_a_stereochemistry_only_misread_is_seen_by_one_criterion_and_no_other(tmp_path):
    """The failure this class of model makes most often, priced under each criterion.

    The expectation written here first was that canonical SMILES, the strictest of the five, would
    catch an inverted stereocentre. It does not: every criterion goes through the project's
    standardiser, which canonicalises tautomers and writes SMILES with isomericSmiles=False, so
    stereochemistry is gone before the key is taken. Of the five declared criteria the full
    InChIKey is the only one whose key moves, which is what makes a transcription error of this
    kind cheap for this work and would not be true of a paper matching on full InChIKeys.
    """
    key = _key()
    rows = {n: v["smiles"] for n, v in key.items()}
    victim = next((n for n, v in sorted(key.items()) if "@" in v["smiles"]), None)
    assert victim, "no reference in the key carries a stereocentre, so this cannot be tested"
    rows[victim] = key[victim]["smiles"].replace("@@", "@").replace("[C@]", "[C@@]")
    out = OCSR.score(_submit(tmp_path, rows), out=tmp_path / "scored.json")
    assert out["by_criterion"]["inchikey"]["rate"] < 1.0, (
        "the full InChIKey did not notice a changed stereocentre, so nothing in the grid reads "
        "stereochemistry and a misread of it could not be priced at all")
    for c in ("inchikey_tautomer", "inchi_no_stereo", "canonical"):
        assert out["by_criterion"][c]["rate"] == 1.0, (
            f"{c} moved on a stereochemistry-only difference; either the perturbation changed "
            f"something else or that criterion is no longer reading through the standardiser")
    assert out["by_criterion"]["formula"]["rate"] == 1.0


def test_a_submission_about_other_images_is_refused(tmp_path):
    rows = {"img_not_in_the_key": "CCO"}
    with pytest.raises(SystemExit):
        OCSR.score(_submit(tmp_path, rows))


def test_the_answer_key_is_not_in_the_directory_the_recogniser_is_given():
    assert OCSR.KEY.parent == OCSR.HOME and OCSR.IMAGES.parent == OCSR.HOME
    assert OCSR.KEY.parent != OCSR.IMAGES, "the key sits beside the images a recogniser reads"
    assert not list(OCSR.IMAGES.glob("*.json")), (
        "a JSON file is in the image directory; if it is the key, every rate below is about a "
        "recogniser that could read its own answers")


def test_the_image_names_carry_no_structure():
    key = _key()
    for name, v in sorted(key.items())[:50]:
        assert name == OCSR.image_id(v["smiles"], v["style"]), f"{name} is not its own digest"
        assert "InChI" not in name and "=" not in name and len(name) <= 20


def test_scoring_in_a_test_leaves_no_rate_in_the_results_directory(tmp_path):
    """A test scores a submission it built itself, which is a measurement of nothing.

    The default destination is the one the command writes to. While a test used it, every run of
    this suite left a file in results/ whose rate came from a submission copied out of the answer
    key, and the artifact audit counted that file among the measurements.
    """
    before = OCSR.OUT.read_bytes() if OCSR.OUT.exists() else None
    key = _key()
    OCSR.score(_submit(tmp_path, {n: v["smiles"] for n, v in key.items()}),
               out=tmp_path / "scored.json")
    assert (tmp_path / "scored.json").exists(), "the destination given was not written"
    after = OCSR.OUT.read_bytes() if OCSR.OUT.exists() else None
    assert after == before, f"{OCSR.OUT.name} was written by a test that was given another path"
