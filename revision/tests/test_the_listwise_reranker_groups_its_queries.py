"""What a listwise objective must get right, on top of everything the pointwise arms needed.

A pointwise model reads one row at a time, so a mistake in how the rows are laid out shows up
as a crash. A listwise objective reads a BLOCK of rows as one query and compares them to each
other, so the layout is part of the model. Three ways that goes wrong quietly:

1. The groups. lightgbm is handed row counts, not substrate names: the first g0 rows are query
   one, the next g1 are query two. If those counts drift out of step with the stacked blocks --
   by one empty substrate, or by a block whose labels and rows disagree -- the objective compares
   a candidate of one substrate against a candidate of another, trains on nonsense, and still
   returns a model that scores every row and produces a full recall table. Nothing fails.

2. The parameter names. lightgbm accepts an unrecognised key with a warning and carries on with
   its default, so a misspelt lambdarank_truncation_level leaves the run optimising the first
   thirty slots while the file, the artifact and the manuscript all say thirty-three.

3. The weights. The metric reported is MICRO recall, which weighs a substrate by its reference
   count; NDCG is normalised per query, which does not. The arm that closes that gap gives every
   row of a substrate the same weight. If lightgbm ignored row weights under a ranking objective
   that arm would be identical to the unweighted one and would still report a separate number.

The tests that need an actual fit skip when lightgbm is absent; the ones that pin the layout and
the parameter names do not, and hold on any checkout.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "scripts" / "typed_edit" / "rerank_learned.py"


def _module():
    for p in (ROOT / "scripts", ROOT / "scripts" / "typed_edit"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location("rerank_listwise_under_test", SRC)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _block(n, rows_seed, label_at=()):
    """One substrate's training block, shaped like what training_rows returns."""
    rng = np.random.default_rng(rows_seed)
    X = rng.normal(size=(n, 3))
    y = np.zeros(n, dtype=int)
    for i in label_at:
        y[i] = 1
    return X, y, np.ones(n, dtype=float)


# --- the groups ------------------------------------------------------------------------------

def test_the_group_sizes_recover_the_blocks_they_index():
    """Not just that they sum: that slicing the stacked matrix by them gives each block back.

    A group vector can sum to the right total and still be wrong -- two substrates of 7 and 3
    recorded as 3 and 7 sums to ten and pairs the wrong candidates.
    """
    m = _module()
    parts = [_block(7, 1, [0, 3]), _block(3, 2, [2]), _block(5, 3)]
    X, y, w, groups = m.listwise_blocks(parts)
    assert groups == [7, 3, 5]
    assert X.shape[0] == len(y) == len(w) == sum(groups) == 15
    at = 0
    for (bx, by, bw), g in zip(parts, groups):
        assert np.array_equal(X[at:at + g], bx)
        assert np.array_equal(y[at:at + g], by)
        assert np.array_equal(w[at:at + g], bw)
        at += g


def test_an_empty_block_is_refused_rather_than_stacked():
    """A zero-length group shifts every query after it by nothing visible.

    The narrowed arms can produce a substrate with no training rows, and a group of zero is
    accepted by lightgbm, so this has to be caught where it is created.
    """
    m = _module()
    with pytest.raises(SystemExit):
        m.listwise_blocks([_block(4, 1), _block(0, 2), _block(4, 3)])


def test_a_block_whose_rows_and_labels_disagree_is_refused():
    """The stack would succeed and the group sizes would then index the wrong rows."""
    m = _module()
    X, y, w = _block(5, 1)
    with pytest.raises(SystemExit):
        m.listwise_blocks([(X, y[:3], w)])
    with pytest.raises(SystemExit):
        m.listwise_blocks([(X, y, w[:2])])


def test_no_blocks_at_all_is_refused():
    """An empty fold would train on nothing and still score every held-out substrate."""
    m = _module()
    with pytest.raises(SystemExit):
        m.listwise_blocks([])


