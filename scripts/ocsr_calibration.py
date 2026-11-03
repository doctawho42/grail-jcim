#!/usr/bin/env python3
"""How well a drawing can be read back, measured on structures whose answer is already held.

The radiolabelled human ADME benchmark publishes its known metabolites as drawings, which is the
one reason no measurement in this work is external. Reading them off the figures by hand is a
bounded job and a transcription step is an instrument like any other: if it is wrong on a handful
of structures, the external number moves and nothing inside the repository can notice. A machine
that reads structures out of images can do the first pass, and the question that decides whether
to trust it is not how good such models are said to be but how often this one is right on this
kind of chemistry.

That can be measured today, without the benchmark's figures. The GLORYx reference set in
docs/benchmark/data/ is 205 published drug metabolites whose structures this repository holds. So:
render them, hand the images to a recogniser, and score what comes back against the key under the
manuscript's own matching criteria. The result is a number the paper can print beside any external
figure, rather than a hope.

Two properties of the protocol matter more than the number.

The key is written outside the directory the recogniser is given, and the image names carry no
structure, so a recogniser that reads its own answers has to be caught rather than trusted. And
the score is reported per criterion, because the dominant failure of this class of model is
stereochemistry, and the criterion this work defaults to canonicalises tautomers and strips
stereochemistry. An error that moves no key under the default criterion is not an error of this
instrument for this purpose, and one that changes a heavy atom is.

The calibration set is a test set for the TRANSCRIPTION and for nothing else. Half of it sits
inside this project's training split, which is recorded in results/external_overlap.json and makes
it useless for measuring a predictor. Reading a drawing does not consult that split.

    python scripts/ocsr_calibration.py render                 # images + the sealed key
    python scripts/ocsr_calibration.py score submission.csv   # image,smiles -> a measured rate
    python scripts/ocsr_calibration.py degeneracy             # what a reported formula decides
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _acs_table import DEFENSIBLE  # noqa: E402
from _provenance import record_inputs, stamp  # noqa: E402

GLORYX = ROOT / "docs" / "benchmark" / "data" / "gloryx_test.json"
HOME = ROOT / "revision" / "ocsr_calibration"
IMAGES = HOME / "images"
KEY = HOME / "key.json"
# Both outputs sit beside the key rather than in results/, which is the paper's artifact
# space and is swept by the provenance audit. These two are calibration of an instrument,
# not measurements the manuscript cites, and a score over a submission that does not exist
# yet has no business being counted among them.
OUT = HOME / "score.json"
DEGEN = HOME / "formula_degeneracy.json"

# Depiction styles, declared and named. One style measures one renderer's defaults, which is the
# easiest case a recogniser meets and not the case the benchmark's figures present: those are
# drawn by a chemist in a drawing program, rotated, crowded and labelled. Varying rotation, line
# width and font is the cheapest approximation of that, and reporting per style says which part of
# the spread is the depiction rather than the molecule.
STYLES = {
    "plain": {"rotate": 0.0, "bondLineWidth": 2, "minFontSize": 12, "stereo": False},
    "rotated": {"rotate": 24.0, "bondLineWidth": 2, "minFontSize": 12, "stereo": False},
    "thin_small": {"rotate": -11.0, "bondLineWidth": 1, "minFontSize": 8, "stereo": False},
    "annotated": {"rotate": 7.0, "bondLineWidth": 2, "minFontSize": 11, "stereo": True},
}
SIZE = 420


def references() -> list:
    """The GLORYx reference metabolites, through the loader the rest of the project uses.

    That file carries stray backslashes inside its SMILES and is not valid JSON; the loader in
    eval_on_gloryx repairs them. Reading it with json.load here would raise on Tacrolimus and a
    calibration set that silently stopped at the thirty-sixth parent would understate nothing and
    measure a different population.
    """
    from eval_on_gloryx import load_gloryx

    out = []
    for parent, mets in sorted(load_gloryx(GLORYX).items()):
        for smiles in mets:
            out.append({"parent": parent, "smiles": smiles})
    return out


def _mol(smiles: str):
    from rdkit import Chem

    return Chem.MolFromSmiles(smiles)


def image_id(smiles: str, style: str) -> str:
    """An opaque name. A file called after its own InChIKey is an answer sheet."""
    return "img_" + hashlib.sha256(f"{style}|{smiles}".encode()).hexdigest()[:12]


def render(limit: int = 0) -> dict:
    """Write one image per reference and style, and the key beside the directory, not inside it."""
    from rdkit.Chem import AllChem
    from rdkit.Chem.Draw import rdMolDraw2D

    refs = references()
    if limit:
        refs = refs[:limit]
    if not refs:
        raise SystemExit("REFUSING: the calibration set is empty, so a score computed from it "
                         "would be a rate over nothing")

    IMAGES.mkdir(parents=True, exist_ok=True)
    for old in IMAGES.glob("img_*.png"):
        old.unlink()

    key, failed = {}, []
    for rec in refs:
        mol = _mol(rec["smiles"])
        if mol is None:
            failed.append(rec["smiles"])
            continue
        AllChem.Compute2DCoords(mol)
        for style, opt in STYLES.items():
            name = image_id(rec["smiles"], style)
            d = rdMolDraw2D.MolDraw2DCairo(SIZE, SIZE)
            o = d.drawOptions()
            o.rotate = opt["rotate"]
            o.bondLineWidth = opt["bondLineWidth"]
            o.minFontSize = opt["minFontSize"]
            o.addStereoAnnotation = opt["stereo"]
            rdMolDraw2D.PrepareAndDrawMolecule(d, mol)
            d.FinishDrawing()
            (IMAGES / f"{name}.png").write_bytes(d.GetDrawingText())
            key[name] = {"smiles": rec["smiles"], "parent": rec["parent"], "style": style}

    blob = {"provenance": stamp(__file__), "inputs": record_inputs([GLORYX]),
            "what_this_is": "the answer key for the transcription calibration: which structure "
                            "each rendered image is, held outside the directory the recogniser "
                            "is given",
            "styles": STYLES, "size_px": SIZE,
            "n_structures": len(refs), "n_images": len(key),
            "unparsed": failed, "key": key}
    KEY.write_text(json.dumps(blob, indent=1))

    with (HOME / "submission_template.csv").open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["image", "smiles"])
        for name in sorted(key):
            w.writerow([f"{name}.png", ""])

    print(f"{len(refs)} structures, {len(key)} images in {IMAGES.relative_to(ROOT)}")
    if failed:
        print(f"{len(failed)} structures RDKit would not parse and that are not in the key")
    print(f"key at {KEY.relative_to(ROOT)}, template at "
          f"{(HOME / 'submission_template.csv').relative_to(ROOT)}")
    return blob


def _keys_of(smiles: str, criterion: str):
    """One structure's key under one criterion, through the manuscript's own implementation."""
    from bank_without_selection import _key as tautomer_key
    from grail_metabolism.metrics import _match_keys

    if criterion == "inchikey_tautomer":
        return tautomer_key(smiles)
    got = _match_keys([smiles], criterion)
    return next(iter(got)) if got else None


def _formula(smiles: str):
    from rdkit.Chem import rdMolDescriptors

    mol = _mol(smiles)
    return rdMolDescriptors.CalcMolFormula(mol) if mol is not None else None


def parent_names() -> dict:
    """Parent SMILES to the drug name the source prints, so a named group can be named.

    The loader the rest of the project uses returns structures and drops the names, which is all
    it needs. A degenerate group of seven reported as a parent SMILES is a finding no chemist can
    act on, so the name is read here from the same file.
    """
    import re

    raw = GLORYX.read_text()
    data = json.loads(re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", raw))  # stray SMILES backslashes
    return {p["smiles"]: p.get("drugName") for p in data if p.get("smiles")}


def formula_degeneracy(refs: list | None = None) -> dict:
    """How much a reported molecular formula can decide about which metabolite a drawing is.

    The check that does not run through any recogniser is the reported one: the formula of the
    structure read back must equal the formula the source prints for that metabolite. How strong
    that check is has nothing to do with the recogniser and cannot be measured by scoring one. It
    is a property of the reference set. Two metabolites of one parent that carry the same formula
    -- an oxidation at two positions, most often -- are a pair the formula cannot separate, so a
    reader who swaps them passes the gate and the swap survives into the external number.

    The grouping is per parent, because a drawing sits in one parent's panel and a formula shared
    between two parents never had to separate them. A metabolite listed twice is collapsed first,
    so a repeated row cannot be counted as a collision.

    Measured here on the GLORYx reference set, the published drug metabolites this repository
    holds. The same number for the external set is computable from its printed formula column
    alone, before a single structure is read.
    """
    from bank_without_selection import _key as tautomer_key

    rows = references() if refs is None else refs
    names = parent_names()
    by_parent, unparsed = {}, []
    for rec in rows:
        if _mol(rec["smiles"]) is None:
            unparsed.append(rec["smiles"])
            continue
        by_parent.setdefault(rec["parent"], {})[tautomer_key(rec["smiles"])] = rec["smiles"]

    groups, collisions = {}, []
    worst = {"parent": None, "formula": None, "n": 0, "drug": None}
    pinned = undecided = 0
    pooled = {}
    for parent in sorted(by_parent):
        shelf = {}
        for smiles in sorted(by_parent[parent].values()):
            shelf.setdefault(_formula(smiles), []).append(smiles)
            pooled.setdefault(_formula(smiles), set()).add(smiles)
        for formula in sorted(shelf):
            members = shelf[formula]
            n = len(members)
            groups[str(n)] = groups.get(str(n), 0) + 1
            if n == 1:
                pinned += 1
            else:
                undecided += n
                collisions.append({"parent": parent, "drug": names.get(parent),
                                   "formula": formula, "members": members})
            if n > worst["n"]:
                worst = {"parent": parent, "drug": names.get(parent),
                         "formula": formula, "n": n}

    n_refs = pinned + undecided
    return {
        "provenance": stamp(__file__),
        "inputs": record_inputs([GLORYX]),
        "what_this_is": "how often a reported molecular formula identifies which metabolite of a "
                        "parent a drawing is, which is the strength of the one check in the "
                        "transcription protocol that does not run through a recogniser",
        "population": "the GLORYx reference metabolites, grouped by parent drug",
        "n_rows": len(rows), "n_references": n_refs, "n_parents": len(by_parent),
        "unparsed": unparsed,
        "pinned": pinned, "undecided": undecided,
        "rate_pinned": round(pinned / n_refs, 4) if n_refs else 0.0,
        "groups_by_size": groups,
        "worst": worst,
        # What the same count becomes if a reader could confuse metabolites across panels rather
        # than only inside one. It is the pessimistic bound on the same gate, and it is reported
        # beside the per-parent number because the per-parent number is the favourable one.
        "pooled_undecided": sum(len(v) for v in pooled.values() if len(v) > 1),
        "collisions": collisions,
        "reading": "A reference in a formula group of one is pinned by the reported formula "
                   "alone: a structure read back with that formula is that metabolite or has a "
                   "heavy atom wrong. A reference sharing its formula with a sibling is not, and "
                   "for those the formula gate passes a swap, so they are the rows a chemist has "
                   "to look at whatever a recogniser returns.",
    }


def score(submission: Path, out: Path = OUT) -> dict:
    """What a recogniser got right, per criterion and per style.

    A submission naming an image the key does not hold is a refusal and not a zero: it means the
    two sides are talking about different sets, and a rate computed across that is a number about
    nothing.

    The destination is an argument because a test scores a submission it built itself, and a rate
    over a synthetic submission left behind in results/ is a file that reads as a measurement.
    """
    if not KEY.exists():
        raise SystemExit(f"REFUSING: no key at {KEY.relative_to(ROOT)}; run `render` first, and "
                         f"keep the key out of the directory the recogniser reads")
    blob = json.loads(KEY.read_text())
    key = blob["key"]

    rows = {}
    with Path(submission).open(newline="") as fh:
        for row in csv.DictReader(fh):
            name = (row.get("image") or "").strip()
            if name.endswith(".png"):
                name = name[:-4]
            if not name:
                continue
            rows[name] = (row.get("smiles") or "").strip()
    unknown = sorted(set(rows) - set(key))
    if unknown:
        raise SystemExit(f"REFUSING: {len(unknown)} submitted images are not in the key, the "
                         f"first being {unknown[0]}. The submission and the key are about "
                         f"different sets.")

    criteria = list(DEFENSIBLE) + ["canonical"]
    per_criterion = {c: {"right": 0, "wrong": 0} for c in criteria}
    per_criterion["formula"] = {"right": 0, "wrong": 0}
    per_style = {s: {"answered": 0, "right_default": 0} for s in blob["styles"]}
    blank = [n for n in key if not rows.get(n)]
    wrong = []

    for name, truth in sorted(key.items()):
        got = rows.get(name)
        style = truth["style"]
        if not got:
            continue
        per_style[style]["answered"] += 1
        hit = {}
        for c in criteria:
            a, b = _keys_of(truth["smiles"], c), _keys_of(got, c)
            ok = a is not None and a == b
            hit[c] = ok
            per_criterion[c]["right" if ok else "wrong"] += 1
        fa, fb = _formula(truth["smiles"]), _formula(got)
        ok_f = fa is not None and fa == fb
        per_criterion["formula"]["right" if ok_f else "wrong"] += 1
        if hit["inchikey_tautomer"]:
            per_style[style]["right_default"] += 1
        else:
            wrong.append({"image": name, "style": style, "truth": truth["smiles"],
                          "submitted": got, "formula_agrees": ok_f,
                          "agrees_under": sorted(c for c in criteria if hit[c])})

    answered = sum(v["answered"] for v in per_style.values())
    report = {
        "provenance": stamp(__file__),
        "inputs": record_inputs([KEY, submission]),
        "what_this_is": "the rate at which a recogniser read the right structure out of a "
                        "rendered drawing, on published drug metabolites this repository holds, "
                        "under the manuscript's own matching criteria",
        # Which file was scored, named in the artifact rather than only in its input digests. A
        # submission built from the key scores one at every criterion, and a 1.0 lying about in
        # results/ with nothing to say where it came from is a number a reader would take for a
        # recogniser's.
        "scored_submission": str(Path(submission)),
        "n_images": len(key), "n_answered": answered, "n_blank": len(blank),
        "by_criterion": {c: dict(v, rate=round(v["right"] / max(v["right"] + v["wrong"], 1), 4))
                         for c, v in per_criterion.items()},
        "by_style": {s: dict(v, rate=round(v["right_default"] / max(v["answered"], 1), 4))
                     for s, v in per_style.items()},
        "default_criterion": "inchikey_tautomer",
        "misread": wrong,
        "reading": "A structure whose key agrees under the default criterion and not under "
                   "canonical SMILES differs in stereochemistry or in tautomer, which this work's "
                   "default does not distinguish and the strictest criterion does. A structure "
                   "whose formula disagrees differs in a heavy atom, and no criterion here "
                   "forgives that.",
    }
    out.write_text(json.dumps(report, indent=1))
    print(f"{answered} of {len(key)} images answered, {len(blank)} left blank")
    for c, v in report["by_criterion"].items():
        print(f"  {c:20s} {v['right']:4d} right  {v['wrong']:4d} wrong  rate {v['rate']}")
    for s, v in report["by_style"].items():
        print(f"  style {s:12s} {v['right_default']:4d} of {v['answered']:4d}  rate {v['rate']}")
    where = out.relative_to(ROOT) if out.is_relative_to(ROOT) else out
    print(f"wrote {where}")
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render", help="write the images and the sealed key")
    r.add_argument("--limit", type=int, default=0, help="first N structures only, for a dry run")
    s = sub.add_parser("score", help="score a recogniser's CSV of image,smiles")
    s.add_argument("submission")
    sub.add_parser("degeneracy", help="how much a reported formula can decide, before any model")
    args = ap.parse_args()

    if args.cmd == "render":
        render(args.limit)
    elif args.cmd == "score":
        score(Path(args.submission))
    else:
        got = formula_degeneracy()
        DEGEN.write_text(json.dumps(got, indent=1))
        print(f"{got['n_references']} references over {got['n_parents']} parents "
              f"({got['n_rows']} rows read, {len(got['unparsed'])} unparsed)")
        print(f"  pinned by the reported formula alone  {got['pinned']:4d}  "
              f"rate {got['rate_pinned']}")
        print(f"  sharing a formula with a sibling      {got['undecided']:4d}  "
              f"in {len(got['collisions'])} groups, largest {got['worst']['n']}")
        print(f"  the same count pooled across parents  {got['pooled_undecided']:4d}")
        print(f"wrote {DEGEN.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
