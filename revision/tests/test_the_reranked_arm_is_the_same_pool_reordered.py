"""Feeding a re-ranked order into the matched-length control, without changing what it measures.

The control truncates both arms to the number of candidates the comparator returned on each
substrate. That makes a lead a lead in ordering rather than in list length, which is the whole
reason it exists. A re-ranked arm can only be read there if it is the SAME pool reordered: if the
file carrying the order were built at a different cap, over a different substrate set, or with a
near-duplicate key collapsed, the control would silently compare two different candidate sets and
report a gap that is partly coverage. The gap being chased is a few thousandths wide, so that is
not a hypothetical amount of error.

So the loader checks the multiset, substrate by substrate, and refuses rather than repairing. It
also has to keep a key's multiplicity: two candidates that normalise to one key consume two slots
in the deployed order and must consume two here, or the arms are read at different lengths.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "scripts" / "typed_edit" / "matched_length_reranked.py"


def _module():
    for p in (ROOT / "scripts", ROOT / "scripts" / "typed_edit"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location("matched_length_reranked_under_test", SRC)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


PARENT = {"S": "pS", "T": "pT"}


def _drop_parent(keys, s):
    return [k for k in keys if k and k != PARENT[s]]


DEPLOYED = {"S": ["a", "b", "c"], "T": ["x", "y"]}


def test_the_same_keys_in_a_different_order_are_accepted_as_given():
    m = _module()
    orders = {"S": ["c", "a", "b"], "T": ["y", "x"]}
    got = m.reranked_arm(orders, ["S", "T"], DEPLOYED, _drop_parent)
    assert got == {"S": ["c", "a", "b"], "T": ["y", "x"]}


def test_the_parent_is_dropped_from_the_reranked_order_as_it_is_from_the_deployed_one():
    """The order the re-ranker writes still carries the substrate's own key; both arms must not."""
    m = _module()
    orders = {"S": ["c", "pS", "a", "b"], "T": ["y", "x"]}
    got = m.reranked_arm(orders, ["S", "T"], DEPLOYED, _drop_parent)
    assert got["S"] == ["c", "a", "b"]


def test_a_substrate_the_order_file_does_not_cover_is_refused():
    m = _module()
    with pytest.raises(SystemExit):
        m.reranked_arm({"S": ["a", "b", "c"]}, ["S", "T"], DEPLOYED, _drop_parent)


def test_an_order_that_gained_a_candidate_is_refused():
    """A larger set would be read at the comparator's length and look like better ordering."""
    m = _module()
    with pytest.raises(SystemExit):
        m.reranked_arm({"S": ["a", "b", "c", "d"], "T": ["x", "y"]},
                       ["S", "T"], DEPLOYED, _drop_parent)


def test_an_order_that_lost_a_candidate_is_refused():
    m = _module()
    with pytest.raises(SystemExit):
        m.reranked_arm({"S": ["a", "b"], "T": ["x", "y"]}, ["S", "T"], DEPLOYED, _drop_parent)


def test_a_repeated_key_keeps_its_multiplicity():
    """Two candidates normalising to one key consume two slots in both arms or neither."""
    m = _module()
    dep = {"S": ["a", "a", "b"]}
    assert m.reranked_arm({"S": ["b", "a", "a"]}, ["S"], dep, _drop_parent) == {"S": ["b", "a", "a"]}
    with pytest.raises(SystemExit):
        m.reranked_arm({"S": ["b", "a"]}, ["S"], dep, _drop_parent)


def test_an_order_file_that_is_not_there_is_refused(tmp_path):
    m = _module()
    with pytest.raises(SystemExit):
        m.load_orders(str(tmp_path / "absent.json"))


def test_an_order_file_with_no_orders_block_is_refused(tmp_path):
    m = _module()
    p = tmp_path / "empty.json"
    p.write_text(json.dumps({"provenance": {}}))
    with pytest.raises(SystemExit):
        m.load_orders(str(p))


def test_an_order_file_is_read_as_written(tmp_path):
    m = _module()
    p = tmp_path / "o.json"
    p.write_text(json.dumps({"orders": {"S": ["c", "a", "b"]}}))
    assert m.load_orders(str(p)) == {"S": ["c", "a", "b"]}


# --- the control that licenses a separate file -------------------------------------------------

def test_the_hardcoded_control_is_the_cell_the_published_artifact_records():
    """The three numbers this producer refuses without are pinned to the publication.

    They are hardcoded rather than read, because reading that artifact would make a file whose
    BioTransformer rows are a tree-local re-run an input of this one. Hardcoding has its own
    failure mode -- the publication moves and the constant does not -- so the tie is asserted
    here instead of being trusted.
    """
    m = _module()
    art = ROOT / "results" / "matched_length.json"
    if not art.exists():
        pytest.skip("the published matched-length artifact is not in this checkout")
    cell = json.loads(art.read_text())["contrasts"][
        f"{m.CONTROL['arm']} - {m.CONTROL['comparator']}"]
    for k in ("recall_ours", "recall_theirs", "gap"):
        assert cell[k] == m.CONTROL[k], f"{k}: published {cell[k]}, hardcoded {m.CONTROL[k]}"


def test_the_constants_come_from_the_published_producer_rather_than_a_second_copy():
    """A duplicated cap, bootstrap size or seed would make the two controls incomparable while
    both kept reporting."""
    m = _module()
    for p in (ROOT / "scripts", ROOT / "scripts" / "typed_edit"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    import matched_length as published
    assert (m.CAP, m.N_BOOT, m.SEED) == (published.CAP, published.N_BOOT, published.SEED)
    assert m.COMPARATORS is published.COMPARATORS
