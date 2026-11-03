"""A path override must not discard the envelope key the comparator is declared with.

deployment_table.py reads a comparator as `blob[key] if key else blob`. The --comparator
override replaced (path, key) with (path, None), so pointing an enveloped arm at a different
file made every substrate look absent: the loop read the envelope dict itself, found no
substrate under "provenance" or "predictions", and the arm was scored zero for absence on all
of them. It exits zero and writes a table, so the defect is a number and not a crash.

This is the same failure the T_main loader was given a test for -- "a file whose predictions
sit under an envelope key must be read through it, or every substrate looks missing" -- one
producer over. Two of the arms the full-population table needs are declared with an envelope,
metatox and gloryx, and both need a path override to reach their 1,170-substrate files.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "scripts" / "typed_edit" / "deployment_table.py"


def _module():
    """Import the producer without running main()."""
    if str(SRC.parent) not in sys.path:
        sys.path.insert(0, str(SRC.parent))
    spec = importlib.util.spec_from_file_location("deployment_table_under_test", SRC)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_the_declared_envelope_survives_a_path_override(tmp_path):
    m = _module()
    f = tmp_path / "metatox_elsewhere.json"
    f.write_text(json.dumps({"provenance": {"script": "x"}, "predictions": {"CCO": ["CC=O"]}}))
    got = m.apply_overrides(dict(m.COMPARATORS), [f"metatox={f}"])
    assert got["metatox"] == (str(f), "predictions"), (
        "the override dropped the envelope key, so the reader would take the whole blob and "
        f"find no substrate in it: {got['metatox']!r}")


def test_an_override_whose_file_lacks_the_declared_envelope_is_refused(tmp_path):
    """Non-vacuous by construction: silently reading zero is the defect, so the only two
    acceptable outcomes are the envelope honoured or a refusal naming what the file holds."""
    m = _module()
    f = tmp_path / "bare.json"
    f.write_text(json.dumps({"CCO": ["CC=O"]}))
    with pytest.raises(SystemExit) as e:
        m.apply_overrides(dict(m.COMPARATORS), [f"metatox={f}"])
    msg = str(e.value)
    assert "predictions" in msg and "CCO" in msg, (
        f"the refusal has to name the key it wanted and the keys the file has, got {msg!r}")


def test_an_arm_declared_without_an_envelope_stays_without_one(tmp_path):
    m = _module()
    f = tmp_path / "sygma_elsewhere.json"
    f.write_text(json.dumps({"CCO": ["CC=O"]}))
    got = m.apply_overrides(dict(m.COMPARATORS), [f"sygma={f}"])
    assert got["sygma"] == (str(f), None), got["sygma"]


def test_an_unknown_arm_is_still_refused(tmp_path):
    m = _module()
    with pytest.raises(SystemExit):
        m.apply_overrides(dict(m.COMPARATORS), ["nosuchsystem=/tmp/x.json"])


def test_a_spec_without_an_equals_sign_is_still_refused():
    m = _module()
    with pytest.raises(SystemExit):
        m.apply_overrides(dict(m.COMPARATORS), ["metatox"])
