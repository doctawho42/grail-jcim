#!/usr/bin/env python3
"""Precision for every arm at every budget, because the paper says it reports it.

Section 2.8 states that precision is reported but not used to order systems, and no precision
figure appears in either document. Under incomplete annotation an unannotated but real metabolite
counts as a false positive, so every figure here is pessimistic by an unknown amount and a method
emitting fewer candidates is flattered; that is the reason it does not order anything, and it is
not a reason to leave the claim unsupported.

Precision at k is hits divided by the number of predictions actually inside the window, so an arm
whose list is shorter than the budget is not penalised for the empty slots.
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

from _control_population import absent_from, out_path, population, resolve  # noqa: E402
from _provenance import record_inputs, stamp  # noqa: E402

from _rrf import rrf_order  # noqa: E402

KS = (1, 3, 5, 8, 10, 15, 20, 30, 50)
CAP = 100
COMPARATORS = {
    "MetaTox": ("results/metatox_smirks_preds.json", "predictions"),
    "SyGMa": ("results/sygma_fulltest_predictions.json", None),
    "MetaPredictor": ("artifacts/tier2_1170/metapredictor_preds.json", None),
    # A sixth arm of the comparison table, and it was absent from this analysis while the
    # comparison counted it. An arm reported in one place and omitted in another is the kind of
    # asymmetry this paper spends its introduction objecting to.
    "BioTransformer": ("results/biotransformer_allhuman_one_step_preds.json", None),
    # GLORYx, from the service its authors operate: see gloryx_via_service.py for why a
    # local build is not possible here.
    "GLORYx": ("results/gloryx_service_preds.json", "predictions"),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    # The population names its own pools, its own comparator files and its own output, so the
    # three cannot be set to two different populations by accident.
    ap.add_argument("--population", default="comparison", choices=("comparison", "whole"))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    spec = population(args.population)
    args.out = args.out or out_path("precision_table", args.population)
    comparators = resolve(COMPARATORS, args.population)

    from bank_without_selection import _dedup, _key as tautkey

    def load(pattern):
        pools, refs = {}, {}
        for f in sorted(glob.glob(str(ROOT / pattern))) or [str(ROOT / pattern)]:
            d = json.loads(Path(f).read_text())
            pools.update(d["pools"]); refs.update(d["references"])
        return pools, refs

    pools, refs = load(spec["exhaustive"])
    read_from = sorted(glob.glob(str(ROOT / spec["exhaustive"])))
    small, _ = load(spec["interactive"])
    subs = sorted(s for s in pools if refs.get(s) and s in small)

    def ranked(pool, s, pk):
        keep = sorted(pool, key=lambda c: -c["generator"])[:CAP]
        return [c["key"] for c in rrf_order(keep) if c.get("key") and c["key"] != pk]

    arms = {}
    for s in subs:
        pk = tautkey(s)
        arms.setdefault("GRAIL exhaustive", {})[s] = ranked(pools[s], s, pk)
        arms.setdefault("GRAIL interactive", {})[s] = ranked(small[s], s, pk)
    for name, (rel, key) in comparators.items():
        blob = json.loads((ROOT / rel).read_text())
        preds = blob[key] if key else blob
        for s in subs:
            pk = tautkey(s)
            arms.setdefault(name, {})[s] = [k for k in _dedup(preds.get(s, []), max(KS) + 5)
                                           if k and k != pk][:max(KS)]

    out = {}
    for a, per in arms.items():
        row = {}
        for k in KS:
            num = den = 0
            for s in subs:
                w = per[s][:k]
                num += len(set(w) & set(refs[s])); den += len(w)
            row[str(k)] = round(num / max(den, 1), 4)
        out[a] = row

    rep = {"provenance": stamp(__file__),
           # Which pools this run actually read, so an artifact written against a pool
           # that has since gone can be told from a current one.
           "inputs": record_inputs(read_from),
           "population": {"n": len(subs),
                          "source": spec["name"] + ": " + spec["describes"],
                          # a column this table would have had and the population does not
                          # carry, so a table one column shorter cannot be read as a complete one
                          "comparators_absent": absent_from(COMPARATORS, args.population)},
           "definition": ("hits divided by the predictions inside the window, so an arm whose "
                          "list is shorter than the budget is not charged for the empty slots"),
           "caveat": ("under incomplete annotation an unannotated but real metabolite counts as a "
                      "false positive, so every figure is pessimistic by an unknown amount and an "
                      "arm emitting fewer candidates is flattered"),
           "parent_dropped": True, "cap": CAP,
           "precision_micro": out}
    Path(args.out).write_text(json.dumps(rep, indent=1))
    print(f"{'k':>4}" + "".join(f"{a:>20}" for a in out))
    for k in KS:
        print(f"{k:>4}" + "".join(f"{out[a][str(k)]:>20.4f}" for a in out))
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