# --- the weights -----------------------------------------------------------------------------

def test_one_weight_per_substrate_expands_to_uniform_rows():
    """Uniform inside a substrate is what makes a row weight act as a query weight."""
    m = _module()
    rows = m.query_weight_rows([3, 1, 2], [2.0, 5.0, 0.5])
    assert rows == [2.0, 2.0, 2.0, 5.0, 0.5, 0.5]


def test_a_weight_vector_that_does_not_match_the_groups_is_refused():
    """Silently recycling or truncating would weight the wrong substrates."""
    m = _module()
    with pytest.raises(SystemExit):
        m.query_weight_rows([3, 1, 2], [2.0, 5.0])
    with pytest.raises(SystemExit):
        m.query_weight_rows([3, 1, 2], [2.0, 5.0, 0.5, 1.0])


# --- the parameter names ---------------------------------------------------------------------

def test_the_declared_truncation_is_the_length_the_work_is_decided_at():
    """The one hyper-parameter that has to agree with the manuscript's budget."""
    m = _module()
    assert m.LISTWISE_PARAMS["lambdarank_truncation_level"] == m.DECIDE_AT == 33


def test_an_unrecognised_listwise_parameter_is_refused_not_passed_through():
    """lightgbm warns and keeps its default, so a typo here is invisible in the output."""
    m = _module()
    p = m.listwise_params(lambdarank_truncation_level=100)
    assert p["lambdarank_truncation_level"] == 100
    assert m.LISTWISE_PARAMS["lambdarank_truncation_level"] == 33, "the base must not be mutated"
    with pytest.raises(SystemExit):
        m.listwise_params(lambdarank_truncation=100)


def test_the_labels_are_declared_binary():
    """lambdarank reads the label as an index into label_gain; a 0/1 label needs a 0/1 gain."""
    m = _module()
    assert m.LISTWISE_PARAMS["label_gain"] == [0, 1]


# --- what the groups and the weights actually do ---------------------------------------------

def _synthetic(n_groups, n_rows, n_pos, seed):
    """Groups in which one feature decides the answer, so a correct fit is recognisable."""
    rng = np.random.default_rng(seed)
    Xs, ys = [], []
    for _ in range(n_groups):
        sig = rng.normal(size=n_rows)
        X = np.column_stack([sig, rng.normal(size=(n_rows, 2))])
        y = np.zeros(n_rows, dtype=int)
        y[np.argsort(-sig)[:n_pos]] = 1
        Xs.append(X)
        ys.append(y)
    return Xs, ys


def _recall_at(Xs, ys, score_of, k):
    hit = tot = 0
    for X, y in zip(Xs, ys):
        s = score_of(X)
        hit += int(y[np.argsort(-s)[:k]].sum())
        tot += int(y.sum())
    return hit / tot


def test_groups_that_merge_every_substrate_into_one_query_destroy_the_ranking():
    """The failure a summing group vector cannot catch, made to show itself.

    One group of everything is the degenerate misalignment: it sums correctly, lightgbm accepts
    it, and the objective then compares candidates across substrates. Measured against the same
    fit with the real groups, on held-out groups, at a fixed budget.
    """
    lgb = pytest.importorskip("lightgbm")
    m = _module()
    Xs, ys = _synthetic(50, 30, 3, seed=7)
    tr, te = slice(0, 40), slice(40, 50)
    Xtr, ytr = np.vstack(Xs[tr]), np.concatenate(ys[tr])

    def fit(groups):
        ds = lgb.Dataset(Xtr, label=ytr, group=groups)
        return lgb.train(m.listwise_params(), ds, num_boost_round=80)

    right = fit([30] * 40)
    merged = fit([30 * 40])
    k = 3
    r_right = _recall_at(Xs[te], ys[te], lambda X: right.predict(X), k)
    r_merged = _recall_at(Xs[te], ys[te], lambda X: merged.predict(X), k)
    r_blind = _recall_at(Xs[te], ys[te],
                         lambda X: np.random.default_rng(0).normal(size=X.shape[0]), k)
    assert r_right > r_blind * 2, f"the fit learnt nothing at all: {r_right:.3f}"
    assert r_right > r_merged, f"grouping made no difference: {r_right:.3f} vs {r_merged:.3f}"


