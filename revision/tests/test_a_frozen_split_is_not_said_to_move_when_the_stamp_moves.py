"""A manifest written by a different run is not a split that moved.

Run: python -m pytest revision/tests/test_a_frozen_split_is_not_said_to_move_when_the_stamp_moves.py -q

paper2/split_manifest.json fingerprints a split the repository cannot hold, and
freeze_split.py --verify recomputes the fingerprint and names every leaf that moved. Beside the
digests it carries a stamp: the commit the freeze was taken at, the digest of the script that took
it, and whether the working tree was dirty at the time. Those leaves are about the run, not about
the data, and they move for reasons the split knows nothing about -- committing the tree moves
git_dirty, editing the producer moves source_sha256.

Comparing them was how --verify came to report "the split moved since the freeze" with every
digest of the data identical, on the single leaf provenance.git_dirty: the freeze had been taken
from a dirty tree and the verification was run from a clean one. A reader who trusted the message
would have gone looking for a swapped dataset.

The exemption has to be narrow or it eats the gate it sits in, so the tests below assert both
directions on the same artifact: a moved digest is a moved split, including a third party's, and a
moved stamp is not. The two third-party leaves that name a path on the machine are exempt for a
different reason -- they are where a comparator's files sat, which differs per checkout -- and the
digest beside them is not.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "paper2" / "split_manifest.json"


def _freeze():
    spec = importlib.util.spec_from_file_location(
        "_freeze_split", ROOT / "scripts" / "typed_edit" / "freeze_split.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_freeze_split"] = mod
    spec.loader.exec_module(mod)
    return mod


pytestmark = pytest.mark.skipif(not MANIFEST.exists(),
                                reason="the split manifest is not in this checkout")


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text())


def _moved(path: tuple, value):
    """The two lists compare() returns for the manifest with one leaf changed to `value`."""
    new = copy.deepcopy(_manifest())
    node = new
    for k in path[:-1]:
        node = node[k]
    assert path[-1] in node, f"the manifest has no leaf {'.'.join(path)}"
    node[path[-1]] = value
    return _freeze().compare(_manifest(), new)


def test_a_manifest_compared_against_itself_moves_nothing():
    """Positive control. Every assertion below reads a difference, and a comparison that found a
    difference everywhere would satisfy them without measuring anything."""
    moved, noted = _freeze().compare(_manifest(), _manifest())
    assert moved == [] and noted == [], f"moved {moved}, noted {noted}"


def test_a_moved_digest_is_the_split_moving():
    moved, noted = _moved(("files", "test", "sha256"), "0" * 64)
    assert len(moved) == 1 and "files.test.sha256" in moved[0], moved
    assert noted == [], noted


def test_a_moved_substrate_count_is_the_split_moving():
    moved, _ = _moved(("splits", "test", "substrates", "n"), 1)
    assert len(moved) == 1 and "splits.test.substrates.n" in moved[0], moved


def test_a_moved_bank_digest_is_the_split_moving():
    moved, _ = _moved(("bank", "sha256"), "0" * 64)
    assert len(moved) == 1 and "bank.sha256" in moved[0], moved


def test_a_third_partys_digest_is_the_split_moving():
    """The per-checkout exemption covers where a comparator's files sat, not what is in them."""
    moved, _ = _moved(("third_party", "sygma", "version"), "not the version that was pinned")
    assert len(moved) == 1 and "third_party.sygma.version" in moved[0], moved


def test_a_dirty_tree_at_the_freeze_is_not_the_split_moving():
    moved, noted = _moved(("provenance", "git_dirty"), not _manifest()["provenance"]["git_dirty"])
    assert moved == [], moved
    assert len(noted) == 1 and "provenance.git_dirty" in noted[0], noted


def test_an_edited_producer_is_not_the_split_moving():
    moved, noted = _moved(("provenance", "source_sha256"), "0" * 64)
    assert moved == [], moved
    assert len(noted) == 1 and "provenance.source_sha256" in noted[0], noted


def test_the_commit_the_freeze_was_taken_at_is_not_the_split_moving():
    moved, noted = _moved(("provenance", "git_commit"), "0" * 40)
    assert moved == [], moved
    assert len(noted) == 1 and "provenance.git_commit" in noted[0], noted


def test_where_a_third_party_sat_on_the_machine_is_not_the_split_moving():
    moved, noted = _moved(("third_party", "sygma", "module"), "<somewhere else>")
    assert moved == [], moved
    assert len(noted) == 1 and "third_party.sygma.module" in noted[0], noted


def test_every_leaf_that_moved_is_named_in_one_list_or_the_other():
    """The two lists have to exhaust the differences, or a leaf can move in silence.

    The form this replaces dropped the exempt leaves before recursing, so nothing printed them and
    a reader could not tell a manifest written by another run from one that matched.
    """
    new = copy.deepcopy(_manifest())
    new["files"]["test"]["sha256"] = "0" * 64
    new["provenance"]["git_dirty"] = not new["provenance"]["git_dirty"]
    new["third_party"]["sygma"]["module"] = "<somewhere else>"
    moved, noted = _freeze().compare(_manifest(), new)
    assert len(moved) == 1, moved
    assert len(noted) == 2, noted


def _leaves(node, path=""):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _leaves(v, f"{path}.{k}" if path else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _leaves(v, f"{path}[{i}]")
    else:
        yield path, node


def test_the_producer_records_no_path_from_the_machine_it_ran_on():
    """A tracked manifest must be writable without a hand edit afterwards.

    The committed manifest says "<external baseline biotransformer>" and "<installed package
    sygma>" where this producer wrote an absolute path on the machine that ran it, so somebody
    scrubbed two leaves by hand before committing it -- and --verify could not see that, because
    those were two of the three keys it dropped before comparing. Asserting the committed file
    would pass on the scrub; this asserts what the producer returns.
    """
    for path, value in _leaves(_freeze().third_party()):
        assert not (isinstance(value, str) and value.startswith("/")), (
            f"third_party.{path} records {value!r}, a path on the machine that ran the freeze; "
            f"record that it was found and the digest of what was found instead")


def test_the_committed_manifest_records_no_path_either():
    for path, value in _leaves(_manifest()):
        assert not (isinstance(value, str) and value.startswith("/")), f"{path} = {value!r}"
