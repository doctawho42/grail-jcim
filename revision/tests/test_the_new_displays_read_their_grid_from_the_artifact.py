"""The two displays that replace a grid of prose read that grid from the artifact.

Run: python -m pytest revision/tests/test_the_new_displays_read_their_grid_from_the_artifact.py -q

Two paragraphs of the Results enumerated a grid: the controls on the wide-budget leads, one cell
per comparator and per control, and the comparison by transformation class, one cell per class and
per system. Prose cannot hold either -- the first was a seventy-five-word sentence -- so both move
into a figure. What a figure makes easy is the defect this project has now met in eleven files: a
typed list of arms beside an artifact that has its own keys, correct the day it is written and
silently short one comparator later.

So neither display may carry its own roster. Both tests derive the expected content from the
artifact here, independently of the producer, and then PERTURB the artifact -- adding a comparator,
adding a transformation class -- and require the display to follow or to refuse by name. A display
that silently omits the new one fails, because that is exactly how a comparator goes missing.

The drawing-corrected SyGMa arm is checked separately. It is the same comparator under a different
presentation of the substrate, so it belongs on SyGMa's row as a third mark and not in the roster
as an eighth system: a display that lists it alongside the others says this work was compared
against one more method than it was.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# The artifact each display reads, asked of the code that reads it. These were named here by
# file, which is how the whole set broke the day the controls moved from the comparison set to
# the whole evaluated test set: the figures drew one population and the tests checked them
# against another, and every failure said "the value drawn is not the value measured" when both
# were correct for their own population.
def _artifact(stem):
    import sys as _s
    _s.path.insert(0, str(ROOT / "scripts"))
    _s.path.insert(0, str(ROOT / "scripts" / "typed_edit"))
    from _acs_table import HEADLINE, control_artifact

    return ROOT / "results" / control_artifact(stem, HEADLINE)


sys.path.insert(0, str(ROOT / "scripts"))

MATCHED = _artifact("matched_length")
CHEM = _artifact("error_by_chemistry")

pytestmark = pytest.mark.skipif(
    not (MATCHED.exists() and CHEM.exists()),
    reason="matched_length.json or error_by_chemistry.json is not in this checkout")

# The suffix the artifact uses for the same comparator under the corrected drawing. One place.
DRAWING_SUFFIX = " on the standardised drawing"


@pytest.fixture
def pf(tmp_path, monkeypatch):
    """The module, with its output redirected.

    Calling a figure writes paper2/fig_*.eps, and the perturbation tests below call it with a
    comparator the paper does not have. Running this file would then leave a figure on disk that
    draws a probe, and the build's digest covers the ARTIFACTS rather than the files, so nothing
    downstream would notice. Redirecting the output is the whole fix.
    """
    import paper2_figures as mod
    monkeypatch.setattr(mod, "OUT", tmp_path)
    return mod


def _expected_rows(contrasts, style, ours=("whole bank", "trained budget")):
    """Today's answer, computed here rather than read from the producer.

    One row per comparator, in the artifact's own order; the drawing-corrected contrast is not a
    row of its own.
    """
    rows = []
    for key in contrasts:
        arm, _, comp = key.partition(" - ")
        if arm not in ours or comp.endswith(DRAWING_SUFFIX):
            continue
        if comp not in rows:
            rows.append(comp)
    return rows


def test_the_control_figure_has_a_row_for_every_comparator_the_artifact_carries(pf):
    drawn = pf.fig_matched()
    art = json.loads(MATCHED.read_text())["contrasts"]
    assert drawn["comparators"] == _expected_rows(art, pf.SWEEP_STYLE), (
        "the control figure's rows are not the comparators the artifact carries, in its order")


def test_the_control_figure_draws_the_artifact_s_gap_and_interval_to_the_digit(pf):
    drawn = pf.fig_matched()
    art = json.loads(MATCHED.read_text())["contrasts"]
    for key, cell in drawn["cells"].items():
        assert key in art, f"the figure drew a cell the artifact does not carry: {key}"
        assert cell["gap"] == art[key]["gap"], f"{key}: gap drawn is not the gap measured"
        assert cell["ci95"] == art[key]["ci95"], f"{key}: interval drawn is not the one measured"
    for key in art:
        arm, _, comp = key.partition(" - ")
        if arm in ("whole bank", "trained budget"):
            assert key in drawn["cells"], (
                f"the artifact carries {key} and the figure does not draw it")


def test_the_drawing_corrected_arm_sits_on_its_comparator_s_row_and_not_in_the_roster(pf):
    """Checked where that arm exists, which is one population and not the other.

    SyGMa re-run on the drawing the declared standardiser produces was obtained for the
    substrates that were submitted, so the whole evaluated test set has no such column and the
    figure drawn there has no such line. The property is still worth holding: wherever the arm
    is drawn, it belongs on its comparator's row rather than as a system of its own, because a
    roster one entry longer says this work was compared against one more system than it was.
    """
    drawn = pf.fig_matched()
    corrected = [k for k in json.loads(MATCHED.read_text())["contrasts"]
                 if k.endswith(DRAWING_SUFFIX)]
    if not corrected:
        comparison = ROOT / "results" / "matched_length.json"
        assert comparison.exists(), "neither population carries the drawing-corrected contrast"
        assert any(k.endswith(DRAWING_SUFFIX)
                   for k in json.loads(comparison.read_text())["contrasts"]), (
            "the drawing-corrected contrast is in neither population's control, so the "
            "paragraph that reports what the drawing costs has nothing behind it")
        pytest.skip(f"{MATCHED.name} carries no drawing-corrected contrast; it exists for the "
                    f"submitted substrates alone, and the comparison-set control has it")
    for key in corrected:
        _, _, comp = key.partition(" - ")
        base = comp[:-len(DRAWING_SUFFIX)]
        assert base in drawn["comparators"], f"{base} is not a row for {key} to sit on"
        assert comp not in drawn["comparators"], (
            f"{comp} is drawn as a comparator of its own, which says this work was compared "
            f"against one more system than it was")
        assert key in drawn["cells"], f"the corrected contrast {key} is not drawn at all"


def test_a_comparator_added_to_the_artifact_reaches_the_control_figure(pf, tmp_path, monkeypatch):
    """The perturbation. A typed roster passes every test above and fails this one."""
    art = json.loads(MATCHED.read_text())
    donor = next(k for k in art["contrasts"] if k.startswith("whole bank - "))
    for arm in ("whole bank", "trained budget"):
        src = art["contrasts"][f"{arm} - {donor.partition(' - ')[2]}"]
        art["contrasts"][f"{arm} - zzz_probe"] = dict(src)
    probe = tmp_path / MATCHED.name
    probe.write_text(json.dumps(art))
    real = pf.art

    def fake(name):
        return json.loads(probe.read_text()) if name == MATCHED.name else real(name)

    monkeypatch.setattr(pf, "art", fake)
    try:
        drawn = pf.fig_matched()
    except SystemExit as e:
        assert "zzz_probe" in str(e), (
            "the figure refused and did not name the comparator it could not place")
        return
    assert "zzz_probe" in drawn["comparators"], (
        "a comparator added to the artifact never reached the figure, so the roster is typed")


def _expected_classes(classes):
    """Ordered by how many known metabolites the class carries, largest first."""
    return [k for k, _ in sorted(classes.items(), key=lambda kv: (-kv[1]["references"], kv[0]))]


def test_the_chemistry_figure_shows_every_class_the_artifact_carries(pf):
    drawn = pf.fig_chemistry()
    classes = json.loads(CHEM.read_text())["classes"]
    assert drawn["classes"] == _expected_classes(classes), (
        "the chemistry figure's rows are not the artifact's classes ordered by reference count")
    assert len(drawn["classes"]) == len(classes)


def test_the_chemistry_figure_draws_every_system_at_the_reported_budget(pf):
    drawn = pf.fig_chemistry()
    art = json.loads(CHEM.read_text())
    budget = str(drawn["budget"])
    assert int(budget) in art["budgets"], "the figure draws a budget the artifact never measured"
    for cls, per_system in drawn["recall"].items():
        src = art["classes"][cls]["recall"]
        assert set(per_system) == set(src), f"{cls}: the systems drawn are not the systems measured"
        for sysname, v in per_system.items():
            assert v == src[sysname][budget], f"{cls}/{sysname}: value drawn is not value measured"


def test_a_class_added_to_the_artifact_reaches_the_chemistry_figure(pf, tmp_path, monkeypatch):
    """The same perturbation on the other display."""
    art = json.loads(CHEM.read_text())
    donor = next(iter(art["classes"]))
    art["classes"]["zzz probe class"] = json.loads(json.dumps(art["classes"][donor]))
    art["classes"]["zzz probe class"]["references"] = 1
    probe = tmp_path / CHEM.name
    probe.write_text(json.dumps(art))
    real = pf.art

    def fake(name):
        return json.loads(probe.read_text()) if name == CHEM.name else real(name)

    monkeypatch.setattr(pf, "art", fake)
    try:
        drawn = pf.fig_chemistry()
    except SystemExit as e:
        assert "zzz probe class" in str(e), (
            "the figure refused and did not name the class it could not place")
        return
    assert "zzz probe class" in drawn["classes"], (
        "a class added to the artifact never reached the figure, so the class list is typed")
