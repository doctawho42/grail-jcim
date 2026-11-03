#!/usr/bin/env python3
"""Rebuild a drawn structure from the segments it is drawn with, and measure that on held answers.

The external benchmark's structures are vector line segments and text labels, not pictures, so the
connectivity is in the document and recovering it is geometry rather than recognition. Geometry is
still an instrument, and this repository's history is of instruments that answered confidently.

The document carries its own answer key for this one. Every per-drug table draws the parent drug
in its first row, in the same hand as the metabolites it is compared against, and those ten parent
structures are already held here as SMILES taken from the benchmark's own input scripts. So the
reconstructor is scored on the authors' own drawings of structures this repository knows, which is
a far better calibration than scoring it on drawings made by the renderer that would be used to
test it.

What is compared is what this work matches on. The project's standardiser canonicalises tautomers
and writes SMILES without stereochemistry, so a wedge read as a plain bond costs nothing here and
a missing heavy atom costs everything; the per-criterion agreement is reported rather than a single
verdict, so which of the two happened is visible.

    python scripts/typed_edit/gao_si_structures.py
    python scripts/typed_edit/gao_si_structures.py --check
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for _p in (str(ROOT), str(ROOT / "scripts"), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _provenance import record_inputs, stamp  # noqa: E402

import gao_si_tables as TAB  # noqa: E402

HOME = ROOT / "revision" / "gao2026_reference_set"
SI = TAB.SI
OUT = HOME / "parent_calibration.json"

# Two endpoints this close are one atom. Bond lengths in these drawings are seven to eleven points,
# so the tolerance is an order below the thing it must not join.
JOIN = 1.2
# A second line beside a bond is its order, not a bond of its own: within this angle, this far from
# the first line, and overlapping it along its own direction. A hexagon's opposite sides are
# parallel too and are seventeen points apart, which is what the distance has to stay under.
PARALLEL_DEG = 12.0
DOUBLE_GAP = 3.8
OVERLAP = 0.5
# How far a bond's endpoint stops from the box of the text it runs into. Measured on the
# ten parent drawings rather than chosen: over their hundred labels the nearest endpoint
# is never further than 1.01 points from the box and is usually touching it. A reach set
# from the bond length instead swallowed the neighbouring atoms and gave oxygens eight
# bonds.
LABEL_REACH = 1.5
ELEMENTS = ("Cl", "Br", "N", "O", "S", "F", "P", "I")


def _mid(a, b):
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def _len(s):
    return math.hypot(s[1][0] - s[0][0], s[1][1] - s[0][1])


def _unit(s):
    n = _len(s) or 1.0
    return ((s[1][0] - s[0][0]) / n, (s[1][1] - s[0][1]) / n)


def _to_box(p, box) -> float:
    """Distance from a point to a rectangle, zero inside it."""
    x0, t, x1, b = box
    dx = max(x0 - p[0], 0.0, p[0] - x1)
    dy = max(t - p[1], 0.0, p[1] - b)
    return math.hypot(dx, dy)


def read_labels(chars: list) -> list:
    """The element each cluster of characters names, and where that element sits.

    Characters are grouped by adjacency and the group is read for an element and a charge: HN and
    NH are the same nitrogen, H2N and NH2 the same, N+ a cation. The position returned is the
    element's own character, not the group's centre, because a bond drawn to HN arrives at the N.
    """
    # Two characters belong to one label when they sit on the same line and touch. This is built
    # as connected components rather than by walking a sorted list: the first version compared
    # each character with the previous one in sort order and accepted a negative gap, so two
    # oxygens twenty-seven points apart became one label whose box swallowed the atoms between
    # them and came out of the build with twelve bonds.
    n = len(chars)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def mid(c):
        return (c["top"] + c["bottom"]) / 2

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if abs(mid(chars[i]) - mid(chars[j])) > 3.0:
                continue
            if 0.0 <= chars[j]["x0"] - chars[i]["x1"] < 1.8:
                a, b = find(i), find(j)
                if a != b:
                    parent[a] = b
    buckets = {}
    for i in range(n):
        buckets.setdefault(find(i), []).append(chars[i])
    out = [sorted(v, key=lambda c: c["x0"]) for _, v in sorted(buckets.items())]

    labels = []
    for g in out:
        text = "".join(c["text"] for c in g)
        element, anchor = None, None
        for i, c in enumerate(g):
            if c["text"] == "C" and i + 1 < len(g) and g[i + 1]["text"] == "l":
                element, anchor = "Cl", [c, g[i + 1]]
                break
            if c["text"] in ELEMENTS:
                element, anchor = c["text"], [c]
                break
        if element is None:
            continue
        labels.append({
            "element": element,
            "charge": text.count("+") - text.count("-"),
            "x": sum((c["x0"] + c["x1"]) / 2 for c in anchor) / len(anchor),
            "y": sum((c["top"] + c["bottom"]) / 2 for c in anchor) / len(anchor),
            # The whole group's box, not the element character's. A bond drawn to NH2 stops at
            # the far side of the text, several points from the N, and measuring the distance to
            # the character left every labelled atom disconnected from half its bonds.
            "box": (min(c["x0"] for c in g), min(c["top"] for c in g),
                    max(c["x1"] for c in g), max(c["bottom"] for c in g)),
        })
    return labels


def _cluster(points: list, tol: float) -> list:
    """Which points are the same point. Union-find, so a chain of near-misses joins."""
    parent = list(range(len(points)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            if math.dist(points[i], points[j]) <= tol:
                a, b = find(i), find(j)
                if a != b:
                    parent[a] = b
    groups = {}
    for i in range(len(points)):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def wedge_bond(pts: list):
    """The bond a filled wedge stands for: apex to the middle of its base.

    A solid stereo bond is drawn as a filled triangle and so is not a line at all. Left out, the
    atom at its far end keeps no bond to anything and leaves the molecule as a loose fragment.
    Its direction is thrown away with the rest of the stereochemistry, which this work's matching
    does not read.
    """
    if not pts or len(pts) < 3:
        return None
    far, best = None, -1.0
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            d = math.dist(pts[i], pts[j])
            if d > best:
                best, far = d, (pts[i], pts[j])
    if best < 2.0:
        return None
    a, b = far
    u = ((b[0] - a[0]) / best, (b[1] - a[1]) / best)
    ends = ([], [])
    for q in pts:
        t = ((q[0] - a[0]) * u[0] + (q[1] - a[1]) * u[1]) / best
        if t < 0.25:
            ends[0].append(q)
        elif t > 0.75:
            ends[1].append(q)
    if not ends[0] or not ends[1]:
        return None

    def spread(group):
        return max(math.dist(x, y) for x in group for y in group) if len(group) > 1 else 0.0

    def centre(group):
        return (statistics.fmean(q[0] for q in group), statistics.fmean(q[1] for q in group))

    tip, base = (ends[0], ends[1]) if spread(ends[0]) <= spread(ends[1]) else (ends[1], ends[0])
    return (centre(tip), centre(base))


def _hashes(segs: list) -> dict:
    """Ladders of short parallel marks: a hashed stereo bond, which stands for one single bond.

    A triple bond is three full-length lines stacked a couple of points apart. A hashed wedge is
    four or more short marks, perpendicular to the bond, evenly spaced along its whole length and
    touching neither atom. Read as inner lines it becomes a triple bond between two atoms that do
    not exist, and the molecule falls into fragments around it.

    The first version of this test asked only for parallel segments, which a hexagon's opposite
    sides also are, and it dismantled seven of the ten structures. A mark is therefore required to
    be short, to sit beside its neighbours, and to be one of a regular stack.
    """
    out, taken = {}, set()
    short = 6.0
    for i in range(len(segs)):
        if i in taken or _len(segs[i]) > short:
            continue
        ui, mi = _unit(segs[i]), _mid(*segs[i])
        family = [j for j in range(len(segs))
                  if j not in taken and _len(segs[j]) <= short
                  and math.dist(_mid(*segs[j]), mi) <= 12.0
                  and abs(ui[0] * _unit(segs[j])[0] + ui[1] * _unit(segs[j])[1])
                  >= math.cos(math.radians(PARALLEL_DEG))]
        if len(family) < 3:
            continue
        lens = [_len(segs[j]) for j in family]
        # A hashed wedge's marks grow from the narrow end; a triple bond's three lines are one
        # length. Without this the three-mark hashes were read as triple bonds and left a
        # two-atom fragment of their own in three of the ten structures.
        if max(lens) / max(min(lens), 0.01) < 1.4:
            continue
        normal = (-ui[1], ui[0])
        proj = sorted((_mid(*segs[j])[0] * normal[0] + _mid(*segs[j])[1] * normal[1], j)
                      for j in family)
        gaps = [b[0] - a[0] for a, b in zip(proj, proj[1:])]
        if not gaps or max(gaps) > 3.2 or proj[-1][0] - proj[0][0] < 1.2 * DOUBLE_GAP:
            continue
        step = statistics.fmean(gaps)
        a, b = _mid(*segs[proj[0][1]]), _mid(*segs[proj[-1][1]])
        ladder = [(a[0] - normal[0] * step, a[1] - normal[1] * step),
                  (b[0] + normal[0] * step, b[1] + normal[1] * step)]
        # The marks touch neither atom, so each end is snapped to the nearest real endpoint it
        # can reach; an unsnapped end becomes an atom of its own and the substituent floats off.
        others = [q for k, s in enumerate(segs) if k not in family for q in s]
        for e, point in enumerate(ladder):
            near = sorted(others, key=lambda q: math.dist(q, point))
            if near and math.dist(near[0], point) <= 3.5:
                ladder[e] = near[0]
        out[tuple(family)] = tuple(ladder)
        taken.update(family)
    return out


def _inner_lines(segs: list) -> dict:
    """Which segments are a second or third line beside another, and beside which."""
    order = sorted(range(len(segs)), key=lambda i: -_len(segs[i]))
    inner = {}
    for j in order:
        if j in inner:
            continue
        for i in order:
            if i == j or i in inner or _len(segs[i]) < _len(segs[j]):
                continue
            ui, uj = _unit(segs[i]), _unit(segs[j])
            dot = abs(ui[0] * uj[0] + ui[1] * uj[1])
            if dot < math.cos(math.radians(PARALLEL_DEG)):
                continue
            mj = _mid(*segs[j])
            ax, ay = segs[i][0]
            px, py = mj[0] - ax, mj[1] - ay
            along = px * ui[0] + py * ui[1]
            off = abs(px * -ui[1] + py * ui[0])
            if off > DOUBLE_GAP or not (0 <= along <= _len(segs[i])):
                continue
            ends = []
            for p in segs[j]:
                t = (p[0] - ax) * ui[0] + (p[1] - ay) * ui[1]
                ends.append(min(max(t, 0.0), _len(segs[i])))
            if abs(ends[1] - ends[0]) < OVERLAP * _len(segs[j]):
                continue
            inner[j] = i
            break
    return inner


def build(segments: list, labels: list) -> tuple:
    """A molecule from segments and labels, or None and the reason it could not be made."""
    from rdkit import Chem

    if not segments:
        return None, "no segments"
    segments = list(segments)
    ladders = _hashes(segments)
    in_ladder = {k for fam in ladders for k in fam}
    segments = [s for k, s in enumerate(segments) if k not in in_ladder] + list(ladders.values())
    inner = _inner_lines(segments)
    skeleton = [s for k, s in enumerate(segments) if k not in inner]
    extra = {}
    for j, i in inner.items():
        extra[i] = extra.get(i, 0) + 1
    index = {k: n for n, k in enumerate(k for k in range(len(segments)) if k not in inner)}

    pts, owner = [], []
    for n, s in enumerate(skeleton):
        for p in s:
            pts.append(p)
            owner.append(n)
    groups = _cluster(pts, JOIN)
    node_of = {}
    positions = []
    for node, g in enumerate(groups):
        positions.append((statistics.fmean(pts[i][0] for i in g),
                          statistics.fmean(pts[i][1] for i in g)))
        for i in g:
            node_of[i] = node

    reach = LABEL_REACH
    element = {}
    charge = {}
    for lab in labels:
        box = lab.get("box")
        if box:
            near = [n for n, p in enumerate(positions) if _to_box(p, box) <= reach]
        else:
            near = [n for n, p in enumerate(positions)
                    if math.dist(p, (lab["x"], lab["y"])) <= reach]
        if not near:
            positions.append((lab["x"], lab["y"]))
            near = [len(positions) - 1]
        keep = near[0]
        for n in near[1:]:
            for k, v in list(node_of.items()):
                if v == n:
                    node_of[k] = keep
        positions[keep] = (lab["x"], lab["y"])
        element[keep] = lab["element"]
        charge[keep] = lab["charge"]

    used = sorted({node_of[i] for i in range(len(pts))} | set(element))
    renumber = {n: i for i, n in enumerate(used)}
    mol = Chem.RWMol()
    for n in used:
        atom = Chem.Atom(element.get(n, "C"))
        atom.SetFormalCharge(charge.get(n, 0))
        mol.AddAtom(atom)

    seen = set()
    for n, s in enumerate(skeleton):
        ends = [node_of[i] for i in range(len(pts)) if owner[i] == n]
        u, v = renumber[ends[0]], renumber[ends[1]]
        if u == v or (min(u, v), max(u, v)) in seen:
            continue
        seen.add((min(u, v), max(u, v)))
        key = [k for k in range(len(segments)) if k not in inner][n]
        extras = extra.get(key, 0)
        if extras >= 2:
            # Three lines are a triple bond when they are one length. A hash of three marks grows
            # along the bond, and read as a triple bond it makes a two-atom fragment of its own.
            lens = [_len(segments[j]) for j, i in inner.items() if i == key] + [_len(s)]
            if max(lens) / max(min(lens), 0.01) > 1.4:
                extras = 1
        mol.AddBond(u, v, {0: Chem.BondType.SINGLE, 1: Chem.BondType.DOUBLE,
                           2: Chem.BondType.TRIPLE}.get(extras, Chem.BondType.SINGLE))
    try:
        out = mol.GetMol()
        Chem.SanitizeMol(out)
    except Exception as exc:  # the drawing did not make a valid molecule, and that is a result
        return None, f"{type(exc).__name__}: {str(exc)[:120]}"
    return Chem.MolToSmiles(out), ""


def cell(page, cols: list, band: tuple) -> tuple:
    """The segments and characters of one Structure cell, without the table's own rules."""
    a, z = band
    segs = []
    for l in page.lines:
        if not (a + 1 < (l["top"] + l["bottom"]) / 2 < z - 1):
            continue
        if not (cols[2] + 2 < (l["x0"] + l["x1"]) / 2 < cols[3] - 2):
            continue
        p = l.get("pts")
        if p and len(p) == 2:
            segs.append((tuple(p[0]), tuple(p[1])))
    # The filled wedges are deliberately not read. A solid stereo bond is a filled triangle, and
    # leaving it out should strand the atom at its far end -- but in this document the triangle is
    # drawn over a line that is already there, so reading it adds a second bond between the same
    # two atoms by a slightly different pair of points. Adding them took three structures that
    # had been rebuilt exactly and gave their carbons five bonds.
    chars = [c for c in page.chars
             if a < (c["top"] + c["bottom"]) / 2 < z and cols[2] < (c["x0"] + c["x1"]) / 2 < cols[3]]
    return segs, chars


