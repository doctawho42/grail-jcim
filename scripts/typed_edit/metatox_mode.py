#!/usr/bin/env python3
"""The comparator's own declared knob, swept: MetaTox in each of the two modes it offers.

This paper's argument is that a comparison turning on an undeclared choice is not a comparison,
and it sweeps the knobs its comparators expose -- SyGMa's scenario depth, BioTransformer's step
count, GLORYxR's site-of-metabolism setting. MetaTox exposes a choice of mode, the submission
behind its column chose the SMIRKS mode, and the default mode was submitted too. So the knob can
be swept and this is the sweep.

It is read on a declared subpopulation, because it has to be. The SMIRKS submission came back for
every substrate of the comparison set; the default-mode submission came back for fewer, and no
further submission is available, so the two modes exist together only on the substrates both
cover. That count is in the artifact and in the printout; it is not the population the rest of the
paper reports, and the sweep says so rather than reading as though it were.

The control is what licenses the numbers: on the whole comparison set this file recomputes the
MetaTox column the deployment table commits, and refuses to report anything if it does not come
back to four decimal places.

    python scripts/typed_edit/metatox_mode.py
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for _p in (str(ROOT), str(ROOT / "scripts"), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _provenance import record_inputs, stamp  # noqa: E402
from deployment_table import CAP, KS, N_BOOT, SEED  # noqa: E402


def common_population(a: dict, b: dict, subs) -> list:
    """The substrates both modes came back for, and no others.

    Coverage is presence, not a non-empty list: a method that returned nothing for a substrate
    answered, and dropping it would score the two modes over different populations. An empty
    intersection refuses, because a sweep over nothing still prints a table.
    """
    out = [s for s in subs if s in a and s in b]
    if not out:
        sys.exit("REFUSING: no substrate of this population is covered by both modes, so there "
                 "is no population on which the knob can be swept")
    return out


def verdict(cell: dict) -> str:
    """leads, trails or undecided -- read from the interval, which is what the paper claims on.

    A gap is not a verdict. The manuscript claims a lead for a cell only where that cell's
    interval excludes zero, so a sweep reporting gaps would report movement the paper would not
    have claimed in either direction.
    """
    if not cell["excludes_zero"]:
        return "undecided"
    return "leads" if cell["gap"] > 0 else "trails"


def shifts(reported: dict, other: dict) -> list:
    """The budgets at which the knob changes the verdict, not the ones at which it moves the gap.

    A lead that grows is not a finding; a lead that stops separating, or reverses, is. Both sides
    are named in each row so the direction cannot be read backwards. A budget only one side
    carries refuses rather than being skipped, because then the sweep's width would depend on
    which cells happened to be computed.
    """
    missing = set(reported) ^ set(other)
    if missing:
        sys.exit(f"REFUSING: {', '.join(sorted(missing))} is carried by one mode and not the "
                 f"other, so the two sweeps are not over the same budgets")
    out = []
    for k in sorted(reported, key=int):
        va, vb = verdict(reported[k]), verdict(other[k])
        if va != vb:
            out.append({"k": k, "under_the_reported_mode": va, "under_the_other_mode": vb,
                        "gap_reported": reported[k]["gap"], "gap_other": other[k]["gap"]})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--whole-bank", default="results/widepools_implicit/w*.json")
    ap.add_argument("--trained", default="results/widepools_k30/all.json")
    ap.add_argument("--smirks", default="results/metatox_smirks_preds.json")
    ap.add_argument("--default", default="results/metatox_preds.json")
    ap.add_argument("--out", default=str(ROOT / "results" / "metatox_mode.json"))
    args = ap.parse_args()

    from _rrf import rrf_order
    from bank_without_selection import _dedup, _key as tautkey

    def load(spec):
        pools, refs = {}, {}
        for f in sorted(glob.glob(str(ROOT / spec))) or [str(ROOT / spec)]:
            blob = json.loads(Path(f).read_text())
            pools.update(blob["pools"]); refs.update(blob["references"])
        return pools, refs

    big, refs_b = load(args.whole_bank)
    small, refs_s = load(args.trained)
    refs = {**refs_b, **refs_s}
    declared = sorted(s for s in set(big) & set(small) if refs.get(s))
    real = {s: set(refs[s]) for s in declared}
    parent = {s: tautkey(s) for s in declared}

    def drop_parent(keys, s):
        return [k for k in keys if k and k != parent[s]]

    def ranked(pool, s):
        keep = sorted(pool, key=lambda c: -c["generator"])[:CAP]
        return drop_parent([c["key"] for c in rrf_order(keep)], s)

    smirks = json.loads((ROOT / args.smirks).read_text())["predictions"]
    plain = json.loads((ROOT / args.default).read_text())
    modes = {"smirks": smirks, "default": plain}
    ours = {"whole bank": {s: ranked(big[s], s) for s in declared},
            "trained budget": {s: ranked(small[s], s) for s in declared}}
    theirs = {m: {s: drop_parent(_dedup(p.get(s, []), CAP + 5), s) for s in declared}
              for m, p in modes.items()}

    def micro(order, subs, k):
        hit = tot = 0
        for s in subs:
            hit += len(set(order.get(s, [])[:k]) & real[s])
            tot += len(real[s])
        return hit / tot if tot else 0.0

    # The control. The SMIRKS column over the declared population is a committed quantity, and
    # nothing below is reported unless it comes back.
    dep = json.loads((ROOT / "results" / "deployment_table.json").read_text())["recall_micro"]
    off = []
    for k in KS:
        if str(k) not in dep or "metatox" not in dep[str(k)]:
            continue
        got = round(micro(theirs["smirks"], declared, k), 4)
        if abs(got - dep[str(k)]["metatox"]) > 1e-9:
            off.append(f"k={k}: {got} against the committed {dep[str(k)]['metatox']}")
    if off:
        sys.exit("REFUSING: this file does not reproduce the committed MetaTox column over the "
                 "declared population, so its own numbers are not comparable with the paper's. "
                 + "; ".join(off))

    both = common_population(smirks, plain, declared)
    U = np.array([len(real[s]) for s in both], dtype=float)
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(both), (N_BOOT, len(both)))
    denom = np.maximum(U[idx].sum(axis=1), 1)

    def contrast(ours_lists, their_lists, k):
        o = np.array([len(set(ours_lists[s][:k]) & real[s]) for s in both], dtype=float)
        t = np.array([len(set(their_lists[s][:k]) & real[s]) for s in both], dtype=float)
        d = o - t
        bt = d[idx].sum(axis=1) / denom
        lo, hi = float(np.quantile(bt, .025)), float(np.quantile(bt, .975))
        return {"recall_ours": round(float(o.sum() / U.sum()), 4),
                "recall_theirs": round(float(t.sum() / U.sum()), 4),
                "gap": round(float(d.sum() / U.sum()), 4),
                "ci95": [round(lo, 4), round(hi, 4)],
                "excludes_zero": bool(lo > 0 or hi < 0)}

    cells = {arm: {m: {str(k): contrast(ours[arm], theirs[m], k) for k in KS} for m in modes}
             for arm in ours}
    moved = {arm: shifts(cells[arm]["smirks"], cells[arm]["default"]) for arm in ours}
    emitted = {m: round(float(np.mean([len(theirs[m][s]) for s in both])), 2) for m in modes}

    report = {
        "provenance": stamp(__file__),
        "inputs": record_inputs([ROOT / args.smirks, ROOT / args.default,
                                 ROOT / "results" / "deployment_table.json"]),
        "question": ("what the comparator's own declared choice of mode is worth, swept the way "
                     "this paper sweeps the other comparators' declared knobs"),
        "modes": {"smirks": "the SMIRKS-rule mode, which is the mode the reported column is",
                  "default": "the mode the service applies when the submitter chooses none"},
        "population": {
            "declared_comparison_set": len(declared),
            "covered_by_both_modes": len(both),
            "not_covered_by_the_default_mode": len(declared) - len(both),
            "n_references": int(U.sum()),
            "note": ("the sweep is read on the substrates both submissions came back for, which "
                     "is NOT the population the rest of the paper reports; no further "
                     "default-mode submission is available")},
        "mean_emitted_on_that_population": emitted,
        "control": {"what": "the MetaTox column of results/deployment_table.json over the "
                            f"{len(declared)} declared substrates",
                    "reproduced": True},
        "bootstrap": {"n": N_BOOT, "seed": SEED},
        "contrasts": cells,
        "verdicts_the_mode_moves": moved,
        "reading": ("a row of verdicts_the_mode_moves is a budget at which the choice of mode "
                    "decides whether this work's arm leads, trails or neither. A gap that moves "
                    "without crossing is not listed, because the paper claims nothing from a "
                    "gap whose interval covers zero."),
    }
    Path(args.out).write_text(json.dumps(report, indent=1))

    print(f"\ndeclared population {len(declared)}; both modes cover {len(both)} "
          f"({int(U.sum())} known metabolites)")
    print(f"mean emitted on that population: {emitted}")
    for arm in ours:
        print(f"\n--- {arm} ---")
        print(f"{'k':>3s} {'ours':>7s} {'SMIRKS':>8s} {'gap':>9s} {'sep':>4s}   "
              f"{'default':>8s} {'gap':>9s} {'sep':>4s}")
        for k in KS:
            a, b = cells[arm]["smirks"][str(k)], cells[arm]["default"][str(k)]
            print(f"{k:>3d} {a['recall_ours']:>7.4f} {a['recall_theirs']:>8.4f} "
                  f"{a['gap']:>+9.4f} {('yes' if a['excludes_zero'] else 'no'):>4s}   "
                  f"{b['recall_theirs']:>8.4f} {b['gap']:>+9.4f} "
                  f"{('yes' if b['excludes_zero'] else 'no'):>4s}")
        for row in moved[arm]:
            print(f"    k={row['k']}: {row['under_the_reported_mode']} under the reported mode, "
                  f"{row['under_the_other_mode']} under the other")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
