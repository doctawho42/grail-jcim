"""A structure drawn as line segments is rebuilt from the segments, and measured where the answer is held.

Run: python -m pytest revision/tests/test_a_drawing_is_rebuilt_from_its_own_vectors.py -q

The external benchmark draws its structures as real vector segments with real text labels, not as
pictures, so the connectivity is in the file and reading it is geometry rather than recognition.
That does not make it right. A reconstructor is an instrument like any other and the question is
how often it is exactly right on this chemistry, drawn by these authors.

The document answers that itself. Every per-drug table draws the parent drug in its first row, in
the same hand as the metabolites, and the parent structures are already held in this directory as
SMILES taken from the benchmark's own input scripts. So the ten parents are an answer key in the
authors' own drawing style, and the calibration below is scored against it.

The unit cases come first and use geometry written here rather than read from the document, so
that a failure says which part is wrong: a ring closes, a double bond is one bond and not two, two
neighbouring ring bonds are not mistaken for one double bond, and a label turns a vertex into the
element it names.
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _mod():
    spec = importlib.util.spec_from_file_location(
        "_vec", ROOT / "scripts" / "typed_edit" / "gao_si_structures.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["_vec"] = m
    spec.loader.exec_module(m)
    return m


VEC = _mod()


def _ring(n: int, r: float = 10.0, doubles=()) -> list:
    """A regular n-gon as segments, with an inner line beside each bond listed in doubles."""
    pts = [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n))
           for i in range(n)]
    segs = []
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        segs.append((a, b))
        if i in doubles:
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            m = math.hypot(mx, my)
            nx, ny = -mx / m, -my / m          # inward
            dx, dy = b[0] - a[0], b[1] - a[1]
            segs.append(((a[0] + 2.4 * nx + 0.18 * dx, a[1] + 2.4 * ny + 0.18 * dy),
                         (b[0] + 2.4 * nx - 0.18 * dx, b[1] + 2.4 * ny - 0.18 * dy)))
    return segs, pts


def test_a_closed_ring_of_single_bonds_is_that_ring():
    segs, _ = _ring(6)
    got, note = VEC.build(segs, [])
    assert got == "C1CCCCC1", f"{got} ({note})"


def test_alternating_inner_lines_make_one_aromatic_ring_and_not_nine_bonds():
    segs, _ = _ring(6, doubles=(0, 2, 4))
    got, note = VEC.build(segs, [])
    assert got == "c1ccccc1", f"{got} ({note})"


def test_two_neighbouring_ring_bonds_are_not_read_as_one_double_bond():
    """The failure a loose parallel test makes: a hexagon has opposite sides parallel too."""
    segs, _ = _ring(6)
    got, _ = VEC.build(segs, [])
    from rdkit import Chem
    assert Chem.MolFromSmiles(got).GetNumBonds() == 6


def test_a_label_turns_a_vertex_into_the_element_it_names():
    """A bond that runs into a label stops at the label's text, and the atom is the label.

    The clearance in the fixture is the measured one. Written first with the bond stopping three
    points short, this passed only because the reach was then a fraction of the bond length --
    which, measured on the document, it is not: over the hundred labels in the parent cells the
    nearest endpoint is never more than 1.01 points from the box. A reach that large swallowed
    neighbouring atoms and gave oxygens eight bonds.
    """
    chain = [((0.0, 0.0), (8.0, 5.0)), ((8.0, 5.0), (13.5, 1.6))]
    oxygen = {"element": "O", "charge": 0, "x": 16.0, "y": 0.0,
              "box": (14.5, -3.0, 18.0, 3.0)}
    got, note = VEC.build(chain, [oxygen])
    assert got == "CCO", f"{got} ({note})"


def test_a_label_is_read_off_the_characters_the_page_carries():
    def ch(t, x):
        return {"text": t, "x0": x, "x1": x + 4.0, "top": 10.0, "bottom": 17.0}
    hn = VEC.read_labels([ch("H", 0), ch("N", 4)])
    assert len(hn) == 1
    assert (hn[0]["element"], hn[0]["charge"], hn[0]["x"], hn[0]["y"]) == ("N", 0, 6.0, 13.5)
    assert VEC.read_labels([ch("C", 0), ch("l", 4)])[0]["element"] == "Cl"
    assert VEC.read_labels([ch("N", 0), ch("+", 4)])[0]["charge"] == 1
    assert VEC.read_labels([ch("O", 0), ch("-", 4)])[0]["charge"] == -1
    far = VEC.read_labels([ch("N", 0), ch("O", 40)])
    assert len(far) == 2, "two labels a long way apart were merged into one"
    # The same pair handed over in the other order. The first grouping walked a sorted list and
    # tested the gap to the previous character without requiring it to be positive, so a pair that
    # arrived right-to-left merged and its box spanned everything between them.
    back = VEC.read_labels([ch("O", 40), ch("N", 0)])
    assert len(back) == 2, "two labels merged because they arrived right to left"
    assert max(l["box"][2] - l["box"][0] for l in back) < 8.0, (
        "a label's box spans the gap between two separate labels")


def test_the_calibration_is_scored_against_the_parents_already_held():
    got = VEC.calibrate()
    assert got["n_parents"] == 10, (
        f"{got['n_parents']} parent drawings were read; the Supporting Information carries ten, "
        f"Sotorasib being scored without a table")
    assert len(got["parents"]) == got["n_parents"]
    assert got["n_exact"] + got["n_wrong"] + got["n_unbuilt"] == got["n_parents"]
    for p in got["parents"]:
        assert p["reference"], f"{p['drug']} was calibrated against no held structure"


def test_the_recorded_calibration_is_what_the_reconstructor_does_now():
    stored = json.loads(VEC.OUT.read_text())
    fresh = VEC.calibrate()
    for field in ("n_parents", "n_exact", "n_wrong", "n_unbuilt"):
        assert stored[field] == fresh[field], (
            f"{VEC.OUT.name} records a different {field}; re-run: "
            f"python scripts/typed_edit/gao_si_structures.py")
