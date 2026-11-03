#!/usr/bin/env python3
"""The held-out check: a rebuilt metabolite must differ from its base by what its pathway states.

The reconstructor was calibrated on the ten parent drawings, and the rule that recognises a hashed
stereo bond came out of reading those ten failures, so seven of ten is an upper bound rather than
an estimate of what it does on a drawing it has not seen.

This is the check nothing was fitted to. Every metabolite row names its biotransformation in text
beside the drawing, and the reconstructor has never read a pathway. An oxidation adds an oxygen, a
glucuronidation adds C6H8O6, a dehydrogenation removes two hydrogens: so a metabolite rebuilt from
its own segments must differ from the structure it was made from by exactly that, and the ninety-two
rows carry their own answers.

What the names do not state is stated here instead of being guessed. A dealkylation removes an
alkyl group of a size the name withholds. A hydrolysis cleaves a bond and the row is one of the
two pieces, so the name gives neither which piece nor what it kept. A conjugation with glutathione
or cysteine can add or substitute. Those are excluded by name, and the vocabulary is required to
recognise every pathway string in the document, so a name nobody has thought about is a refusal
rather than a pass.

    python scripts/typed_edit/gao_pathway_check.py
    python scripts/typed_edit/gao_pathway_check.py --check
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for _p in (str(ROOT), str(ROOT / "scripts"), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _provenance import record_inputs, stamp  # noqa: E402

import gao_si_structures as VEC  # noqa: E402
import gao_si_tables as TAB  # noqa: E402

HOME = ROOT / "revision" / "gao2026_reference_set"
OUT = HOME / "pathway_check.json"

UNCLASSIFIED = object()

# What a named step does to a molecular formula. Each is the net change: an acetylation puts on
# C2H3O and takes off the hydrogen it replaces, a glycine conjugation condenses and loses water.
STEP = {
    "oxidation": {"O": 1},
    "hydroxylation": {"O": 1},
    "hydroxylated": {"O": 1},
    "n-oxidation": {"O": 1},
    "dehydrogenation": {"H": -2},
    "reduction": {"H": 2},
    "dehydration": {"H": -2, "O": -1},
    "dehydroxylation": {"O": -1},
    "decarboxylation": {"C": -1, "O": -2},
    "glucuronidation": {"C": 6, "H": 8, "O": 6},
    "sulfation": {"S": 1, "O": 3},
    "methylation": {"C": 1, "H": 2},
    "o-methylation": {"C": 1, "H": 2},
    "acetylation": {"C": 2, "H": 2, "O": 1},
    "n-acetylation": {"C": 2, "H": 2, "O": 1},
    "glycine conjugation": {"C": 2, "H": 3, "N": 1, "O": 1},
}

# Named steps whose formula change the name does not fix. These are excluded by name and counted,
# not quietly passed: a dealkylation's alkyl has no stated size, a hydrolysis keeps one of two
# pieces the name does not identify, and a thiol conjugate may add across a double bond or
# substitute for a hydrogen, which differ by two.
VAGUE = {
    "n-dealkylation", "o-dealkylation", "dealkylation", "hydrolysis",
    "cysteine conjugation", "glutathione conjugation", "cysteinylglycine conjugation",
    "oxidative cleavage of morpholine ring", "morpholino amino ethanol",
    "hydroxylated isavuconazole carbamoyl form",
    "n-acetylcysteine conjugate of hydroxylated",
}

# A row may be made from another row rather than from the parent, and says so by naming it.
IDENT = re.compile(r"\b(?:m|mwt|bia)\s?\d[\w.\-]*", re.I)


def _norm(pathway: str) -> str:
    text = " ".join(pathway.split()).lower().replace("n- ", "n-").replace("o- ", "o-")
    text = IDENT.sub(" ", text)
    text = " ".join(text.split())
    for edge in (" of", "of "):
        if text.startswith("of "):
            text = text[3:]
        if text.endswith(" of"):
            text = text[:-3]
    return text.strip()


def classify(pathway: str):
    """The formula change a pathway states, None when it states none, UNCLASSIFIED when unknown."""
    text = _norm(pathway)
    if not text:
        return None
    total, vague = collections.Counter(), False
    for part in text.split(" and "):
        part = part.strip()
        if part in STEP:
            total.update(STEP[part])
        elif part in VAGUE:
            vague = True
        else:
            return UNCLASSIFIED
    return None if vague else dict(total)


def base_of(row: dict, rows: list):
    """The row this one is made from, when its pathway names one, else None for the parent."""
    named = [o["id"] for o in rows
             if o["id"] != row["id"] and o["id"] and o["id"] in row["pathway"]]
    return max(named, key=len) if named else None


def _counts(smiles: str) -> dict:
    from rdkit import Chem
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {}
    return dict(collections.Counter(a.GetSymbol() for a in Chem.AddHs(mol).GetAtoms()))


def _delta(after: dict, before: dict) -> dict:
    keys = set(after) | set(before)
    return {k: after.get(k, 0) - before.get(k, 0) for k in sorted(keys)
            if after.get(k, 0) - before.get(k, 0) != 0}


def _trim(d: dict) -> dict:
    return {k: v for k, v in sorted(d.items()) if v != 0}


def rebuild_all() -> dict:
    """Every row of every table, rebuilt from its own segments, keyed by drug and row."""
    import pdfplumber

    out = {}
    with pdfplumber.open(TAB.SI) as pdf:
        for t in TAB.extract()["tables"]:
            by_page = collections.defaultdict(list)
            for r in t["rows"]:
                by_page[r["page"]].append(r)
            for page_no, wanted in sorted(by_page.items()):
                page = pdf.pages[page_no - 1]
                marker = [w for w in page.extract_words() if w["text"] == "Table"]
                cols, rows = TAB.grid(page, min(w["top"] for w in marker) if marker else 0.0)
                words = page.extract_words()
                bands = []
                for a, z in zip(rows, rows[1:]):
                    ident = " ".join(w["text"] for w in words
                                     if cols[0] <= (w["x0"] + w["x1"]) / 2 < cols[1]
                                     and a <= (w["top"] + w["bottom"]) / 2 < z)
                    if ident.strip() and not ident.startswith("Compound"):
                        bands.append((ident, a, z))
                for ident, a, z in bands:
                    row = next((r for r in wanted if r["id"] == ident), None)
                    if row is None:
                        continue
                    segs, chars = VEC.cell(page, cols, (a, z))
                    smiles, note = VEC.build(segs, VEC.read_labels(chars))
                    out[(t["drug"], row["id"])] = (smiles, note)
    return out


def check() -> dict:
    tables = TAB.extract()["tables"]
    built = rebuild_all()
    rows_out = []
    for t in tables:
        rows = t["rows"]
        parent = next(r for r in rows if r["is_parent"])
        for r in rows:
            if r["is_parent"]:
                continue
            base_id = base_of(r, rows) or parent["id"]
            expected = classify(r["pathway"])
            record = {"drug": t["drug"], "id": r["id"], "pathway": " ".join(r["pathway"].split()),
                      "base": base_id, "verdict": r["verdict"],
                      "expected": None if expected in (None, UNCLASSIFIED) else _trim(expected)}
            if expected is UNCLASSIFIED:
                record["outcome"] = "pathway not recognised"
            elif expected is None:
                record["outcome"] = "pathway states no formula change"
            elif r["verdict"] == TAB.NOT_A_STRUCTURE:
                record["outcome"] = "a marked region, not a structure"
            else:
                mine = built.get((t["drug"], r["id"]), (None, "row not located"))
                base = built.get((t["drug"], base_id), (None, "base not located"))
                if mine[0] is None:
                    record["outcome"] = "structure not rebuilt"
                    record["note"] = mine[1]
                elif base[0] is None:
                    record["outcome"] = "base not rebuilt"
                    record["note"] = base[1]
                else:
                    observed = _delta(_counts(mine[0]), _counts(base[0]))
                    record["observed"] = observed
                    record["outcome"] = ("agrees" if observed == record["expected"]
                                         else "disagrees")
            rows_out.append(record)

    tally = collections.Counter(r["outcome"] for r in rows_out)
    checked = tally["agrees"] + tally["disagrees"]
    # Split by what the drawing was already judged to be, before this check existed. The rows both
    # signals called plain are the ones the reconstructor is for; the rows the two signals
    # disagreed about were left undecided there, and this is a measurement that can decide them.
    per_verdict = {}
    for r in rows_out:
        if r["outcome"] in ("agrees", "disagrees"):
            slot = per_verdict.setdefault(r["verdict"], {"agrees": 0, "disagrees": 0})
            slot[r["outcome"]] += 1
    for slot in per_verdict.values():
        n = slot["agrees"] + slot["disagrees"]
        slot["rate"] = round(slot["agrees"] / n, 4) if n else None
    return {
        "provenance": stamp(__file__),
        "inputs": record_inputs([TAB.SI, HOME / "si_tables.json"]),
        "what_this_is": "whether a metabolite rebuilt from the segments it is drawn with differs "
                        "from the structure it was made from by the formula change its stated "
                        "pathway implies, which is a check the reconstructor was not fitted to",
        "n_rows": len(rows_out), "n_checked": checked,
        "n_agree": tally["agrees"], "n_disagree": tally["disagrees"],
        "rate": round(tally["agrees"] / checked, 4) if checked else None,
        "by_outcome": dict(tally),
        "by_verdict": per_verdict,
        "rows": rows_out,
        "a_disagreement_names_two_suspects": "A row that disagrees says the reading and the "
              "pathway vocabulary are inconsistent; it does not say which is wrong. Opicapone is "
              "a nitrocatechol and one of its rows is called Reduction, which this vocabulary "
              "takes to be the addition of two hydrogens and which for a nitro group is not: the "
              "observed change there is the loss of one oxygen, and the drawing may well be "
              "right. The vocabulary is deliberately left as it was written, before any row was "
              "checked, because repairing the entries that disagree is how a held-out check "
              "stops being one.",
        "reading": "A row that agrees was rebuilt into a molecule whose formula moved by exactly "
                   "what the document says happened to it, which nothing in the reconstructor "
                   "could have arranged. A row that disagrees names a drawing feature read "
                   "wrongly. The rows that are not checked are not failures and not passes: the "
                   "name states no size, or the drawing marks a region rather than a structure.",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="measure and write nothing")
    args = ap.parse_args()
    blob = check()
    print(f"{blob['n_rows']} metabolite rows")
    for outcome, n in sorted(blob["by_outcome"].items(), key=lambda kv: -kv[1]):
        print(f"  {outcome:<36} {n:3d}")
    if blob["n_checked"]:
        print(f"  checked {blob['n_checked']}, agreeing {blob['n_agree']} "
              f"(rate {blob['rate']})")
    for verdict_text, slot in sorted(blob["by_verdict"].items()):
        print(f"    {verdict_text:<40} {slot['agrees']:3d} of "
              f"{slot['agrees'] + slot['disagrees']:3d}  rate {slot['rate']}")
    for r in blob["rows"]:
        if r["outcome"] == "disagrees":
            print(f"    disagrees  {r['drug']}/{r['id']:<12} {r['pathway'][:30]:<30} "
                  f"expected {r['expected']} observed {r['observed']}")
    if args.check:
        print("checked, nothing written")
        return 0
    OUT.write_text(json.dumps(blob, indent=1))
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
