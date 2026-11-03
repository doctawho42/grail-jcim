"""A note typed into an artifact may not contradict the artifact's own measured keys.

Run: python -m pytest revision/tests/test_a_typed_note_does_not_contradict_the_keys_beside_it.py -q

results/population_definition.json carried a field reading "the exhaustive arm was built on the
comparison set only, so the whole-test-set row carries the deployed interactive arm and not it".
Two keys further down, the same artifact printed arms_present as ["deployed", "exhaustive"] and
a full grail_exhaustive_recall curve over the 1170 substrates of the whole evaluated test set. The
note was a string typed into the producer; the curve was measured by it. They disagreed, and the
string was the one a reader met.

What it cost was not the field. A reviewer asked for the headline comparison to move onto the
whole evaluated split and expected the answer to be that the table does not exist. The table did
exist -- nine arms, nine budgets, every comparator present -- and this note is what a reader of
the repository would have found instead. A sentence that says a measurement cannot be made, next
to the measurement, is worse than no sentence: it is a reason not to look.

So a note of that kind is derived from the keys it is about, and this test fails when a typed one
reappears. It checks the artifact rather than the producer, because the producer can be rewritten
to compute the same wrong string.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "results/population_definition.json"

pytestmark = pytest.mark.skipif(not ART.exists(),
                                reason="population_definition.json is not in this checkout")

# The words a note uses to say an arm is not there. Matched against the note, not the data.
ABSENT = re.compile(r"\b(?:not it|absent|was not run|only the deployed|and not it)\b", re.I)


def _whole(d):
    return d["contrasts"]["the whole evaluated test set"]


def test_the_arms_the_note_describes_are_the_arms_the_artifact_measured():
    d = json.loads(ART.read_text())
    whole = _whole(d)
    present = set(whole["arms_present"])
    note = str(d.get("absent_arm", ""))
    measured = {a for a in ("deployed", "exhaustive") if f"grail_{a}_recall" in whole}
    assert measured == present, (
        f"the artifact's arms_present is {sorted(present)} and the recall curves it carries are "
        f"for {sorted(measured)}; one of the two is wrong before any note is read")
    if "exhaustive" in present:
        assert not ABSENT.search(note), (
            "the artifact measures the exhaustive arm over the whole evaluated test set and a "
            "typed note beside it says the arm is not there: " + note)


def test_the_note_names_what_it_is_about_rather_than_asserting_an_absence():
    """A note that cannot be checked against a key is a note nobody can falsify."""
    d = json.loads(ART.read_text())
    note = str(d.get("absent_arm", ""))
    assert note, "the field is gone; if it was renamed, point this test at the new name"
    whole = _whole(d)
    named = [a for a in ("deployed", "exhaustive") if a in note.lower()]
    assert named, f"the note names no arm, so no key can check it: {note}"
    for a in named:
        assert a in whole["arms_present"] or f"grail_{a}_recall" not in whole, (
            f"the note names {a} and the artifact's keys disagree about whether it is measured")


def test_the_whole_split_curves_cover_every_budget_the_comparison_set_does():
    """The other half of the same claim: a population is not secondary for carrying fewer cells."""
    d = json.loads(ART.read_text())
    whole = _whole(d)
    ks = {tuple(sorted(map(int, whole[f"grail_{a}_recall"])))
          for a in ("deployed", "exhaustive") if f"grail_{a}_recall" in whole}
    assert len(ks) == 1, f"the two arms are reported at different budgets on the whole split: {ks}"
    comparators = [k for k, v in whole.items() if isinstance(v, dict) and "recall" in v]
    assert comparators, "the whole-split block carries no comparator"
    for c in comparators:
        got = tuple(sorted(map(int, whole[c]["recall"])))
        assert got == next(iter(ks)), (
            f"{c} is reported at {got} on the whole split and the arms at {next(iter(ks))}, so a "
            f"contrast there cannot be read across the arms")
