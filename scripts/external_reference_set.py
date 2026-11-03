#!/usr/bin/env python3
"""The machine-readable reference set the radiolabelled ADME benchmark does not publish.

The strongest limitation this work states is that no measurement in it is external. Every figure
is measured on one corpus, assembled here, whose selection cannot be recovered, so a held-out
split of it tests the ranking and leaves the chemistry where it came from. The answer exists:
\\citet{Gao_2026} benchmark this class of tool against human radiolabelled ADME data, which is
*in vivo* data on exactly the population predicted here. The reason it has not been used is that
their known metabolites appear only as drawings, which no tool can read.

Drawings can be redrawn, and ninety-seven structures across eleven drugs is a bounded job. This
module prepares that job and checks what comes back.

What it does NOT do is invent a structure. The substrates are read out of the authors' own
deposited input scripts, so the molecule each sheet is about is theirs. The number of metabolites
per drug is the number their paper publishes, transcribed once into
results/external_budget_confound.json and read from there, so a sheet that comes back with a row
too few or too many fails before it can become a recall figure. The metabolite structures
themselves are drawn by a chemist from the published figures; nothing here guesses one.

    python scripts/external_reference_set.py --worksheet   # write the sheets to be filled
    python scripts/external_reference_set.py --check       # check a filled sheet
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

DEPOSIT = ROOT / "artifacts" / "external" / "gao2026"
PUBLISHED = ROOT / "results" / "external_budget_confound.json"
OUTDIR = ROOT / "revision" / "gao2026_reference_set"
SHEET = OUTDIR / "metabolites.csv"

# The deposit and the published table disagree on one name out of eleven, and they disagree in
# the way a development code and an adopted name disagree. It is recorded as an alias with its
# reason rather than merged in silence, because a wrong pairing here would attach a drug's
# metabolite count to another drug's structure and nothing downstream would notice.
ALIASES = {
    "Fovinaciclib": ("FCN-437c",
                     "the only name in the published table with no file in the deposit, matched "
                     "to the only file in the deposit with no row in the published table; "
                     "FCN-437c is the development code the deposit's scripts are named by. "
                     "Confirm before the sheet is filled."),
}


def published_counts() -> dict:
    """How many known metabolites each drug has, as the benchmark's own table reports."""
    if not PUBLISHED.exists():
        raise SystemExit(f"{PUBLISHED.relative_to(ROOT)} is missing, and it carries the counts "
                         f"this worksheet is built against")
    return json.loads(PUBLISHED.read_text())["reference_set_sizes"]


def deposit_substrates() -> dict:
    """The parent structure of each drug, read from the authors' own tool input."""
    out = {}
    for f in sorted(DEPOSIT.glob("*.py")):
        m = re.search(r'Chem\.MolFromSmiles\(\s*"([^"]+)"\s*\)', f.read_text())
        if m:
            out[f.stem] = (m.group(1), f.name)
    return out


def build_spec() -> dict:
    """Drug -> its substrate, where that came from, and how many metabolites it must have."""
    counts, subs = published_counts(), deposit_substrates()
    spec, missing = {}, []
    for name, n in sorted(counts.items()):
        key, reason = name, None
        if name not in subs and name in ALIASES:
            key, reason = ALIASES[name]
        if key not in subs:
            missing.append(name)
            continue
        smiles, src = subs[key]
        spec[name] = {"substrate": smiles, "source_file": src, "deposit_name": key,
                      "metabolites_published": n}
        if reason:
            spec[name]["alias_reason"] = reason
    if missing:
        raise SystemExit(
            "no substrate in the deposit for " + ", ".join(missing) + ". Every drug needs one, "
            "because the alternative is reading the structure off a figure, which is the thing "
            "this file exists to avoid.")
    return spec


def _mol(smiles):
    from rdkit import Chem, RDLogger

    RDLogger.DisableLog("rdApp.*")
    return Chem.MolFromSmiles(smiles)


def _formula(mol):
    from rdkit.Chem import rdMolDescriptors

    return rdMolDescriptors.CalcMolFormula(mol)


def _delta(a, b) -> dict:
    from collections import Counter
    from rdkit import Chem

    def counts(m):
        c = Counter()
        for at in Chem.AddHs(m).GetAtoms():
            c[at.GetSymbol()] += 1
        return c

    x, y = counts(a), counts(b)
    return {el: y.get(el, 0) - x.get(el, 0)
            for el in sorted(set(x) | set(y)) if y.get(el, 0) != x.get(el, 0)}


