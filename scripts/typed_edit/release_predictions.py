#!/usr/bin/env python3
"""The two arms of this work as per-substrate predictions, so the released grid is whole.

The comparison is offered as a resource: the per-substrate predictions of every arm on one set of
substrates, frozen, with the harness that scores them. For the seven published predictors that was
what the repository held. For our own two arms it was not. The deployment table that carries both
GRAIL columns at every budget is computed from twelve candidate-pool shards of about 200 MB, which
are outside the repository, so the two columns a reader would most want to check were the two they
could not. The bar this paper applies to others is that a comparison requires weights a reader can
obtain; the checkpoints are released and the predictions were not.

What is written here is what the displays actually score, under the convention they apply: the
generator's top CAP candidates, re-ranked by the registered fusion, with a prediction equal to the
substrate dropped. The scores behind the ranking stay out, which keeps this the same kind of object
as a comparator's prediction file rather than a dump of the model's internals.

The file is not written unless it reproduces the table it is cited for. Recall is recomputed at
every budget from the lists about to be written and from the released reference descriptors -- both
files a reader holds -- and compared against the deployment table's own row. A release that does
not reproduce the paper is a release nobody should trust, so the producer refuses rather than
writing it and leaving the check to a reader.

    python scripts/typed_edit/release_predictions.py
    python scripts/typed_edit/release_predictions.py --check   # verify, write nothing
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

from _acs_table import HEADLINE, control_artifact  # noqa: E402
from _rrf import rrf_order  # noqa: E402

# The convention is the deployment table's, not a second one invented here. CAP and the fusion are
# registered decisions and the budgets are the grid's; a copy of any of them that drifted would
# produce a release that scores differently from the table, which is what the refusal below is for.
CAP = 100
KS = (1, 3, 5, 8, 10, 15, 20, 30, 50)
ARMS = ("whole bank", "trained budget")
DESCRIPTORS = ROOT / "results" / "test_reference_descriptors.json"
POOLS = {"whole bank": "results/widepools_fulltest/w*.json",
         "trained budget": "results/widepools_k30_fulltest/w*.json"}
OUT = ROOT / "results" / "grail_predictions_1170.json"


def load(pattern: str) -> tuple:
    """Every shard of one arm's pools, merged, with the files read named for the stamp."""
    pools, files = {}, []
    for f in sorted(glob.glob(str(ROOT / pattern))):
        d = json.loads(Path(f).read_text())
        pools.update(d["pools"])
        files.append(f)
    if not pools:
        raise SystemExit(f"REFUSING: {pattern} matched no candidate pool, so there is nothing to "
                         f"release and an empty file would read as an arm that returns nothing")
    return pools, files


def ranked(pool: list, parent: str) -> list:
    """One substrate's prediction, exactly as the displays form it."""
    keep = sorted(pool, key=lambda c: -c["generator"])[:CAP]
    return [{"smiles": c["smiles"], "key": c["key"]}
            for c in rrf_order(keep) if c["key"] and c["key"] != parent]


def recall(lists: dict, refs: dict, k: int) -> float:
    """Micro recall at k, over the substrates the release carries."""
    subs = sorted(lists)
    hit = sum(len(set(c["key"] for c in lists[s][:k]) & refs[s]) for s in subs)
    return hit / sum(len(refs[s]) for s in subs)


def build() -> dict:
    from bank_without_selection import _key as tautkey

    desc = json.loads(DESCRIPTORS.read_text())
    refs = {s: {r["tautomer_key"] for r in rs} for s, rs in desc["references"].items()}

    arms, read = {}, [str(DESCRIPTORS.relative_to(ROOT))]
    for name, pattern in POOLS.items():
        pools, files = load(pattern)
        read += [str(Path(f).relative_to(ROOT)) for f in files]
        subs = sorted(s for s in pools if s in refs)
        arms[name] = {s: ranked(pools[s], tautkey(s)) for s in subs}

    first, *rest = (set(a) for a in arms.values())
    for other in rest:
        if other != first:
            raise SystemExit(
                f"REFUSING: the two arms cover different substrates -- "
                f"{len(first)} and {len(other)}, {len(first ^ other)} in one and not the other. "
                f"A release whose arms are measured on different populations cannot be read as "
                f"one grid.")

    table = json.loads((ROOT / "results" / control_artifact(
        "deployment_table", HEADLINE)).read_text())
    printed = table["recall_micro"]
    rows, bad = {}, []
    for name in ARMS:
        rows[name] = {}
        for k in KS:
            got = round(recall(arms[name], refs, k), 4)
            rows[name][str(k)] = got
            if got != printed[str(k)][name]:
                bad.append(f"{name} at {k}: release {got}, table {printed[str(k)][name]}")
    if bad:
        raise SystemExit("REFUSING: the release does not reproduce the table it is cited for.\n  "
                         + "\n  ".join(bad))

    n_refs = sum(len(refs[s]) for s in sorted(first))
    return {
        "provenance": stamp(__file__),
        "inputs": record_inputs(read),
        "what_this_is": "the per-substrate predictions of this work's two arms on the evaluated "
                        "test set, as the displays score them, so that the released grid carries "
                        "every arm and not only the published predictors",
        "population": {"substrates": len(first), "references": n_refs},
        "convention": {
            "cap": CAP,
            "selection": "the generator's top CAP candidates of the arm's pool",
            "fusion": "H7 reciprocal rank fusion, k=60, over the generator and filter ranks",
            "parent_dropped": "a prediction whose tautomer key equals the substrate's is removed, "
                              "which is the convention every arm in the comparison is held to",
            "not_included": "the generator and filter scores behind the ranking; a comparator's "
                            "file carries its predictions and so does this one",
        },
        "reproduces": {
            "artifact": control_artifact("deployment_table", HEADLINE),
            "field": "recall_micro",
            "checked_at_budgets": list(KS),
            "recall_micro": rows,
            "note": "recomputed from the predictions below and from the released reference "
                    "descriptors, and equal to the table's row at every budget; the producer "
                    "refuses to write this file when it is not",
        },
        "arms": arms,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="build and verify against the table, and write nothing")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    blob = build()
    for name in ARMS:
        n = sum(len(v) for v in blob["arms"][name].values())
        print(f"{name}: {n} predictions over {len(blob['arms'][name])} substrates, "
              f"mean {n / len(blob['arms'][name]):.1f}")
    print(f"reproduces {blob['reproduces']['artifact']} at "
          f"{len(KS)} budgets for {len(ARMS)} arms")
    if args.check:
        print("checked, nothing written")
        return 0
    out = Path(args.out)
    out.write_text(json.dumps(blob, separators=(",", ":")))
    print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
