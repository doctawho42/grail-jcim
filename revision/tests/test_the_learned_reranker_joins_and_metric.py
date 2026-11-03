"""What the learned re-ranker must get right before it is allowed to report a number.

Three failure modes, all silent, all of which would make the comparison against the deployed
order meaningless rather than wrong-looking:

1. The join. Per-template scores live in results/aggregation_shards*, keyed by candidate SMILES;
   the scores the pool carries live in the pool files. The 291 run recorded 358 candidates the
   pool does not carry, so the join is lossy in at least one direction. A candidate the shards
   lack must keep its place in the ranking with an explicit zero-template feature, not vanish:
   dropping it shrinks the candidate set and the deployed order would then be scored on a
   different set from the learned one.

2. The metric. recall@k has to honour the declared convention -- a prediction whose key equals
   the substrate's is dropped before the budget bites -- and has to be able to go DOWN. A metric
   that cannot fall on a worse order cannot certify a better one.

3. The set invariant. The learned order and the deployed order must be permutations of the same
   multiset of keys. Any feature step that filters candidates breaks the only comparison this
   work is for.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "scripts" / "typed_edit" / "rerank_learned.py"


def _module():
    for p in (ROOT / "scripts", ROOT / "scripts" / "typed_edit"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location("rerank_learned_under_test", SRC)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# --- 2. the metric -------------------------------------------------------------------------

def test_recall_at_k_drops_the_parent_before_the_budget():
    m = _module()
    # one substrate, 3 references, an order whose first slot is the parent
    order = {"S": ["PARENT", "A", "B", "Z"]}
    refs = {"S": {"A", "B", "C"}}
    # with the parent occupying a slot, k=2 would reach only A; dropped, it reaches A and B
    assert m.recall_at(order, refs, 2, parent={"S": "PARENT"}) == pytest.approx(2 / 3)


def test_recall_at_k_can_fall_on_a_worse_order():
    """Non-vacuous by construction: the same keys in a worse order must score lower."""
    m = _module()
    refs = {"S": {"A", "B"}}
    good = m.recall_at({"S": ["A", "B", "X", "Y"]}, refs, 2, parent={"S": "P"})
    bad = m.recall_at({"S": ["X", "Y", "A", "B"]}, refs, 2, parent={"S": "P"})
    assert good == pytest.approx(1.0)
    assert bad == pytest.approx(0.0)
    assert bad < good


def test_recall_at_k_is_micro_the_ratio_of_sums():
    """Two substrates with unequal reference counts weigh by their counts, not equally."""
    m = _module()
    order = {"S1": ["A"], "S2": ["X"]}
    refs = {"S1": {"A"}, "S2": {"X", "Y", "Z"}}
    # micro: 2 hits of 4 references
    assert m.recall_at(order, refs, 5, parent={}) == pytest.approx(2 / 4)


# --- 1. the join ---------------------------------------------------------------------------

def test_a_candidate_the_shards_lack_keeps_its_place_with_zero_templates():
    m = _module()
    pool = [{"smiles": "CCO", "generator": 0.9, "filter": 0.5, "combined": 0.45, "key": "K1"},
            {"smiles": "CCN", "generator": 0.8, "filter": 0.4, "combined": 0.32, "key": "K2"}]
    shards = {"CCO": [0.7, 0.6]}          # CCN is missing
    rows, miss = m.join_pool_with_templates(pool, shards)
    assert len(rows) == 2, f"a missing candidate was dropped from the ranking: {rows}"
    by_key = {r["key"]: r for r in rows}
    # The count lives in the feature vector rather than beside the scores, so there is one
    # source of truth for it; what this pins is that the candidate survives the join and
    # reaches the model as a zero rather than as an absence.
    assert by_key["K2"]["template_scores"] == []
    assert m.features(by_key["K2"])["n_templates"] == 0
    assert m.features(by_key["K2"])["tmpl_noisy_or"] == 0.0
    assert miss["pool_candidates_without_template_scores"] == 1


def test_a_shard_candidate_the_pool_lacks_is_counted_not_ignored():
    m = _module()
    pool = [{"smiles": "CCO", "generator": 0.9, "filter": 0.5, "combined": 0.45, "key": "K1"}]
    shards = {"CCO": [0.7], "CCC": [0.3]}   # CCC is not in the pool
    rows, miss = m.join_pool_with_templates(pool, shards)
    assert len(rows) == 1
    assert miss["template_candidates_not_in_the_pool"] == 1


# --- 3. the set invariant -------------------------------------------------------------------

def test_the_learned_order_is_a_permutation_of_the_deployed_one():
    m = _module()
    pool = [{"smiles": f"C{i}", "generator": 0.9 - i / 10, "filter": 0.5,
             "combined": 0.4, "key": f"K{i}"} for i in range(6)]
    shards = {f"C{i}": [0.5] for i in range(6)}
    rows, _ = m.join_pool_with_templates(pool, shards)
    learned = m.order_by_score(rows, {r["key"]: 1.0 / (1 + i) for i, r in enumerate(rows)})
    deployed = m.deployed_order(pool)
    assert sorted(learned) == sorted(deployed), (
        "the two orders rank different key sets, so comparing their recall compares two "
        f"different problems: learned={sorted(learned)} deployed={sorted(deployed)}")


def test_features_expose_the_duplication_signal_the_deployed_rule_collapses():
    """The point of the ranker: how many templates produced a candidate, and their spread,
    enter as features instead of being collapsed into one noisy-or probability."""
    m = _module()
    one = m.features({"generator": 0.4, "filter": 0.6, "combined": 0.24,
                      "key": "K", "template_scores": [0.4]})
    many = m.features({"generator": 0.95, "filter": 0.6, "combined": 0.57,
                       "key": "K", "template_scores": [0.3] * 20})
    assert one["n_templates"] == 1 and many["n_templates"] == 20
    assert many["tmpl_max"] == pytest.approx(0.3)
    assert many["tmpl_noisy_or"] > many["tmpl_max"], (
        "noisy-or over twenty near-duplicates must exceed the best single template, which is "
        "the inflation the ranker is given the raw count to discount")


# --- positional features --------------------------------------------------------------------

def test_rank_features_give_the_model_the_deployed_position():
    """The deployed order is rank-based: reciprocal-rank fusion of two orders. A model given
    only raw scores has to rediscover that from scratch; given the fused position it can only
    improve on it, which is the question worth asking of a re-ranker.
    """
    m = _module()
    rows = [{"smiles": "A", "generator": 0.9, "filter": 0.1, "combined": 0.09,
             "key": "KA", "template_scores": [0.9]},
            {"smiles": "B", "generator": 0.5, "filter": 0.9, "combined": 0.45,
             "key": "KB", "template_scores": [0.5]},
            {"smiles": "C", "generator": 0.1, "filter": 0.5, "combined": 0.05,
             "key": "KC", "template_scores": [0.1]}]
    rf = m.rank_features(rows)
    assert len(rf) == 3
    # best generator is row 0, best filter is row 1 -- ranks are 0-based and per substrate
    assert rf[0]["rank_generator"] == 0
    assert rf[1]["rank_filter"] == 0
    assert rf[2]["rank_generator"] == 2
    # the deployed position must agree with the deployed order itself, or the feature is a
    # different ranking from the one being improved on
    dep = m.deployed_order(rows)
    pos = {r["key"]: rf[i]["rank_deployed"] for i, r in enumerate(rows)}
    assert [k for k, _ in sorted(pos.items(), key=lambda kv: kv[1])] == dep
    assert all(r["n_candidates"] == 3 for r in rf)


def test_rank_features_are_not_constant_across_a_substrate():
    """A positional feature that is the same for every candidate carries nothing; this would
    pass vacuously if rank_features returned a fixed value, which is how the last silent
    feature bug in this repository looked."""
    m = _module()
    rows = [{"smiles": str(i), "generator": i / 10, "filter": 0.5, "combined": 0.1,
             "key": f"K{i}", "template_scores": [0.5]} for i in range(5)]
    rf = m.rank_features(rows)
    assert len({r["rank_generator"] for r in rf}) == 5
    assert len({r["rank_deployed"] for r in rf}) == 5


# --- chemistry of the transformation --------------------------------------------------------

def test_delta_features_are_product_minus_substrate():
    """Every feature so far is a score or a position. None says what the transformation DID,
    which is the one thing that separates a sulfate from an arbitrary hydroxylation -- and the
    classes the exhaustive arm fails on are exactly the classic conjugations.
    """
    m = _module()
    rdkit = pytest.importorskip("rdkit")  # noqa: F841
    d = m.delta_features("CCO", "CCOS(=O)(=O)O")        # sulfation
    assert d["d_heavy"] == 4 and d["d_S"] == 1 and d["d_O"] == 3
    d = m.delta_features("CCO", "CC=O")                 # dehydrogenation, loses two hydrogens
    assert d["d_heavy"] == 0 and d["d_O"] == 0
    d = m.delta_features("CCOC(C)=O", "CCO")            # hydrolysis: a fragment
    assert d["d_heavy"] < 0, "a cleavage product must register as losing heavy atoms"


def test_a_candidate_identical_to_the_substrate_has_zero_deltas():
    m = _module()
    pytest.importorskip("rdkit")
    d = m.delta_features("c1ccccc1O", "c1ccccc1O")
    assert all(v == 0 for k, v in d.items() if k.startswith("d_")), d


def test_an_unparseable_candidate_is_marked_rather_than_silently_zeroed():
    """A zero delta and an unknown delta are different claims. If a bad SMILES returned zeros
    it would be indistinguishable from an unchanged molecule, which is a real row in this data.
    """
    m = _module()
    pytest.importorskip("rdkit")
    d = m.delta_features("CCO", "this is not a molecule")
    assert d["parsed"] == 0
    good = m.delta_features("CCO", "CC=O")
    assert good["parsed"] == 1


# --- targeting the budget the comparison is read at -----------------------------------------

def test_decision_weights_boost_only_what_recall_at_k_can_change():
    """Pointwise log-loss spends its capacity on the whole list; recall at a fixed budget is
    decided by two populations only -- positives sitting below the budget, which have to come
    up, and negatives sitting above it, which have to go down. Everything else is already
    right and reweighting it is wasted capacity. No listwise objective is available in this
    environment, so this is the nearest thing that can be expressed as sample weights.
    """
    m = _module()
    ranks = [0, 1, 2, 3, 4]
    y = [0, 1, 0, 1, 0]
    w = m.decision_weights(ranks, y, k=2, boost=4.0)
    assert w[1] == 1.0, "a positive already inside the budget needs no boost"
    assert w[3] == 4.0, "a positive below the budget is exactly what has to move"
    assert w[0] == 4.0, "a negative above the budget is exactly what has to move"
    assert w[2] == 1.0 and w[4] == 1.0, "a negative already below the budget is settled"


def test_decision_weights_are_not_all_equal_on_real_shaped_input():
    """Vacuity guard: a weighting that returns a constant is a no-op that would still show up
    as a declared grid arm and be indistinguishable from the plain run."""
    m = _module()
    ranks = list(range(50))
    y = [1 if i in (0, 40, 45) else 0 for i in range(50)]
    w = m.decision_weights(ranks, y, k=33, boost=3.0)
    assert len(set(w)) > 1
    assert w[40] == 3.0 and w[45] == 3.0 and w[0] == 1.0


def test_the_top_region_is_the_deployed_top_and_keeps_every_positive():
    """Training only near the decision boundary cuts the imbalance, but silently dropping a
    positive that sits deep in the list would remove the very rows the model has to learn to
    pull up. The region must be the deployed top PLUS every positive."""
    m = _module()
    ranks = list(range(100))
    y = [1 if i in (5, 90) else 0 for i in range(100)]
    idx = m.top_region(ranks, y, m_top=60)
    assert len(idx) == 61, f"expected the top 60 plus the deep positive, got {len(idx)}"
    assert 90 in idx and 5 in idx
    assert max(i for i in idx if y[i] == 0) < 60


# --- re-ranking the head only ----------------------------------------------------------------

def test_reranking_the_head_leaves_the_tail_in_deployed_order():
    """Training on the deployed top and then scoring all hundred candidates inverted the rank
    feature: every training row deeper than the cut was a positive, by construction, so the
    model learned that depth predicts a hit. Measured recall at 33 fell .6550 -> .1786.

    Matching the two distributions is the fix: re-rank the head, leave the tail where the
    deployed order put it. The result must still be a permutation of the same key multiset, or
    it is not comparable with the order it replaces.
    """
    m = _module()
    rows = [{"smiles": str(i), "generator": 1.0 - i / 100, "filter": 0.5, "combined": 0.4,
             "key": f"K{i}", "template_scores": [0.5]} for i in range(10)]
    dep = m.deployed_order(rows)
    # a learned score that reverses the head only
    head = 4
    pos = {i: float(i) for i in range(len(rows))}
    got = m.order_head_by_score(rows, pos, head)
    assert sorted(got) == sorted(dep), "the head re-rank changed the key multiset"
    assert got[head:] == dep[head:], "the tail moved, so the head cut is not being honoured"
    assert got[:head] != dep[:head], "the head did not move, so this arm is a no-op"


def test_a_head_larger_than_the_pool_is_the_whole_pool():
    m = _module()
    rows = [{"smiles": str(i), "generator": 1.0 - i / 10, "filter": 0.5, "combined": 0.4,
             "key": f"K{i}", "template_scores": [0.5]} for i in range(3)]
    got = m.order_head_by_score(rows, {0: 0.1, 1: 0.9, 2: 0.5}, 99)
    assert sorted(got) == sorted(m.deployed_order(rows))
    assert got == ["K1", "K2", "K0"]


# --- the feature-block ablation --------------------------------------------------------------

def test_column_subset_resolves_to_real_positions_and_refuses_a_name_it_lacks():
    """The ablation that says WHICH block of features bought the gain has to be in the
    artifact, not in a conversation. A subset silently resolving to the wrong columns, or to
    all of them, would report an ablation that never happened.
    """
    m = _module()
    cols = ("a", "b", "c", "d")
    assert m.col_index(cols, ("a", "c")) == [0, 2]
    assert m.col_index(cols, cols) == [0, 1, 2, 3]
    with pytest.raises(SystemExit):
        m.col_index(cols, ("a", "nosuchfeature"))


def test_the_declared_blocks_partition_the_feature_list():
    """If a block were dropped from the union the ablation would be measuring something other
    than the feature set the selected model uses."""
    m = _module()
    union = tuple(m.FEATURES) + tuple(m.RANK_FEATURES) + tuple(m.DELTA_FEATURES)
    assert len(union) == len(set(union)), "a feature name appears in two blocks"
