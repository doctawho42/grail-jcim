#!/usr/bin/env python3
"""Provenance checking that does not stop one level from the number.

`_provenance.stamp` records which code wrote an artifact and `record_inputs` records the digests of
the files it read. `audit_artifact_provenance.py` then verifies, for a pinned list, that the
producer has not moved since it ran. That apparatus is one level deep. It asks whether an
artifact's own producer is current; it never asks whether the artifacts that artifact READ have
producers at all.

The difference is not hypothetical here. `results/deployment_table.json` is stamped, pinned and
current, and every recall figure in the released column comes out of it. Its candidate pools come
from `results/widepools_k30/all.json`, which records the checkpoints it used, by digest, and
records nothing about what turned those checkpoints into pools. `results/retraining_spread.json` is
in the same position: the spread its numbers are quoted in units of is computed from three
`results/seedpools/interactive_seed*.json` files that name no producer and that no script in this
repository writes. Verifying the consumer tells a reader nothing about that.

So this walks the edge instead of the node. For every tracked artifact under `results/` that
records its inputs, it follows each JSON input and asks the same question of it, and reports the
ones that cannot answer.

Three answers are distinguished, because they are three different situations and lumping them
together would make the count useless:

    stamped        the input carries a producer, and the existing audit already covers it
    half           the input records what it READ, by digest, but not what wrote it. A reader can
                   check the inputs were the intended ones and cannot check the step between them
    bare           the input is a mapping from substrate to predictions with no header at all, so
                   there is nowhere for provenance to live without changing the format

Files this project does not produce are declared, with the reason, rather than being silently
absent from the count: a third party's database has no producer of ours by definition and its
provenance is a citation. A census that called those defects would be a detector nobody could
trust, which is the failure mode this file exists to avoid rather than to repeat.

    python scripts/audit_input_provenance.py            # census, exit 0
    python scripts/audit_input_provenance.py --strict   # exit 1 if any consumer got worse
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[0]
for _p in (str(ROOT), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _provenance import stamp  # noqa: E402

# Inputs this project does not write. Their provenance is a citation, not a stamp, and counting
# them as unprovenanced would inflate the census with things no change here could fix.
NOT_OURS = {
    "grail_metabolism/resources/external/":
        "third-party rule and reaction databases, redistributed under their own terms or read in "
        "place; NOTICE.md carries the attribution and the producer records each digest",
    "artifacts/tier2/biotransformer/":
        "BioTransformer's own distribution, obtainable from its project",
    "artifacts/tier2/metapredictor_src/":
        "MetaPredictor's own source checkout",
    "artifacts/external/gao2026/":
        "the prediction files Gao et al. deposited on Zenodo (10.5281/zenodo.17878495, CC BY 4.0)",
    "docs/benchmark/data/":
        "published benchmark test sets, read as distributed",
}

# The count the tree is expected to be at. A census that only ever reports is a census nobody
# reads; --strict fails when a consumer acquires an unstamped input it did not have, which is the
# direction that matters. Raising this number is a decision, not a fix.
#
# Raised from 24 to 27 for the three matched-arm summaries, rulegate_id_gate_result.json,
# rulegate_candfilter_result.json and rulegate_survivors_summary.json. Each reads the
# metrics.json of a training run under results/rulegate_cpu/, and those are written by the
# training harness rather than by a stamped producer, so the step that made their inputs cannot
# be checked even though the summaries themselves record what they read, by digest. The arms are
# reported in the supporting information, so the artifacts stay and the census says plainly that
# they are unverifiable one step back.
#
# Raised from 27 to 36 for nine artifacts this revision added: the learned re-ranker and its
# comparison, the matched-length re-ranked arm, the MetaTox mode axis with its two submissions
# and its tie-break sensitivity, the BioTransformer step contrast, and the deployment table on
# the whole evaluated split. Between them they read 42 input records with no producer, and every
# one falls in a class the existing 27 already read: 24 are shards of a sweep this repository
# writes and does not track, 17 are prediction files delivered by the comparators' own authors
# and produced by no script here, and one is the reference set. Over the same change the count of
# STAMPED distinct inputs rose from 18 to 28, so the apparatus did not get looser.
#
# That is also the weakness of this number, and it should be said rather than discovered later: it
# counts CONSUMERS, so it rises whenever the tree gains artifacts, and a rise cannot be told from
# a loss of provenance without opening the artifact. A share of tracked artifacts would separate
# the two. The count is kept because it is the one a --strict run can fail on without a second
# artifact to compare against, and the classes above are recorded so the next raise has something
# to be checked against.
#
# Raised from 36 to 40 for the four controls recomputed at the whole evaluated test set: the
# criterion sweep, the matched-length contrast, the precision table and the error by chemistry.
# Between them they read 26 input records with no producer -- 19 pool shards of a sweep this
# repository writes and does not track, and 7 prediction files delivered by the comparators' own
# authors -- and not one of those inputs is new. Every distinct input they read was already read
# by one of the 36, and the distinct-input tally below is unchanged in every class, stamped 28,
# half 37, bare 35, unreadable 0 and third-party 3. So this raise is the weakness named in the
# paragraph above, measured: four more consumers of the same unprovenanced inputs, and no step
# that lost a producer. EXPECTED_INPUTS is what would have caught the other case.
#
# Raised from 40 to 41 for results/grail_predictions_1170.json, the release of this work's own two
# arms as per-substrate predictions. It reads the twelve candidate-pool shards the deployment table
# reads and the released reference descriptors, so 12 of its 13 recorded inputs cannot name a
# producer and every one of the twelve was already in the census. The thirteenth is stamped, which
# is the whole of the move in the distinct-input tally: stamped 28 to 29, and half, bare and
# unreadable unchanged at 37, 35 and 0. Releasing a file therefore made the consumer count worse
# and left the number below untouched, which is the clearest statement available of what each of
# the two counts is for.
EXPECTED_CONSUMERS = 41

# The distinct inputs that cannot say what produced them, which is the number the paragraph above
# says is missing. It does not move when the tree gains an artifact that reads what is already
# read, and it rises exactly when a step loses its producer or a new unprovenanced file is read
# for the first time. Both halves of the census are now failable, and this is the half that
# answers the question a reader asks.
EXPECTED_INPUTS = 72


def _tracked() -> set:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True)
    return set(out.stdout.split())


def _classify(path: Path) -> str:
    """stamped, half, bare, or unreadable -- what this file records about where it came from."""
    try:
        blob = json.loads(path.read_text())
    except Exception:
        return "unreadable"
    if not isinstance(blob, dict):
        return "bare"
    if isinstance(blob.get("provenance"), dict) and blob["provenance"].get("script_path"):
        return "stamped"
    # Records the files it read, by digest, but not the step that read them. A reader can check the
    # inputs and not the transformation.
    for field in ("checkpoints", "inputs", "config", "source"):
        if field in blob:
            return "half"
    return "bare"


def _why_not_ours(rel: str):
    for prefix, reason in NOT_OURS.items():
        if rel.startswith(prefix):
            return reason
    return None


def build() -> dict:
    tracked = _tracked()
    consumers, tally = [], {"stamped": 0, "half": 0, "bare": 0, "unreadable": 0, "not_ours": 0}
    seen_inputs = {}

    for rel in sorted(p for p in tracked if p.startswith("results/") and p.endswith(".json")):
        path = ROOT / rel
        try:
            blob = json.loads(path.read_text())
        except Exception:
            continue
        if not isinstance(blob, dict) or not isinstance(blob.get("inputs"), list):
            continue
        weak = []
        for item in blob["inputs"]:
            ip = item.get("path") if isinstance(item, dict) else None
            if not ip or not ip.endswith(".json"):
                continue
            target = ROOT / ip
            if not target.exists():
                continue
            reason = _why_not_ours(ip)
            if reason:
                if ip not in seen_inputs:
                    tally["not_ours"] += 1
                seen_inputs[ip] = "not_ours"
                continue
            kind = _classify(target)
            if ip not in seen_inputs:
                tally[kind] += 1
            seen_inputs[ip] = kind
            if kind in ("half", "bare", "unreadable"):
                weak.append({"input": ip, "records": kind, "tracked": ip in tracked})
        if weak:
            consumers.append({"artifact": rel, "inputs_recorded": len(blob["inputs"]),
                              "inputs_without_a_producer": len(weak), "which": weak})

    consumers.sort(key=lambda c: -c["inputs_without_a_producer"])
    return {
        "provenance": stamp(__file__),
        "question": ("whether the artifacts a manuscript number is computed from can themselves "
                     "say what produced them, which the existing audit never asks"),
        "how": ("every tracked results/*.json that records its inputs is walked, each JSON input "
                "is classified by what it records about its own origin, and inputs this project "
                "does not write are declared rather than counted"),
        "classes": {
            "stamped": "carries a producer; the existing audit covers it",
            "half": "records what it read, by digest, but not what wrote it",
            "bare": "no header at all, so provenance has nowhere to live without a format change",
            "not_ours": "a third party's file; its provenance is a citation",
        },
        "distinct_inputs_by_class": tally,
        "consumers_reading_an_input_without_a_producer": len(consumers),
        "expected": EXPECTED_CONSUMERS,
        "consumers": consumers,
        "not_ours": NOT_OURS,
        "reading": ("A consumer on this list is not wrong. It is unverifiable one step back: its "
                    "own producer can be checked and the step that made its inputs cannot. The "
                    "ones that matter most are the ones whose numbers reach the manuscript."),
    }


def unprovenanced_inputs(report: dict) -> int:
    """Distinct inputs that cannot say what produced them, over every class that cannot."""
    t = report["distinct_inputs_by_class"]
    return t["half"] + t["bare"] + t["unreadable"]


def refusals(report: dict) -> list:
    """Why a --strict run would refuse, as sentences, or an empty list.

    Kept out of main() so a refusal can be exercised on a report the caller builds. A gate nobody
    has seen go red is a gate nobody knows the direction of, and the only way to see this one
    without making the tree worse is to hand it a report that is.
    """
    out = []
    n = report["consumers_reading_an_input_without_a_producer"]
    if n > EXPECTED_CONSUMERS:
        out.append(f"{n} consumers read an input with no producer, against the "
                   f"{EXPECTED_CONSUMERS} this tree is known to have. Something acquired one. "
                   f"Either stamp the new input's producer or raise EXPECTED_CONSUMERS "
                   f"deliberately.")
    inputs = unprovenanced_inputs(report)
    if inputs > EXPECTED_INPUTS:
        out.append(f"{inputs} distinct inputs cannot say what produced them, against the "
                   f"{EXPECTED_INPUTS} this tree is known to read. A step lost its producer, or a "
                   f"file nothing here writes is being read for the first time. Stamp it, declare "
                   f"it in NOT_OURS with the reason, or raise EXPECTED_INPUTS deliberately.")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 when more consumers read an unprovenanced input than expected")
    args = ap.parse_args()

    report = build()
    out = ROOT / "results" / "input_provenance.json"
    out.write_text(json.dumps(report, indent=1))

    t = report["distinct_inputs_by_class"]
    print(f"\n  distinct JSON inputs read by tracked artifacts")
    for k in ("stamped", "half", "bare", "unreadable", "not_ours"):
        print(f"    {k:12s} {t[k]}")
    n = report["consumers_reading_an_input_without_a_producer"]
    print(f"\n  {n} tracked artifacts read at least one input that cannot say what produced it")
    for c in report["consumers"][:8]:
        print(f"    {c['artifact']:52s} {c['inputs_without_a_producer']} of "
              f"{c['inputs_recorded']}")
    if len(report["consumers"]) > 8:
        print(f"    ... and {len(report['consumers']) - 8} more, all in the artifact")
    print(f"\nwrote {out.relative_to(ROOT)}")

    print(f"  {unprovenanced_inputs(report)} of them cannot say what produced them, against the "
          f"{EXPECTED_INPUTS} this tree is known to read")

    why = refusals(report)
    for line in why:
        print(f"\nREFUSING: {line}", file=sys.stderr)
    return 1 if (args.strict and why) else 0


if __name__ == "__main__":
    raise SystemExit(main())
