"""The negation counter, driven on cases whose answer is known before it runs.

Run: python -m pytest revision/tests/test_the_negation_counter_counts_negations.py -q

A referee read the manuscript and reported that 44% of its prose sentences carry a negation, and
that the share is worst in the two sections a referee reads last. That is a measurement, and the
reply to a measurement is a measurement, not a pass of rewriting that feels better afterwards.

So the counter comes first and is driven on fixtures here. Three things can go wrong with a
counter like this and each is cheap to plant: it can miss a negation that is spelled as a word
rather than as `not`; it can fire on a word that merely contains the letters, which is how
`cannot` inside `cannot` is correct but `nothing` inside `notwithstanding` is not; and it can
count the same sentence twice when a sentence carries two.

The important one is the third. The referee reports both a share of sentences and a rate per
thousand words, and those two disagree exactly when sentences carry more than one negation, which
is the population the rewriting is aimed at. A counter that collapses them would report the pass
as finished while the doubled sentences are untouched.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture
def N():
    import negation_density as m
    return m


def test_a_plain_sentence_carries_none(N):
    assert N.negations("The bank recovers 0.8171 of known metabolites in a single step.") == []


def test_the_narrow_forms_are_found(N):
    for s, want in [
        ("The system does not lead at the tight budgets.", ["not"]),
        ("No system leads across the sweep.", ["no"]),
        ("It cannot be run as released.", ["cannot"]),
        ("The arm is never read at that budget.", ["never"]),
        ("Neither arm separates.", ["neither"]),
        ("It carries no stereochemistry, nor does it distinguish tautomers.", ["no", "nor"]),
    ]:
        assert N.negations(s) == want, (s, N.negations(s))


def test_a_word_that_merely_contains_one_is_not_counted(N):
    """`notwithstanding`, `nothing` as a noun phrase, `cannon`, `norm`, `nevertheless`."""
    for s in ("Notwithstanding the budget, the ordering holds.",
              "The cannon is irrelevant here.",
              "The norm in this literature is to report a site.",
              "Nevertheless the ordering holds."):
        assert N.negations(s) == [], (s, N.negations(s))


def test_the_broad_forms_are_separable_from_the_narrow_ones(N):
    """The referee quotes two rates. A counter that gives one of them cannot answer them both."""
    s = "The rule fails without the reactant, and the type is absent from the bank."
    assert N.negations(s) == []
    assert sorted(N.negations(s, broad=True)) == ["absent", "fails", "without"]


def test_a_sentence_with_two_is_counted_once_as_a_sentence_and_twice_as_a_rate(N):
    text = ("The arm does not lead. The control is not run and the population is not fixed.")
    m = N.measure(text)
    assert m["sentences"] == 2
    assert m["sentences_with_a_negation"] == 2
    assert m["sentences_with_two_or_more"] == 1
    # One denial in the first sentence and two in the second: the share says two sentences and
    # the rate says three denials, and the gap between them is the sentence worth rewriting.
    assert m["negations"] == 3, m


def test_the_measurement_refuses_an_empty_text(N):
    """A rate over no words is a number that cannot be wrong, which is the failure to avoid."""
    with pytest.raises(SystemExit):
        N.measure("   ")


def test_sections_are_read_from_the_manuscript_rather_than_named_here(N):
    """A typed section list goes stale the first time a heading is renamed."""
    body = ROOT / "paper2" / "body.tex"
    if not body.exists():
        pytest.skip("paper2/body.tex is not in this checkout")
    got = N.by_section(body.read_text())
    assert len(got) >= 5, sorted(got)
    assert all(v["words"] > 0 for v in got.values()), got
    # The counter must see the manuscript's own headings, not a list written here.
    assert "Results" in got and "Limitations" in got, sorted(got)
