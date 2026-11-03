"""What the abstract offers as a resource has to be in the deposit, and has to reproduce the table.

Run: python -m pytest revision/tests/test_the_released_predictions_reproduce_the_table_they_are_cited_for.py -q

The abstract offers the per-substrate predictions of every arm, this work's two included, and the
introduction says any cell of any table can be recomputed from them. For the seven published
predictors that was true: their prediction files are tracked. For our own two arms it was not. The
table that carries both GRAIL columns at every budget reads twelve candidate-pool shards of about
200 MB that are outside the repository, so the two columns a reader would most want to check were
the two they could not. The paper applies the opposite bar to others, and the availability section,
written more carefully than the abstract, says "of every comparator".

So the release carries the two arms as what the displays actually score: the ranked list each arm
returns per substrate, under the convention the displays apply -- the generator's top hundred,
re-ranked by the fusion, with a prediction equal to the substrate dropped. The scores behind the
ranking are not in it, which keeps it the same kind of object as the comparators' files.

A file that merely exists would be a resource nobody can trust, so the gate is reproduction: the
recall row of the deployment table is recomputed here from the released predictions and the
released reference descriptors, and nothing else. Both are in the repository. If the release ever
stops reproducing the table, this goes red rather than the deposit going quietly wrong.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / "results" / "grail_predictions_1170.json"
DESCRIPTORS = ROOT / "results" / "test_reference_descriptors.json"
TABLE = ROOT / "results" / "deployment_table_1170.json"
ARMS = ("whole bank", "trained budget")
KS = (1, 3, 5, 8, 10, 15, 20, 30, 50)


def _json(p: Path) -> dict:
    assert p.exists(), f"{p.relative_to(ROOT)} is not in this checkout"
    return json.loads(p.read_text())


def _refs() -> dict:
    """Each substrate's annotated metabolites, as the tautomer key the table matches on."""
    d = _json(DESCRIPTORS)
    return {s: {r["tautomer_key"] for r in rs} for s, rs in d["references"].items()}


def _recall(arm_lists: dict, refs: dict, k: int) -> float:
    """Micro recall at k: references recovered over references annotated, over the population."""
    subs = sorted(arm_lists)
    hit = sum(len(set(arm_lists[s][:k]) & refs[s]) for s in subs)
    return hit / sum(len(refs[s]) for s in subs)


def test_the_release_is_in_the_repository():
    """The claim is a release, so its absence is a failure and not a skip."""
    d = _json(RELEASE)
    for arm in ARMS:
        assert arm in d["arms"], f"the release carries no {arm!r} arm"
        assert len(d["arms"][arm]) == _json(TABLE)["population"]["n"], (
            f"{arm} covers {len(d['arms'][arm])} substrates, the table's population "
            f"{_json(TABLE)['population']['n']}")


def test_it_reproduces_every_recall_cell_of_the_two_arms():
    d, refs, table = _json(RELEASE), _refs(), _json(TABLE)["recall_micro"]
    assert set(d["arms"]["whole bank"]) <= set(refs), (
        "the release names substrates the released descriptors do not, so a reader holding both "
        "cannot score it")
    for arm in ARMS:
        lists = {s: [c["key"] for c in v] for s, v in d["arms"][arm].items()}
        for k in KS:
            got = round(_recall(lists, refs, k), 4)
            assert got == table[str(k)][arm], (
                f"{arm} at budget {k}: the release gives {got}, the table prints "
                f"{table[str(k)][arm]}")


def test_the_reproduction_is_sensitive_to_what_it_reads():
    """Perturbation control. A recomputation that ignored its input would match the table too."""
    d, refs, table = _json(RELEASE), _refs(), _json(TABLE)["recall_micro"]
    lists = {s: [c["key"] for c in v] for s, v in d["arms"]["whole bank"].items()}
    moved = 0
    for s in sorted(lists):
        if set(lists[s][:1]) & refs[s]:
            lists[s] = lists[s][1:]
            moved += 1
        if moved == 3:
            break
    assert moved == 3, "no substrate recovers a reference in its first slot, so nothing to perturb"
    assert round(_recall(lists, refs, 1), 4) != table["1"]["whole bank"], (
        "dropping three first-slot hits left recall at a budget of one unchanged, so this test "
        "is not reading the lists it claims to")


def test_the_release_carries_predictions_and_not_the_scores_behind_them():
    """The comparators' files are predictions. Ours has to be the same kind of object, or the
    grid offers the reader two things and calls them one."""
    d = _json(RELEASE)
    one = next(iter(d["arms"]["whole bank"].values()))
    assert one, "the first substrate's list is empty"
    assert set(one[0]) == {"smiles", "key"}, f"a prediction carries {sorted(one[0])}"
