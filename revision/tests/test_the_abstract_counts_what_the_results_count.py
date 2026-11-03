"""Two places report the same quantity, so they must cite the same macro.

Run: python -m pytest revision/tests/test_the_abstract_counts_what_the_results_count.py -q

The criterion sweep produces two counts that are easy to mistake for one another: the budgets at
which the VERDICT moves among the defensible criteria, and the budgets at which the MARGIN
changes sign among them. On the comparison set both were one and nothing distinguished them. On
the whole evaluated test set the first is one and the second is two, and the abstract was citing
the second while the Results cited the first, so the paper said a verdict moved at two budgets in
one place and at one budget in the other.

Both numbers were generated, both were correct, and the sentence picked the wrong one. A reader
cannot catch that and neither can a gate that checks a macro is defined. What catches it is
asking whether the two sentences that report one quantity cite one macro.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

DOCS = (ROOT / "paper2" / "grail_jcim.tex", ROOT / "paper2" / "body.tex")
# A sentence reporting how many budgets the matching criterion moves a verdict at. Both
# spellings the two documents use, matched on the claim rather than on either wording.
VERDICT_CLAIM = re.compile(
    r"(?:the verdict is stable, moving at|criterion moves a verdict at)\s*(\\num\w+)", re.I)


def _cited():
    out = {}
    for d in DOCS:
        if not d.exists():
            continue
        for m in VERDICT_CLAIM.finditer(" ".join(d.read_text().split())):
            out.setdefault(m.group(1), []).append(d.name)
    return out


def test_the_claim_is_found_in_both_documents():
    """Guards the pattern: a check that matches nothing passes by finding nothing."""
    cited = _cited()
    files = {f for v in cited.values() for f in v}
    assert files >= {"grail_jcim.tex", "body.tex"}, (
        f"the verdict-movement claim was found in {sorted(files)}; this check only means "
        f"something when it finds the claim in both the abstract and the Results")


def test_both_documents_cite_one_macro_for_it():
    cited = _cited()
    assert len(cited) == 1, (
        "the abstract and the Results report how many budgets the criterion moves a verdict at "
        "and cite different macros for it: "
        + "; ".join(f"{k} in {sorted(set(v))}" for k, v in sorted(cited.items())))


def test_the_two_counts_it_could_cite_are_different_numbers_here():
    """Otherwise the test above is satisfied by a coincidence rather than by agreement."""
    p = ROOT / "results" / "paper2_numbers.json"
    if not p.exists():
        pytest.skip("results/paper2_numbers.json is not in this checkout")
    n = json.loads(p.read_text())["numbers"]
    moved, signs = n.get("crit.defensible_moved"), n.get("crit.defensible.signchanges")
    assert moved is not None and signs is not None
    if moved == signs:
        pytest.skip(
            f"the verdict count and the sign-change count are both {moved} on this population, "
            f"so citing either gives the same sentence and the check above cannot discriminate")
    assert moved != signs


def test_the_claim_cites_the_verdict_count_and_not_the_sign_count():
    cited = _cited()
    assert set(cited) == {"\\numCritDefensibleMovedWord"}, (
        "the sentence says a verdict moves, so it has to cite the count of budgets at which the "
        "verdict moves. The count of budgets at which the margin changes sign is a different "
        f"quantity and a different number here. Cited: {sorted(cited)}")
