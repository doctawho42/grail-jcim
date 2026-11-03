#!/usr/bin/env python3
"""What a comparator's declared setting moves: the candidate list, or only its order.

GLORYxR exposes a site-of-metabolism setting, and this paper reports both of its values as
separate columns because a comparison that turns on an undeclared knob is not a comparison. In
the matched-length control the two columns come out identical to the digit -- same recall, same
slot count, same interval -- and a reader's first reading of two identical rows is that one file
was loaded twice.

It is not that. The setting moves the ORDER of a substrate's candidate list and leaves its
contents alone, and the matched-length control reads each comparator's whole list, so order
cannot reach it. At a fixed budget, which truncates, the same setting does move the cells. This
measures that rather than asserting it, as a partition over the substrates both settings cover:
identical, same multiset in another order, a different multiset, a different length. A partition
that does not sum to the substrates compared is not a measurement, so the sum is checked.

    python scripts/typed_edit/setting_scope.py
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for _p in (str(ROOT), str(ROOT / "scripts"), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _provenance import record_inputs, stamp  # noqa: E402


def load_predictions(spec: str, key: str) -> dict:
    path = ROOT / spec
    if not path.exists():
        sys.exit(f"REFUSING: {spec} is not on disk")
    blob = json.loads(path.read_text())
    preds = blob[key] if key else blob
    if not isinstance(preds, dict) or not preds:
        sys.exit(f"REFUSING: {spec} carries no per-substrate predictions under {key!r}")
    return preds


def partition(a: dict, b: dict, subs) -> dict:
    """Classify every substrate by what the setting did to its list, exhaustively.

    Comparison is on the sorted list and not on the set: a list holding a candidate twice and a
    list holding it once are not the same list, and a set comparison would file them as the same
    contents in another order. The four classes are mutually exclusive by construction and their
    sum is returned beside them, because a partition that does not add up measures nothing.
    """
    out = {"compared": 0, "identical": 0, "same_set_other_order": 0,
           "different_set": 0, "different_length": 0}
    for s in subs:
        if s not in a or s not in b:
            sys.exit(f"REFUSING: {s!r} is covered by only one of the two settings, so the two "
                     f"lists cannot be compared there; a silent skip would shrink the "
                     f"denominator of every share below")
        out["compared"] += 1
        x, y = list(a[s]), list(b[s])
        if x == y:
            out["identical"] += 1
        elif len(x) != len(y):
            out["different_length"] += 1
        elif sorted(x) == sorted(y):
            out["same_set_other_order"] += 1
        else:
            out["different_set"] += 1
    total = sum(out[k] for k in ("identical", "same_set_other_order",
                                 "different_set", "different_length"))
    if total != out["compared"]:
        sys.exit(f"REFUSING: the classes sum to {total} over {out['compared']} substrates "
                 f"compared, so they are not a partition")
    # The direction that makes the finding non-vacuous: if the two sides never differ anywhere,
    # the result is that one file was shipped twice and this is not a statement about a setting.
    out["the_two_sides_never_differ"] = out["identical"] == out["compared"]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default="results/gloryxr_local_preds_default.json")
    ap.add_argument("--b", default="results/gloryxr_local_preds_strict.json")
    ap.add_argument("--key", default="predictions")
    ap.add_argument("--name-a", default="gloryxr_default")
    ap.add_argument("--name-b", default="gloryxr_strict")
    ap.add_argument("--comparison-pools", default="results/widepools_implicit/w*.json")
    ap.add_argument("--out", default=str(ROOT / "results" / "setting_scope.json"))
    args = ap.parse_args()

    a = load_predictions(args.a, args.key)
    b = load_predictions(args.b, args.key)
    both = sorted(set(a) & set(b))
    if not both:
        sys.exit("REFUSING: the two settings cover no substrate in common")

    comparison = set()
    for f in sorted(glob.glob(str(ROOT / args.comparison_pools))):
        comparison |= set(json.loads(Path(f).read_text()).get("references", {}))
    in_comparison = sorted(comparison & set(a) & set(b))
    if not in_comparison:
        sys.exit("REFUSING: no substrate of the comparison set is covered by both settings, so "
                 "the population the manuscript reports on would not be measured at all")

    rows = {"every substrate both settings cover": partition(a, b, both),
            "the comparison set": partition(a, b, in_comparison)}

    report = {
        "provenance": stamp(__file__),
        "inputs": record_inputs([ROOT / args.a, ROOT / args.b]),
        "question": (f"whether the setting separating {args.name_a} from {args.name_b} moves a "
                     f"substrate's candidate list or only the order of it"),
        "settings": {"a": args.name_a, "b": args.name_b},
        "coverage": {"substrates_in_a": len(a), "substrates_in_b": len(b),
                     "covered_by_both": len(both),
                     "of_the_comparison_set": len(in_comparison)},
        "partition": rows,
        "reading": ("same_set_other_order is the setting moving the ranking and nothing else. "
                    "Where it accounts for the substrates, a control that reads a comparator's "
                    "whole list cannot see the setting, and the two columns of that control are "
                    "identical by construction rather than by accident; a fixed budget, which "
                    "truncates, does see it."),
    }
    Path(args.out).write_text(json.dumps(report, indent=1))

    for pop, r in rows.items():
        print(f"\n{pop}: {r['compared']} substrates")
        for k in ("identical", "same_set_other_order", "different_set", "different_length"):
            print(f"    {k:<24s} {r[k]:>6d}  {r[k] / r['compared']:>7.2%}")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