def _reference() -> dict:
    import csv
    with (HOME / "substrates.csv").open() as fh:
        return {r["drug"]: r["smiles"] for r in csv.DictReader(fh)}


def _keys(smiles: str) -> dict:
    from bank_without_selection import _key as tautomer
    from grail_metabolism.metrics import _match_keys
    out = {}
    for crit in ("canonical", "inchi_no_stereo", "inchikey"):
        got = _match_keys([smiles], crit)
        out[crit] = next(iter(got)) if got else None
    out["inchikey_tautomer"] = tautomer(smiles)
    return out


def calibrate() -> dict:
    import pdfplumber

    tables = TAB.extract()["tables"]
    held = _reference()
    results = []
    with pdfplumber.open(SI) as pdf:
        for t in tables:
            row = next(r for r in t["rows"] if r["is_parent"])
            page = pdf.pages[row["page"] - 1]
            marker = [w for w in page.extract_words() if w["text"] == "Table"]
            cols, rows = TAB.grid(page, min(w["top"] for w in marker) if marker else 0.0)
            band = next((a, z) for a, z in zip(rows, rows[1:])
                        if any(cols[0] <= (w["x0"] + w["x1"]) / 2 < cols[1]
                               and a <= (w["top"] + w["bottom"]) / 2 < z
                               and w["text"].startswith(row["id"].split()[0][:6])
                               for w in page.extract_words()))
            segs, chars = cell(page, cols, band)
            smiles, note = build(segs, read_labels(chars))
            ref = held.get(t["drug"], "")
            agree = {}
            if smiles and ref:
                got, want = _keys(smiles), _keys(ref)
                agree = {k: (got[k] is not None and got[k] == want[k]) for k in want}
            results.append({
                "drug": t["drug"], "page": row["page"], "segments": len(segs),
                "characters": len(chars), "reference": ref, "rebuilt": smiles,
                "note": note, "agrees_under": agree,
                "verdict": ("not built" if smiles is None
                            else "exact" if agree.get("canonical") else "wrong"),
            })
    counts = {v: sum(1 for r in results if r["verdict"] == v)
              for v in ("exact", "wrong", "not built")}
    return {
        "provenance": stamp(__file__),
        "inputs": record_inputs([SI, HOME / "substrates.csv"]),
        "what_this_is": "how often a structure rebuilt from the segments it is drawn with is the "
                        "structure this repository already holds, measured on the ten parent "
                        "drugs the benchmark draws in its own tables",
        "criterion": "canonical SMILES after this project's standardiser, which canonicalises "
                     "tautomers and strips stereochemistry; agreement under the other criteria "
                     "is reported per drug",
        "n_parents": len(results),
        "n_exact": counts["exact"], "n_wrong": counts["wrong"],
        "n_unbuilt": counts["not built"],
        "parents": results,
        "fitted_on_what_it_is_scored_on": "The rule that recognises a hashed stereo bond -- how "
              "short a mark is, how many make a ladder, how unequal their lengths must be -- was "
              "arrived at by running this on these ten drawings and reading the failures, so the "
              "score below is an upper bound on what the same code does on a drawing it has not "
              "seen. One constant was not fitted: the distance a bond stops from a label's text "
              "was measured over the hundred labels these cells carry, where the nearest endpoint "
              "is never more than 1.01 points away. A held-out check is available and not yet "
              "run: the metabolite rows state a pathway, so a rebuilt metabolite can be required "
              "to differ from its parent by the formula that pathway implies.",
        "reading": "A parent rebuilt exactly says the geometry of that drawing was read right. A "
                   "parent rebuilt wrongly is a reading error of a kind the metabolite rows will "
                   "make too, and the drug it happened on says which drawing feature caused it. "
                   "The ten parents are the whole key the document offers; Sotorasib is scored by "
                   "the summary without a table here, so there is no eleventh.",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="measure and write nothing")
    args = ap.parse_args()
    blob = calibrate()
    print(f"{blob['n_parents']} parent drawings, scored against the structures already held")
    for r in blob["parents"]:
        mark = {"exact": "  exact", "wrong": "  WRONG", "not built": "UNBUILT"}[r["verdict"]]
        print(f"  {mark}  {r['drug']:<14} {r['segments']:3d} segments  "
              f"{r['note'][:60] if r['note'] else (r['rebuilt'] or '')[:60]}")
    print(f"  exact {blob['n_exact']}, wrong {blob['n_wrong']}, not built {blob['n_unbuilt']}")
    if args.check:
        print("checked, nothing written")
        return 0
    OUT.write_text(json.dumps(blob, indent=1))
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