def validate_sheet(text: str, spec: dict) -> dict:
    """Every way a hand-filled sheet goes wrong, named one at a time.

    A validator that stops at the first problem makes the chemist run it once per mistake, so
    this collects all of them and reports the sheet as a whole.
    """
    from rdkit import Chem

    rows, problems, by_drug = [], [], {}
    reader = csv.DictReader(io.StringIO(text))
    for i, r in enumerate(reader, 2):
        drug = (r.get("drug") or "").strip()
        smiles = (r.get("smiles") or "").strip()
        idx = (r.get("index") or "").strip()
        where = f"line {i} ({drug} {idx})"
        if drug not in spec:
            problems.append(f"{where}: {drug!r} is not one of the eleven drugs")
            continue
        if not smiles:
            problems.append(f"{where}: no structure was filled in")
            by_drug.setdefault(drug, [])
            continue
        mol = _mol(smiles)
        if mol is None:
            problems.append(f"{where}: {smiles!r} does not parse")
            by_drug.setdefault(drug, [])
            continue
        key = Chem.MolToInchiKey(mol)
        seen = by_drug.setdefault(drug, [])
        if key in [s["inchikey"] for s in seen]:
            problems.append(f"{where}: the same structure as an earlier row for this drug")
        parent = _mol(spec[drug]["substrate"])
        if parent is not None and Chem.MolToInchiKey(parent) == key:
            problems.append(f"{where}: this is the substrate, not a metabolite")
        row = {"drug": drug, "index": idx, "smiles": smiles, "inchikey": key,
               "formula": _formula(mol),
               "formula_delta": _delta(parent, mol) if parent is not None else None,
               "note": (r.get("note") or "").strip()}
        seen.append(row)
        rows.append(row)

    for drug, want in sorted((d, s["metabolites_published"]) for d, s in spec.items()):
        got = len(by_drug.get(drug, []))
        if got != want:
            problems.append(
                f"{drug}: the sheet has {got} metabolites and the benchmark publishes {want}")
    return {"ok": not problems, "problems": problems, "rows": rows,
            "n_drugs": len(spec), "n_rows": len(rows),
            "n_published": sum(s["metabolites_published"] for s in spec.values())}


def write_worksheet(spec: dict, outdir: Path = OUTDIR) -> list:
    """The sheets a chemist fills, with the row count fixed in advance per drug."""
    from _provenance import stamp

    outdir.mkdir(parents=True, exist_ok=True)
    written = []

    with (outdir / "substrates.csv").open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["drug", "smiles", "metabolites_published", "deposit_file"])
        for name, r in sorted(spec.items()):
            w.writerow([name, r["substrate"], r["metabolites_published"], r["source_file"]])
    written.append(outdir / "substrates.csv")

    (outdir / "substrates.smi").write_text(
        "".join(f"{r['substrate']}\t{n}\n" for n, r in sorted(spec.items())))
    written.append(outdir / "substrates.smi")

    if not SHEET.exists():
        with SHEET.open("w", newline="") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(["drug", "index", "smiles", "note"])
            for name, r in sorted(spec.items()):
                for i in range(1, r["metabolites_published"] + 1):
                    w.writerow([name, i, "", ""])
        written.append(SHEET)

    (outdir / "manifest.json").write_text(json.dumps({
        "provenance": stamp(__file__),
        "what_this_is": (
            "the worksheet for a machine-readable version of the known metabolites of the "
            "radiolabelled human ADME benchmark, whose paper publishes them as drawings"),
        "substrates_came_from": str(DEPOSIT.relative_to(ROOT)),
        "counts_came_from": str(PUBLISHED.relative_to(ROOT)),
        "nothing_here_was_guessed": (
            "every substrate is the string the benchmark's own tool-input script passes to "
            "RDKit, and every metabolite count is the number its paper publishes; the "
            "metabolite structures are left empty for a chemist to draw"),
        "drugs": spec,
        "metabolites_to_draw": sum(r["metabolites_published"] for r in spec.values()),
    }, indent=1))
    written.append(outdir / "manifest.json")
    return written


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worksheet", action="store_true", help="write the sheets to be filled")
    ap.add_argument("--check", action="store_true", help="check the filled sheet")
    ap.add_argument("--sheet", default=str(SHEET))
    ap.add_argument("--json", default=str(OUTDIR / "validation.json"))
    args = ap.parse_args()

    spec = build_spec()
    if args.worksheet:
        for f in write_worksheet(spec):
            print(f"  wrote {f.relative_to(ROOT)}")
        print(f"\n{len(spec)} drugs, {sum(r['metabolites_published'] for r in spec.values())} "
              f"metabolites to draw")
        for name, r in sorted(spec.items()):
            if "alias_reason" in r:
                print(f"\n  CONFIRM: {name} is matched to the deposit's {r['deposit_name']}. "
                      f"{r['alias_reason']}")
        return 0

    if args.check:
        p = Path(args.sheet)
        if not p.exists():
            raise SystemExit(f"{p} does not exist; run with --worksheet first")
        res = validate_sheet(p.read_text(), spec)
        Path(args.json).write_text(json.dumps(res, indent=1))
        print(f"{res['n_rows']} structures over {res['n_drugs']} drugs, "
              f"{res['n_published']} published")
        for pr in res["problems"]:
            print(f"  {pr}")
        print("\nexternal_reference_set: " + ("OK" if res["ok"] else "FAIL"))
        return 0 if res["ok"] else 1

    ap.error("one of --worksheet or --check")


if __name__ == "__main__":
    raise SystemExit(main())
