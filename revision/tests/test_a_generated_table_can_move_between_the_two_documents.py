"""A generated table's cross-references follow the document it is placed in.

Run: python -m pytest revision/tests/test_a_generated_table_can_move_between_the_two_documents.py -q

The manuscript and the Supporting Information reach each other through xr: a reference from the
Supporting Information to the manuscript carries MS- and one the other way carries SI-, while a
reference inside one document carries no prefix at all. Every generated table writes its own
references, and each prefix was typed at the call site that wrote it.

That makes a table's text depend on which document it happens to be \\input into, and nothing said
so. Moving two tables out of the manuscript -- their figures now carry the shape and the tables
carry only the levels, so they belong with the detail -- produced five undefined references at
once: a table in the Supporting Information still pointing at MS-tab:si-matched, another still
pointing at SI-sec:si-matched from inside the very document that defines sec:si-matched. The build
caught them, and the move would otherwise have been reverted as too expensive, which is how a
manuscript becomes unshortenable.

So the prefix is derived rather than typed, and from the documents themselves: which table each
document \\input{}s, and which file defines each \\label{}. Nothing here is a list anyone maintains,
so a table moved by editing one \\input line is a table whose references move with it. The last
test is the one that matters -- it moves a table in a scratch copy of the documents and requires
every prefix in it to flip.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
PAPER = ROOT / "paper2"

pytestmark = pytest.mark.skipif(not (PAPER / "si.tex").exists(),
                                reason="paper2/si.tex is not in this checkout")


@pytest.fixture
def gen():
    """The module that owns the resolver, which is not the module that first used it.

    `xref` started in the Supporting Information generator and moved to `_acs_table` when the
    manuscript's own generator needed it too. Reaching for it through whichever generator
    happens to import it is how this fixture broke on that move, so it reaches for the owner.
    """
    import _acs_table as mod
    assert hasattr(mod, "xref") and hasattr(mod, "OUT"), (
        "_acs_table no longer owns the cross-document resolver; this fixture is pointed at the "
        "wrong module and every assertion below it is testing something else")
    for name in ("xref", "_doc_inputs", "_label_homes"):
        fn = getattr(mod, name, None)
        if fn is not None and hasattr(fn, "cache_clear"):
            fn.cache_clear()
    return mod


@pytest.fixture
def inventory():
    """The list of generated tables, which stayed in the Supporting Information generator."""
    import paper2_si_tables as mod
    assert hasattr(mod, "generators"), (
        "paper2_si_tables no longer lists the generated tables; this fixture is pointed at the "
        "wrong module")
    return mod


def test_a_reference_inside_one_document_carries_no_prefix(gen):
    # si_table_matched now lives in the Supporting Information, and so does sec:si-matched.
    assert gen.xref("sec:si-matched", "si_table_matched") == "\\ref{sec:si-matched}"


def test_a_reference_across_the_boundary_carries_the_other_document_s_prefix(gen):
    # tab:sweep is printed in the manuscript; a Supporting Information table reaching it needs MS-.
    assert gen.xref("tab:sweep", "si_table_matched") == "\\ref{MS-tab:sweep}"


def test_a_label_no_document_defines_is_a_refusal_and_not_a_blank_reference(gen):
    with pytest.raises(SystemExit) as e:
        gen.xref("tab:no-such-thing-anywhere", "si_table_matched")
    assert "tab:no-such-thing-anywhere" in str(e.value)


def test_a_table_no_document_inputs_is_a_refusal(gen):
    with pytest.raises(SystemExit) as e:
        gen.xref("tab:sweep", "si_table_nobody_inputs_this")
    assert "si_table_nobody_inputs_this" in str(e.value)


def test_every_generated_table_is_input_by_exactly_one_document(inventory):
    """Two documents \\input{}ing one table would print it twice under one label."""
    seen = {}
    for doc in ("body.tex", "si.tex"):
        for m in re.finditer(r"\\input\{([^}]+)\}", (PAPER / doc).read_text()):
            seen.setdefault(m.group(1), []).append(doc)
    both = {k: v for k, v in seen.items() if len(v) > 1}
    assert not both, f"a table is \\input by both documents: {both}"
    for stem, fn in inventory.generators():
        assert stem in seen, (
            f"{stem} is generated and neither document \\input{{}}s it, so it is written on every "
            f"build and printed nowhere")


def test_moving_a_table_moves_its_prefixes(gen, inventory, tmp_path, monkeypatch):
    """The perturbation. A typed prefix passes every test above and fails this one."""
    moved = "si_table_matched"
    for doc in ("body.tex", "si.tex"):
        (tmp_path / doc).write_text((PAPER / doc).read_text())
    for stem, _ in inventory.generators():
        src = PAPER / f"{stem}.tex"
        if src.exists():
            (tmp_path / f"{stem}.tex").write_text(src.read_text())

    before = gen.xref("sec:si-matched", moved)
    # Take the table out of the Supporting Information and put it in the manuscript.
    s = (tmp_path / "si.tex").read_text().replace("\\input{%s}\n" % moved, "")
    (tmp_path / "si.tex").write_text(s)
    b = (tmp_path / "body.tex").read_text()
    (tmp_path / "body.tex").write_text(b.replace("\\input{table_sweep}",
                                                 "\\input{table_sweep}\n\\input{%s}" % moved, 1))
    monkeypatch.setattr(gen, "OUT", tmp_path)
    for name in ("_doc_inputs", "_label_homes"):
        getattr(gen, name).cache_clear()

    after = gen.xref("sec:si-matched", moved)
    assert before == "\\ref{sec:si-matched}", before
    assert after == "\\ref{SI-sec:si-matched}", (
        "the table moved to the manuscript and its reference to a Supporting Information section "
        "did not acquire the SI- prefix, so the prefix is typed rather than derived")
