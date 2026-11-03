#!/usr/bin/env python3
"""The external benchmark's tables, read out of its Supporting Information and checked against it.

The radiolabelled human ADME benchmark publishes its known metabolites as drawings inside a table
per drug, and that is the reason no measurement in this work is external. Reading those tables is a
transcription step, and transcription here has a history of answering confidently and wrongly.

This one does not have to be trusted. The same document prints, in Table S12, the recall of each
model on each drug, and recall is hits over published metabolites. So a mark matrix read out of the
per-drug tables predicts all fifty cells of that summary: a missed row, a mark landing in the wrong
column, a parent counted as a metabolite, and the arithmetic stops agreeing. The producer refuses
to write when it does not.

What comes out is everything the tables hold except the structures: the row identifier, the
biotransformation pathway, which of the five models predicted the row, and the labels inside the
drawing. The structures themselves are drawn and are left to a chemist.

The labels are reported because they decide how much of this set is readable at all. Some rows do
not draw a structure: they draw the parent skeleton with a bracket and a token such as -2H or 2O,
which states that a change of that mass happened somewhere in that region and not where it
happened. There is no single structure to read off those, and reading one would be inventing the
position. Others abbreviate an attached group -- GluA, GSH -- which is recoverable if the bond to
it is drawn. Both are counted, and counted apart, because they are different jobs.

    python scripts/typed_edit/gao_si_tables.py
    python scripts/typed_edit/gao_si_tables.py --check   # verify against Table S12, write nothing
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for _p in (str(ROOT), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _provenance import record_inputs, stamp  # noqa: E402

HOME = ROOT / "revision" / "gao2026_reference_set"
SI = HOME / "ci5c03045_si_001.pdf"
OUT = HOME / "si_tables.json"

CAPTION = re.compile(r"Table S(\d+)\s*([A-Za-z0-9\-]+)\s*metabolite prediction")
SUMMARY_PAGE = 27          # zero-based; Table S12, the recall the extraction is checked against
MODELS = ["SM", "GX", "BT", "MP", "MT"]

# The caption of Table S6 spells the drug differently from every other place the document names it,
# including the summary this extraction is checked against. It is recorded rather than silently
# mapped, as the deposit's Fovinaciclib/FCN-437c pairing is recorded in this directory's README.
SPELLING = {"Isavuconazoium": "Isavuconazole"}

# A label in a Structure cell that is not an element or a drawn group. Collected from the document
# -- every distinct label in the Structure column of the ten tables was listed before this set was
# written -- and split by what it costs a reader. A count of atoms gained or lost states a mass and
# withholds a position; a named group is a structure written short.
UNPLACED = re.compile(r"^[+-]?\d+[A-Z][a-z]?$")
ABBREVIATED = {"GluA", "GSH", "Cys", "SO3"}


# The two signals a row carries about whether it draws one structure: a label the document only
# uses when it is withholding something, and a mark that scopes a change to a region. They are
# independent, so where they agree the row is settled and where they do not it is a row for a
# chemist to look at. Nothing here guesses which signal is right.
READABLE = "drawn as one structure"
NOT_A_STRUCTURE = "a change of stated mass somewhere in a marked region"
DISPUTED = "one signal only, to be looked at"


def verdict(has_token: bool, scoped: bool) -> str:
    if has_token and scoped:
        return NOT_A_STRUCTURE
    if not has_token and not scoped:
        return READABLE
    return DISPUTED


def _merged(intervals: list) -> float:
    """Total length covered by a set of intervals, overlaps counted once."""
    out, cur = 0.0, None
    for a, b in sorted(intervals):
        if cur and a <= cur[1] + 1:
            cur = (cur[0], max(cur[1], b))
        else:
            if cur:
                out += cur[1] - cur[0]
            cur = (a, b)
    if cur:
        out += cur[1] - cur[0]
    return out


def grid(page, below: float = 0.0) -> tuple:
    """A table's column and row boundaries, told apart from the bonds drawn inside it.

    Row boundaries are the wide horizontal rules. Columns are not simply the tall vertical lines:
    a large molecule draws bonds taller than a short row, and on two pages that let a bond stand in
    for a column boundary and shifted every mark one cell to the right. A column separator is the
    line that runs the height of the whole table, so the test is coverage, and it separates
    cleanly -- every table page gives exactly nine columns with nothing in between.
    """
    rows = sorted({round(l["top"], 1) for l in page.lines
                   if abs(l["top"] - l["bottom"]) < 0.6 and abs(l["x1"] - l["x0"]) > 300
                   and l["top"] > below})
    if len(rows) < 2:
        return [], []
    top, bot = rows[0], rows[-1]
    spans = collections.defaultdict(list)
    for l in page.lines:
        if abs(l["x0"] - l["x1"]) < 0.6 and l["bottom"] > top - 1 and l["top"] < bot + 1:
            spans[round(l["x0"], 1)].append((max(l["top"], top), min(l["bottom"], bot)))
    cols = sorted(x for x, v in spans.items() if _merged(v) / (bot - top) >= 0.8)
    return cols, rows


def is_shorthand(labels: list) -> bool:
    """Whether a Structure cell states something other than a structure."""
    return bool(shorthand_tokens(labels))


def shorthand_tokens(labels: list) -> list:
    return sorted({t for t in labels if UNPLACED.match(t) or t in ABBREVIATED})


def _why(tokens: list) -> str:
    unplaced = [t for t in tokens if UNPLACED.match(t)]
    named = [t for t in tokens if t in ABBREVIATED]
    both = []
    if unplaced:
        both.append("position not stated")
    if named:
        both.append("group abbreviated")
    return " and ".join(both)


def scoping(objs: list) -> dict:
    """The marks this document uses to say a change happened somewhere in a region.

    Two notations, and they are counted rather than inferred from the labels. A square bracket is
    a tall vertical with a short horizontal at each of its two ends, on the same side; the first
    detector written here counted short horizontals alone and fired on every hashed stereo bond,
    which would have called six fully drawn structures unreadable. A dashed box is drawn as a
    dashed curve and nothing else in these cells is dashed.
    """
    tall = [o for o in objs if abs(o["x0"] - o["x1"]) < 0.6 and abs(o["bottom"] - o["top"]) > 12]
    ticks = [o for o in objs if abs(o["top"] - o["bottom"]) < 0.6 and abs(o["x1"] - o["x0"]) < 6]
    n = 0
    for v in tall:
        x, t, b = v["x0"], v["top"], v["bottom"]
        def tick_at(y):
            return any(abs(h["top"] - y) < 1.0 and min(abs(h["x0"] - x), abs(h["x1"] - x)) < 1.0
                       for h in ticks)
        if tick_at(t) and tick_at(b):
            n += 1
    return {"brackets": n, "dashed": sum(1 for o in objs if o.get("dash"))}


def _open():
    try:
        import pdfplumber
    except ImportError:
        raise SystemExit("REFUSING: pdfplumber is not installed, and the tables cannot be read "
                         "without it")
    if not SI.exists():
        raise SystemExit(
            f"REFUSING: the benchmark's Supporting Information is not at {SI.relative_to(ROOT)}. "
            f"It is the publisher's file and is not carried here; fetch it from "
            f"doi:10.1021/acs.jcim.5c03045 and put it at that path.")
    return pdfplumber.open(SI)


def recall_printed() -> dict:
    """Table S12, the recall this document prints for every model on every drug."""
    with _open() as pdf:
        page = pdf.pages[SUMMARY_PAGE]
        cols, rows = grid(page)
        words = page.extract_words()
        grid_rows = []
        for a, z in zip(rows, rows[1:]):
            grid_rows.append(["".join(
                w["text"] for w in sorted(
                    (w for w in words
                     if cols[j] <= (w["x0"] + w["x1"]) / 2 < cols[j + 1]
                     and a <= (w["top"] + w["bottom"]) / 2 < z),
                    key=lambda w: (w["top"], w["x0"])))
                for j in range(len(cols) - 1)])
    if not grid_rows:
        raise SystemExit("REFUSING: Table S12 did not parse, so the extraction has nothing to be "
                         "checked against")
    header, printed = grid_rows[0], {}
    for row in grid_rows[1:]:
        if row[0] not in MODELS:
            continue
        for drug, value in zip(header[1:], row[1:]):
            printed.setdefault(drug, {})[row[0]] = float(value)
    return printed


def extract() -> dict:
    """Every per-drug table, with the structures left where they are."""
    tables, order = {}, []
    with _open() as pdf:
        for i, page in enumerate(pdf.pages):
            text = " ".join((page.extract_text() or "").split())
            found = CAPTION.search(text)
            if not found:
                continue
            caption = found.group(2)
            drug = SPELLING.get(caption, caption)
            marker = [w for w in page.extract_words() if w["text"] == "Table"]
            cols, rows = grid(page, min(w["top"] for w in marker) if marker else 0.0)
            if len(cols) != 9:
                raise SystemExit(
                    f"REFUSING: page {i + 1} gave {len(cols)} column boundaries, not the nine "
                    f"these tables have, so every cell read from it would be in the wrong column")
            words = page.extract_words()
            shapes = list(page.lines) + list(page.rects) + list(page.curves)
            if drug not in tables:
                tables[drug] = {"drug": drug, "caption_spelling": caption,
                                "table": f"S{found.group(1)}", "pages": [], "rows": []}
                order.append(drug)
            tables[drug]["pages"].append(i + 1)
            for a, z in zip(rows, rows[1:]):
                def cell(lo, hi):
                    return [w["text"] for w in words
                            if lo <= (w["x0"] + w["x1"]) / 2 < hi
                            and a <= (w["top"] + w["bottom"]) / 2 < z]
                ident = " ".join(cell(cols[0], cols[1]))
                if not ident.strip() or ident.startswith("Compound"):
                    continue
                pathway = " ".join(cell(cols[1], cols[2]))
                labels = cell(cols[2], cols[3])
                tokens = shorthand_tokens(labels)
                marks = scoping([o for o in shapes
                                 if a <= (o["top"] + o["bottom"]) / 2 < z
                                 and cols[2] <= (o["x0"] + o["x1"]) / 2 < cols[3]
                                 and min(abs(o["x0"] - cols[2]), abs(o["x0"] - cols[3])) > 1.5])
                scoped = marks["brackets"] > 0 or marks["dashed"] > 0
                tables[drug]["rows"].append({
                    "id": ident,
                    "pathway": pathway,
                    "is_parent": pathway.strip() in ("-", ""),
                    "marks": {MODELS[j - 3]: ("X" in " ".join(cell(cols[j], cols[j + 1])))
                              for j in range(3, 8)},
                    "labels": labels,
                    "shorthand": tokens,
                    "why_not_a_structure": _why(tokens),
                    "scoping": marks,
                    "scoped": scoped,
                    "verdict": verdict(bool(tokens), scoped),
                    "page": i + 1,
                })

    printed = recall_printed()
    mets = [r for d in order for r in tables[d]["rows"] if not r["is_parent"]]
    shorthand = [r for r in mets if r["shorthand"]]
    by_verdict = collections.Counter(r["verdict"] for r in mets)
    return {
        "provenance": stamp(__file__),
        "inputs": record_inputs([SI]),
        "what_this_is": "the external benchmark's per-drug tables as data -- row, pathway, which "
                        "models predicted it, and what the drawing is labelled with -- read from "
                        "the Supporting Information and checked against the recall the same "
                        "document prints",
        "checked_against": {
            "table": "S12", "field": "recall", "cells": len(printed) * len(MODELS),
            "note": "the producer refuses to write unless every drug's mark count over its "
                    "metabolite rows equals the recall printed there, to the three decimals "
                    "printed",
        },
        "scored_without_a_table": sorted(set(printed) - set(order)),
        "n_drugs": len(order), "n_metabolites": len(mets),
        "n_specified": len(mets) - len(shorthand), "n_shorthand": len(shorthand),
        "shorthand_by_reason": dict(collections.Counter(r["why_not_a_structure"]
                                                        for r in shorthand)),
        "by_verdict": {k: by_verdict.get(k, 0)
                       for k in (READABLE, NOT_A_STRUCTURE, DISPUTED)},
        "disputed": [{"drug": t["drug"], "id": r["id"], "page": r["page"],
                      "shorthand": r["shorthand"], "scoping": r["scoping"]}
                     for t in (tables[d] for d in order) for r in t["rows"]
                     if not r["is_parent"] and r["verdict"] == DISPUTED],
        "tables": [tables[d] for d in order],
        "reading": "A row both signals call plain draws one structure and can be read off. A "
                   "row both call marked does not: the document states a mass change and the "
                   "region it happened in, so what it publishes is a formula and a neighbourhood, "
                   "and a single structure read from it would be a position nobody measured. "
                   "Where the two signals differ the row is listed and left undecided, because "
                   "an abbreviation such as GluA is sometimes bonded to a drawn atom and "
                   "sometimes to a dashed box, and only looking tells which.",
    }


def disagreements(tables: list, printed: dict) -> list:
    """Every cell of Table S12 the extraction fails to predict, as sentences."""
    out = []
    for t in tables:
        rows = [r for r in t["rows"] if not r["is_parent"]]
        n = len(rows)
        if t["drug"] not in printed:
            out.append(f"{t['drug']}: the summary prints no recall for this drug")
            continue
        for model in MODELS:
            hits = sum(1 for r in rows if r["marks"][model])
            got = (Decimal(hits) / Decimal(n)).quantize(Decimal("0.001"),
                                                        rounding=ROUND_HALF_UP) if n else None
            want = Decimal(str(printed[t["drug"]][model])).quantize(Decimal("0.001"))
            if got != want:
                out.append(f"{t['drug']} {model}: read {hits}/{n} = {got}, printed {want}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify and write nothing")
    args = ap.parse_args()

    blob = extract()
    bad = disagreements(blob["tables"], recall_printed())
    if bad:
        raise SystemExit("REFUSING: the tables read here do not reproduce the recall the same "
                         "document prints.\n  " + "\n  ".join(bad))
    print(f"{blob['n_drugs']} tables, {blob['n_metabolites']} metabolite rows, "
          f"reproducing {blob['checked_against']['cells']} printed recall cells")
    for verdict_text, n in blob["by_verdict"].items():
        print(f"  {verdict_text:<45} {n:4d}")
    for why, n in sorted(blob["shorthand_by_reason"].items()):
        print(f"      label says: {why:<33} {n:4d}")
    if blob["scored_without_a_table"]:
        print(f"  scored by the summary with no table in it: "
              f"{', '.join(blob['scored_without_a_table'])}")
    if args.check:
        print("checked, nothing written")
        return 0
    OUT.write_text(json.dumps(blob, indent=1))
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
