"""The comparison set may be measured on, and must not be chosen on.

The grid is thirteen arms and they land within a few metabolites of each other, so taking the
maximum is a choice worth several thousandths of recall. Taking it on the population the result
is reported for converts a measurement into a selection, and the gap being chased is itself
only a few thousandths wide.

The producer computed every arm on whatever population it was run on and then took the maximum
there. On the comparison set it would have reported the best of thirteen and recorded, in the
artifact, "selected on recall at 33 on the comparison draw" -- a violation stated plainly in
the output and easy to read past, because the number beside it looks like the number that was
wanted. These pin the arm to what the validation run chose, and make the producer refuse rather
than fall back when that choice cannot be recovered.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "scripts" / "typed_edit" / "rerank_learned.py"

AVAILABLE = ("pointwise", "listwise lambdarank truncated at 33", "pointwise, classes balanced")


def _module():
    for p in (ROOT / "scripts", ROOT / "scripts" / "typed_edit"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location("rerank_pinned_under_test", SRC)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _validation_artifact(tmp_path: Path, selected: str) -> Path:
    p = tmp_path / "rerank_learned.json"
    p.write_text(json.dumps({"model": {"selected": selected}}))
    return p


def test_the_validation_draw_is_where_the_choice_is_made():
    """Nothing is pinned there: that run is the one allowed to take the maximum."""
    m = _module()
    assert m.arm_fixed_on_validation("validation", AVAILABLE) is None


def test_any_other_population_is_pinned_to_what_validation_chose(tmp_path):
    """Not the best arm of the run being reported, the arm the earlier run settled on."""
    m = _module()
    art = _validation_artifact(tmp_path, "pointwise, classes balanced")
    assert m.arm_fixed_on_validation("comparison", AVAILABLE, artifact=art) \
        == "pointwise, classes balanced"


def test_a_missing_validation_artifact_is_refused_not_worked_around(tmp_path):
    """Falling back to the maximum of the run in hand is exactly the thing being prevented."""
    m = _module()
    with pytest.raises(SystemExit):
        m.arm_fixed_on_validation("comparison", AVAILABLE,
                                  artifact=tmp_path / "nothing_here.json")


def test_an_arm_the_grid_no_longer_carries_is_refused(tmp_path):
    """A pin naming an arm this grid did not compute is a pin to a different experiment.

    The grid grew from eight arms to thirteen once already. A renamed or dropped arm has to stop
    the run, because silently reporting some other arm under the pinned name is indistinguishable
    in the artifact from reporting the pinned one.
    """
    m = _module()
    art = _validation_artifact(tmp_path, "an arm from an older grid")
    with pytest.raises(SystemExit):
        m.arm_fixed_on_validation("comparison", AVAILABLE, artifact=art)


def test_the_real_validation_artifact_pins_an_arm_the_current_grid_still_carries():
    """The pin has to resolve against the grid as it stands, not as it stood.

    Read from the deposited artifact rather than constructed, so the guard fails here if the
    grid is edited and the validation run is not redone.
    """
    m = _module()
    art = ROOT / m.POPULATIONS["validation"]["out"]
    if not art.exists():
        pytest.skip("the validation artifact is not in this checkout")
    selected = json.loads(art.read_text())["model"]["selected"]
    grid = list(json.loads(art.read_text())["model"]["grid"])
    assert selected in grid, "the validation artifact pins an arm its own grid does not list"
    assert m.arm_fixed_on_validation("comparison", grid, artifact=art) == selected