def test_row_weights_change_a_ranking_fit_so_the_weighted_arm_is_a_real_arm():
    """If a ranking objective ignored row weights, the weighted arm would be a duplicate.

    Checked by scoring the SAME rows under two fits that differ only in the weights, which is
    the only thing that distinguishes those two arms in the grid.
    """
    lgb = pytest.importorskip("lightgbm")
    m = _module()
    Xs, ys = _synthetic(40, 25, 2, seed=11)
    Xtr, ytr = np.vstack(Xs), np.concatenate(ys)
    groups = [25] * 40

    def fit(w):
        ds = lgb.Dataset(Xtr, label=ytr, group=groups, weight=np.asarray(w, dtype=float))
        return lgb.train(m.listwise_params(), ds, num_boost_round=60)

    flat = fit(m.query_weight_rows(groups, [1.0] * 40))
    tilted = fit(m.query_weight_rows(groups, [1.0 + 9.0 * (i % 2) for i in range(40)]))
    a, b = flat.predict(Xtr[:200]), tilted.predict(Xtr[:200])
    assert not np.allclose(a, b), "row weights had no effect under the ranking objective"


# --- the counts behind the ratio -------------------------------------------------------------

def test_the_hit_count_is_the_numerator_of_the_recall_it_reports():
    """A ratio of two small integers is not a continuous quantity.

    Arms of this grid tie exactly and differ by a single metabolite, and reporting those gaps as
    decimals invites reading one hit as a result. The integers have to be available and have to
    be the ones the ratio is made of, not a reconstruction by multiplication.
    """
    m = _module()
    order = {"S": ["a", "b", "c"], "T": ["x", "y"]}
    refs = {"S": {"a", "c"}, "T": {"y"}}
    parent = {"S": "p", "T": "p"}
    for k in (1, 2, 3, 5):
        hit, tot = m.hits_at(order, refs, k, parent)
        assert isinstance(hit, int) and isinstance(tot, int)
        assert (hit / tot) == m.recall_at(order, refs, k, parent)
    # Budget by budget: at one slot only "a" is reached; at two the second substrate's single
    # answer arrives as well; at three the first substrate's "c" completes the set.
    assert m.hits_at(order, refs, 1, parent) == (1, 3)
    assert m.hits_at(order, refs, 2, parent) == (2, 3)
    assert m.hits_at(order, refs, 3, parent) == (3, 3)


def test_the_denominator_does_not_move_with_the_order_or_the_budget():
    """The total is what every arm is divided by; if it moved, the arms would not be comparable."""
    m = _module()
    refs = {"S": {"a", "c"}, "T": {"y"}}
    parent = {"S": "p", "T": "p"}
    good = {"S": ["a", "c", "b"], "T": ["y", "x"]}
    bad = {"S": ["b", "a", "c"], "T": ["x", "y"]}
    tots = {m.hits_at(o, refs, k, parent)[1] for o in (good, bad) for k in (1, 2, 3, 50)}
    assert tots == {3}
    assert m.hits_at(good, refs, 1, parent)[0] > m.hits_at(bad, refs, 1, parent)[0]


def test_a_substrate_with_no_reference_enters_neither_side():
    """It carries no answer, so counting it in the denominator would dilute every arm equally
    and silently change what the reported ratio is over."""
    m = _module()
    order = {"S": ["a"], "U": ["q", "r"]}
    refs = {"S": {"a"}}
    assert m.hits_at(order, refs, 5, {"S": "p", "U": "p"}) == (1, 1)
