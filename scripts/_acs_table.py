"""A table's title is one sentence and the rest is a footnote, which is what ACS asks for.

JCIM's guidelines say each table must have a brief, one-phrase-or-sentence title, understandable
without reference to the text, and that details belong in footnotes rather than in the title. The
tables here carried captions of 84 to 150 words and four to six sentences, which explained the
table instead of naming it.

Rewriting seven generators by hand would put the same split in seven places, so the split lives
here: the caption's first sentence stays a caption, everything after it becomes a table note, and
the whole float is wrapped in a threeparttable so the notes sit under the table body where a
reader looks for them. The label moves up beside the caption, because a label that follows
\\end{threeparttable} binds to the wrong counter and prints ?? in every reference to it.

    from _acs_table import acs_table
    return acs_table(latex)
"""
from __future__ import annotations

import re

# A full stop that ends a sentence rather than an abbreviation or a decimal. The caption text is
# ordinary prose, so the cases that matter are "exh." and "int." in the arm names, "pct." and the
# numbers, all of which are followed by a lower-case letter or a digit rather than a capital.
_SENTENCE_END = re.compile(r"(?<=[a-z0-9\)\]])\.\s+(?=[A-Z$\\])")


def _balanced(s: str, open_at: int) -> int:
    """Index just past the brace group that opens at `open_at`."""
    depth, i = 0, open_at
    while i < len(s):
        if s[i] == "{" and s[i - 1] != "\\":
            depth += 1
        elif s[i] == "}" and s[i - 1] != "\\":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError("unbalanced caption braces")


def acs_table(latex: str, extra_notes: tuple = ()) -> str:
    """Split one generated float's caption into an ACS title and its footnotes.

    `extra_notes` are appended as further \\item entries, for a generator that wants a note it
    never wrote into the caption. A float whose caption is already one sentence and that has no
    extra notes is returned unchanged, so this is safe to apply to every table.
    """
    m = re.search(r"\\caption\{", latex)
    if not m:
        return latex
    end = _balanced(latex, m.end() - 1)
    caption = latex[m.end():end - 1]

    flat = re.sub(r"\s+", " ", caption).strip()
    parts = _SENTENCE_END.split(flat, maxsplit=1)
    title, rest = parts[0].rstrip(". ") + ".", (parts[1].strip() if len(parts) > 1 else "")
    notes = ([rest] if rest else []) + [n for n in extra_notes if n]
    if not notes:
        return latex

    lm = re.search(r"\\label\{[^}]*\}\n?", latex)
    label = lm.group(0).strip() if lm else ""
    body = latex[:m.start()] + latex[end:]
    if lm:
        body = body.replace(lm.group(0), "", 1)

    # The float's opening line, then the wrapper, then the caption and label, then the tabular the
    # generator built, then the notes.
    om = re.search(r"\\begin\{table\*?\}(\[[^\]]*\])?\n", body)
    if not om:
        return latex
    head, tail = body[:om.end()], body[om.end():]
    cm = re.search(r"\\end\{table\*?\}", tail)
    if not cm:
        return latex
    inner, closing = tail[:cm.start()], tail[cm.start():]

    lead = ""
    im = re.match(r"((?:\\centering[^\n]*\n)|(?:\\centering\n))", inner)
    if im:
        lead, inner = im.group(1), inner[im.end():]

    items = "\n".join(f"\\item {n}" for n in notes)
    return (f"{head}{lead}\\begin{{threeparttable}}\n"
            f"\\caption{{{title}}}\n{label}\n"
            f"{inner.strip()}\n"
            f"\\begin{{tablenotes}}[flushleft]\\footnotesize\n{items}\n\\end{{tablenotes}}\n"
            f"\\end{{threeparttable}}\n{closing}")


import functools
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "paper2"

# The manuscript and the Supporting Information reach each other through xr: a reference from the
# Supporting Information to the manuscript carries MS-, one the other way carries SI-, and a
# reference inside one document carries nothing. Both prefixes used to be typed at the call site
# that wrote them, which made a generated table's text depend on which document it was \input
# into while nothing said so. Moving two tables out of the manuscript gave five undefined
# references in one build. The prefix is derived here now, from the documents themselves, so a
# table moved by editing one \input line is a table whose references move with it.
PREFIX = {("si", "ms"): "MS-", ("ms", "si"): "SI-"}


