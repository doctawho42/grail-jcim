"""The benchmark's own summary table is the answer key for reading its per-drug tables.

Run: python -m pytest revision/tests/test_the_published_tables_reproduce_their_own_recall.py -q

The external set's metabolites are published as drawings inside tables, one table per drug, with a
pathway in text and a column per model carrying an X where that model predicted the row. Reading
those tables out of the document is a transcription step, and this repository's standing problem
with transcription is that a wrong reading answers confidently.

Here it does not have to. The same document prints, in Table S12, the recall of each model on each
drug. Recall is hits over published metabolites, so a mark matrix read out of the per-drug tables
predicts every cell of that summary. If the reading is wrong anywhere -- a row missed, a mark put
in the wrong column, a parent counted as a metabolite -- the arithmetic stops agreeing. That is
asserted below for every drug and every model, and it is the reason this extraction may be
trusted where the structures themselves may not.

The other assertions are about what the tables do not contain. Some rows are not structures: they
carry the parent skeleton with a bracket and a token such as -2H or 2O, which says a modification
of that mass happened somewhere in that region and not where. Those rows have no single structure
to read, and calling them read would be inventing the position.
"""
from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _mod():
    spec = importlib.util.spec_from_file_location(
        "_gao", ROOT / "scripts" / "typed_edit" / "gao_si_tables.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["_gao"] = m
    spec.loader.exec_module(m)
    return m


GAO = _mod()
pytestmark = pytest.mark.skipif(not GAO.SI.exists(), reason="the publisher's SI is not in this checkout")


def _published() -> dict:
    with (ROOT / "revision" / "gao2026_reference_set" / "substrates.csv").open() as fh:
        return {r["drug"]: int(r["metabolites_published"]) for r in csv.DictReader(fh)}


def test_the_tables_cover_every_drug_the_summary_scores_but_one_and_name_it():
    got = GAO.extract()
    scored = set(GAO.recall_printed())
    covered = {t["drug"] for t in got["tables"]}
    assert covered < scored, "the per-drug tables cover drugs the summary does not score"
    assert set(got["scored_without_a_table"]) == scored - covered, (
        "the artifact does not name the drugs the summary scores and the tables do not carry")
    assert got["scored_without_a_table"], (
        "every scored drug has a table, which contradicts the summary having one more column")


def test_every_table_reproduces_the_recall_the_summary_prints():
    got = GAO.extract()
    printed = GAO.recall_printed()
    bad = GAO.disagreements(got["tables"], printed)
    assert bad == [], "the mark matrix read out of the tables does not predict Table S12:\n  " + \
                      "\n  ".join(bad)


def test_the_row_counts_are_the_ones_the_reference_set_was_built_from():
    got = GAO.extract()
    want = _published()
    for t in got["tables"]:
        n = sum(1 for r in t["rows"] if not r["is_parent"])
        assert n == want[t["drug"]], (
            f"{t['drug']}: {n} metabolite rows read, {want[t['drug']]} published by the summary's "
            f"own denominator")


def test_the_parent_row_is_read_as_the_parent_and_not_as_a_metabolite():
    got = GAO.extract()
    for t in got["tables"]:
        parents = [r for r in t["rows"] if r["is_parent"]]
        assert len(parents) == 1, f"{t['drug']} has {len(parents)} parent rows"
        assert parents[0]["pathway"] in ("-", ""), parents[0]["pathway"]
        assert not any(parents[0]["marks"].values()), "a model is marked as predicting the parent"


def test_a_row_carrying_a_shorthand_token_is_not_called_a_structure():
    assert GAO.is_shorthand(["F", "HN", "-2H", "O", "2O", "N", "NH"])
    assert GAO.is_shorthand(["F", "GluA", "O", "N"])
    assert not GAO.is_shorthand(["F", "HN", "O", "N", "N", "NH", "HO"]), (
        "a cell of plain element labels was called shorthand, so the count of readable rows is "
        "an undercount")


def test_the_three_verdicts_exhaust_the_metabolites():
    got = GAO.extract()
    mets = [r for t in got["tables"] for r in t["rows"] if not r["is_parent"]]
    assert got["n_metabolites"] == len(mets)
    assert sum(got["by_verdict"].values()) == got["n_metabolites"]
    assert got["by_verdict"][GAO.NOT_A_STRUCTURE] > 0, (
        "no row was read as a change in a marked region, though the document draws them")
    assert len(got["disputed"]) == got["by_verdict"][GAO.DISPUTED], (
        "the artifact counts rows the two signals disagree on without listing them, so nobody "
        "can look at the rows it is asking to have looked at")


def _rows_on(page: int) -> dict:
    got = GAO.extract()
    return {r["id"]: r for t in got["tables"] for r in t["rows"] if r["page"] == page}


def test_the_two_signals_agree_with_the_page_that_was_read_by_eye():
    """Table S2, whose nine rows were looked at before any detector was written.

    Four of them draw a finished structure and four carry a bracket with a token; the parent
    draws the drug. If a detector disagrees here it is wrong, whatever it does elsewhere.
    """
    rows = _rows_on(9)
    for ident in ("M2", "M1", "M10"):
        assert rows[ident]["verdict"] == GAO.READABLE, f"{ident} is drawn in full"
    for ident in ("M3", "M5", "M4", "M25", "M8"):
        assert rows[ident]["verdict"] == GAO.NOT_A_STRUCTURE, (
            f"{ident} carries a bracket and a token and is not one structure")


def test_a_hashed_stereo_bond_is_not_read_as_a_bracket():
    """Table S3's first page, whose six rows are finished structures with hashed stereocentres.

    The detector written before this test counted short horizontal segments, which a hashed bond
    is made of, and called all six of these unreadable. A square bracket is a tall vertical with
    a tick at each end; a hash is neither.
    """
    rows = _rows_on(11)
    mets = [r for r in rows.values() if not r["is_parent"]]
    assert len(mets) == 6, f"{len(mets)} rows read from the page, not the six it carries"
    for r in mets:
        assert r["scoping"] == {"brackets": 0, "dashed": 0}, (
            f"{r['id']} was read as carrying a scoping mark; the page draws none")
        assert r["verdict"] == GAO.READABLE, r["id"]
