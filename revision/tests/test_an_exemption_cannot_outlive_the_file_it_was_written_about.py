"""An artifact excused from the provenance guarantee is excused as it stood, not for ever.

Run: python -m pytest revision/tests/test_an_exemption_cannot_outlive_the_file_it_was_written_about.py -q

Three artifacts the manuscript prints numbers from cannot be regenerated here. One is a recorded
run of someone else's web service; one has an input that is a zero-byte placeholder in every
checkout and no producer in this repository writes it; one takes two files the service returned
and that were never deposited. Each is a real reason and each was already written down
somewhere, and the gate that asks whether every artifact's producer can be identified has no way
to hear any of them, so it has been red for as long as they have existed.

A reason on its own is the wrong mechanism, because a reason outlives the file it was written
about. "This cannot be re-run" stays true while the file is replaced by hand, and the exemption
would cover the replacement without anyone deciding that. So the reason is recorded with the
digest the artifact carried when it was written, and an artifact that changes stops being exempt
and fails until someone looks again.

These tests drive that: the exemption holds for the file it names, lapses the moment the file
changes, and refuses an entry for a file that is not there at all.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture
def C():
    import check_number_provenance as m
    return m


def _digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def test_every_excused_artifact_is_there_and_carries_the_digest_recorded_for_it(C):
    assert C.UNREPEATABLE, "nothing is excused, so this file is checking an empty set"
    for rel, (digest, reason) in C.UNREPEATABLE.items():
        p = ROOT / rel
        assert p.exists(), f"{rel} is excused and is not in the checkout"
        assert len(reason.split()) >= 12, f"{rel}: the reason is too short to be one"
        assert _digest(p) == digest, (
            f"{rel} has changed since its exemption was written: the exemption names "
            f"{digest} and the file is {_digest(p)}. The exemption does not carry over to a "
            f"file nobody has looked at; read what changed and record the new digest with a "
            f"reason that is still true of it.")


def test_the_exemption_lapses_when_the_file_changes(C, tmp_path, monkeypatch):
    """The property, driven rather than asserted."""
    rel = "results/a_probe.json"
    f = tmp_path / "results" / "a_probe.json"
    f.parent.mkdir(parents=True)
    f.write_text('{"a": 1}')
    monkeypatch.setattr(C, "ROOT", tmp_path)
    monkeypatch.setattr(C, "UNREPEATABLE",
                        {rel: (_digest(f), "a probe, excused for the length of this test only "
                                           "and for no other reason at all")})
    assert C.excused(rel), "the exemption did not hold for the file it names"
    f.write_text('{"a": 2}')
    assert not C.excused(rel), "the exemption survived the file being replaced"


def test_an_entry_for_a_file_that_is_not_there_is_refused(C, tmp_path, monkeypatch):
    monkeypatch.setattr(C, "ROOT", tmp_path)
    monkeypatch.setattr(C, "UNREPEATABLE",
                        {"results/gone.json": ("0" * 16, "a reason long enough to be a reason, "
                                                         "about a file that is not here")})
    assert not C.excused("results/gone.json")


def test_what_is_excused_is_three_artifacts_and_not_a_category(C):
    """A list that grows without anyone noticing is the failure this mechanism invites."""
    assert len(C.UNREPEATABLE) <= 4, (
        f"{len(C.UNREPEATABLE)} artifacts are excused from the provenance guarantee. Each one "
        f"is a number in the paper whose producer cannot be run, so the list getting longer is "
        f"the release getting weaker, and it should be read rather than extended: "
        + ", ".join(sorted(C.UNREPEATABLE)))