@functools.lru_cache(maxsize=1)
def _doc_inputs():
    r"""Which document \input{}s each generated table, read from the documents."""
    homes = {}
    for doc, tag in (("body.tex", "ms"), ("si.tex", "si")):
        src = (OUT / doc).read_text()
        for m in re.finditer(r"\\input\{([^}]+)\}", src):
            homes[m.group(1)] = tag
    return homes


@functools.lru_cache(maxsize=1)
def _label_homes():
    r"""Which document each \label{} ends up in, counting the tables through their \input."""
    out = {}
    for stem, tag in _doc_inputs().items():
        f = OUT / f"{stem}.tex"
        if f.exists():
            for m in re.finditer(r"\\label\{([^}]+)\}", f.read_text()):
                out[m.group(1)] = tag
    # The documents' own labels last, so a section heading is never shadowed by a table's.
    for doc, tag in (("body.tex", "ms"), ("si.tex", "si")):
        for m in re.finditer(r"\\label\{([^}]+)\}", (OUT / doc).read_text()):
            out[m.group(1)] = tag
    return out


def xref(label, writing):
    """``\\ref{...}`` as it must read inside the generated table named by `writing`.

    A label no document defines, and a table no document prints, are both refusals: a missing
    prefix compiles to a question mark that a reader meets and a build log reports once.
    """
    there = _label_homes().get(label)
    if there is None:
        raise SystemExit(f"no document defines \\label{{{label}}}, so the reference to it from "
                         f"{writing} cannot be given a prefix")
    here = _doc_inputs().get(writing)
    if here is None:
        raise SystemExit(f"{writing} is not \\input by either document, so the prefix its "
                         f"references need cannot be derived")
    return "\\ref{%s%s}" % (PREFIX.get((here, there), ""), label)


def wide_float(writing):
    r"""``table*`` in the manuscript and ``table`` in the Supporting Information.

    The two documents have different measures: the manuscript is two columns of about 3.3 inches
    and the Supporting Information one column of about six. A table too wide for a manuscript
    column needs ``table*`` there and does not need it here, so the environment is as
    document-dependent as the cross-reference prefix, and for the same reason it is derived. The
    precision table moved into the manuscript as ``table`` and overran its column by the width of
    four of its eight headings.
    """
    here = _doc_inputs().get(writing)
    if here is None:
        raise SystemExit(f"{writing} is not \\input by either document, so the float "
                         f"environment it needs cannot be derived")
    return "table*" if here == "ms" else "table"


# The matching criteria the manuscript defends as defaults, and therefore the rows its grid
# draws. Canonical SMILES equality is the strictest of the five and tests whether two pipelines
# standardise alike rather than whether two structures are one compound; Tanimoto of one on a
# folded fingerprint is the loosest and merges what the fingerprint cannot separate. Both are
# declared and both are swept, in the Supporting Information, because the paper's argument is
# that the choice must be declared; neither belongs in the grid a reader reads the verdict off.
#
# Defined here because the figure draws from it and the number macros count over it, and a
# roster written in two files is the defect this project has met in eleven of them.
# Which file a control writes for each evaluation population. The controls were computed on the
# comparison set and moved to the whole evaluated test set, and the producers, the figures and the
# number generator each named the file themselves. That is how a figure came to draw one
# population while the sentence beside it was read from another, so the suffix is decided here and
# every one of them asks.
CONTROL_SUFFIX = {"comparison": "", "whole": "_1170"}


# The population the manuscript reads a control AT. Both are produced; this says which one the
# figures, the macros and the main tables quote, and a call site that deliberately wants the
# other says so by naming it, which is the only way the two can be told apart on sight.
HEADLINE = "whole"


def control_artifact(stem: str, population: str) -> str:
    """`<stem>.json` for the comparison set, `<stem>_1170.json` for the whole evaluated split."""
    if population not in CONTROL_SUFFIX:
        raise SystemExit(
            f"no evaluation population named {population!r}; the populations are "
            f"{sorted(CONTROL_SUFFIX)}")
    return f"{stem}{CONTROL_SUFFIX[population]}.json"


DEFENSIBLE = ("inchikey", "inchi_no_stereo", "inchikey_tautomer")
