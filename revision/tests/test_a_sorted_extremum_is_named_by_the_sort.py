"""A class the prose calls "the largest" must take its name from the sort, not from the author.

Run: python -m pytest revision/tests/test_a_sorted_extremum_is_named_by_the_sort.py -q

The transformation-class split was computed on the comparison set, where cleavages losing two or
more carbons carried more known metabolites than any other class and the unnamed residue came
second. The manuscript said so, by name. Moving the split to the whole evaluated test set
reordered it: one-oxygen oxidation is larger than either, and the two sentences calling cleavage
"the largest class" and the residue "the second largest" became false while every number in them
stayed correct, because the numbers were generated and the names were typed.

The value is derived and the name it belongs to is typed. That is the whole defect, and it has
appeared in this project before in another form, so the check is on the shape rather than on the
two sentences: wherever the prose ranks a class, the name beside the rank has to be the macro the
generator writes from the sort.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

BODY = ROOT / "paper2" / "body.tex"
NUMBERS = ROOT / "results" / "paper2_numbers.json"
RANK_WORDS = r"(?:largest|biggest|smallest|commonest|most common|rarest)"


def _artifact():
    sys.path.insert(0, str(ROOT / "scripts" / "typed_edit"))
    from _acs_table import HEADLINE, control_artifact

    p = ROOT / "results" / control_artifact("error_by_chemistry", HEADLINE)
    if not p.exists():
        pytest.skip(f"{p.name} is not in this checkout")
    return json.loads(p.read_text())


def _sentences(text: str):
    import check_prose_density as cpd

    return [s for b in cpd.blocks(text) for s in cpd.sentences(b)]


def test_the_generator_derives_the_name_as_well_as_the_number():
    """Without this the macro the sentences are meant to use does not exist."""
    if not NUMBERS.exists():
        pytest.skip("results/paper2_numbers.json is not in this checkout")
    n = json.loads(NUMBERS.read_text())["numbers"]
    for key in ("chem.largest.name", "chem.largest.refs", "chem.second.name"):
        assert key in n, f"{key} is not generated, so the prose has nothing to print"
    art = _artifact()
    ranked = sorted(art["classes"].items(), key=lambda kv: -kv[1]["references"])
    assert n["chem.largest.name"] == ranked[0][0], (
        f"the generator calls {n['chem.largest.name']!r} the largest class and the artifact's "
        f"largest is {ranked[0][0]!r}")
    assert n["chem.second.name"] == ranked[1][0]


def test_no_sentence_ranks_a_class_and_then_types_its_name():
    art = _artifact()
    names = sorted(art["classes"], key=len, reverse=True)
    offenders = []
    for s in _sentences(BODY.read_text()):
        if not re.search(RANK_WORDS + r"\s+class", s, re.I):
            continue
        for cls in names:
            # The artifact's own key, as prose would write it: the vocabulary spells a class
            # "cleavage, two or more carbons lost" and a sentence writes "cleavages losing two or
            # more carbons", so the test looks for the distinctive words rather than the key.
            # A key of one ordinary word, "other", is skipped: it cannot be told from the same
            # word used as English, so a detector that fired on it would fire on anything. The
            # cost is stated rather than hidden -- that one class is outside this check.
            words = [w for w in re.findall(r"[a-z]{5,}", cls.lower())]
            if len(words) < 2:
                continue
            if all(re.search(w[:-1] if w.endswith("s") else w, s, re.I) for w in words):
                offenders.append((cls, s[:110]))
                break
    assert not offenders, (
        "a sentence ranks a transformation class and names it in prose; the name has to come "
        "from \\numChemLargestName{} or \\numChemSecondName{}, which the generator writes from "
        "the sort:\n  " + "\n  ".join(f"{c}: {s}" for c, s in offenders))


def test_the_check_fires_on_the_sentence_it_was_written_for():
    """The exact sentence the whole-split move falsified, so the check cannot be vacuous."""
    art = _artifact()
    planted = ("The bank earns its size on the largest class, cleavages losing two or more "
               "carbons, where it recovers more than the best comparator.")
    names = sorted(art["classes"], key=len, reverse=True)
    hit = False
    for cls in names:
        words = [w for w in re.findall(r"[a-z]{5,}", cls.lower())]
        if len(words) < 2:
            continue
        if all(re.search(w[:-1] if w.endswith("s") else w, planted, re.I) for w in words):
            hit = True
            break
    assert hit, ("the detector does not recognise the sentence that prompted it, so a green "
                 "result above means nothing")
