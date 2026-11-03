"""A rate measured with a model belongs to the build of it, so the build has to be recorded true.

Run: python -m pytest revision/tests/test_the_recorded_environment_is_the_one_that_is_installed.py -q

The image recogniser lives in a second interpreter whose versions are load-bearing in an
unusually literal way: torch below 2 because MolScribe pins it, numpy below 2 because torch 1.13
was built against it, OpenCV below 5 because numpy 1 is what it accepts. A record of those that
has drifted from what is installed would attach a measured rate to an environment nobody ran.

The record is therefore asserted against the live environment rather than trusted, and the
normalisation it uses to find a package is asserted on the case that defeated the first version:
pip spells the distribution MolScribe and this repository spells it molscribe.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _mod():
    spec = importlib.util.spec_from_file_location(
        "_env", ROOT / "scripts" / "typed_edit" / "record_ocsr_environment.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["_env"] = m
    spec.loader.exec_module(m)
    return m


ENV = _mod()
pytestmark = pytest.mark.skipif(
    not (ENV.VENV / "bin" / "pip").exists(),
    reason="the recogniser's environment is not built on this machine")


def test_a_distribution_is_found_however_it_is_spelled():
    assert ENV._key("MolScribe") == ENV._key("molscribe") == "molscribe"
    assert ENV._key("opencv_python") == ENV._key("opencv-python") == "opencv-python"
    assert ENV._key("OpenNMT-py") == "opennmt-py"


def test_every_load_bearing_package_is_present():
    resolved = ENV.freeze()
    index = {ENV._key(k): v for k, v in resolved.items()}
    missing = [p for p in ENV.LOAD_BEARING if ENV._key(p) not in index]
    assert missing == [], (
        f"the environment is missing {missing}, which the recogniser cannot run without")


def test_the_record_is_the_environment_that_is_installed():
    stored = json.loads(ENV.OUT.read_text())
    index = {ENV._key(k): v for k, v in ENV.freeze().items()}
    drifted = {p: (stored["load_bearing"][p], index.get(ENV._key(p)))
               for p in ENV.LOAD_BEARING
               if stored["load_bearing"].get(p) != index.get(ENV._key(p))}
    assert drifted == {}, (
        f"the recorded environment is not the installed one: {drifted}; re-run "
        f"python scripts/typed_edit/record_ocsr_environment.py")


def test_the_pins_that_make_it_run_are_the_ones_recorded():
    """Not that they are any particular number, but that they satisfy the chain that was measured."""
    stored = json.loads(ENV.OUT.read_text())["load_bearing"]
    assert stored["torch"].startswith("1."), "torch 2 is what MolScribe pins away from"
    assert stored["numpy"].startswith("1."), "numpy 2 stops torch 1.13 converting a tensor"
    assert stored["opencv-python"].startswith("4."), "OpenCV 5 requires the numpy torch cannot use"
