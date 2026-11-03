"""The preregistration's MetaTox claim must be exactly what the artifact produces.

The hand-written version of this sentence conflated two arms within an hour of being written.
It is now derived, and this holds the file to the derivation.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def test_the_prereg_contains_the_generated_claim_verbatim():
    from sweep_claim import TABLE, claim
    if not TABLE.exists():
        pytest.skip("the deployment table is not in this checkout")
    text = (ROOT / "paper2/preregistration.md").read_text()
    assert claim() in text, (
        "section 0.2b has drifted from results/deployment_table.json; regenerate it with "
        "scripts/sweep_claim.py rather than editing the prose")


def test_the_claim_changes_when_the_artifact_does():
    """A check that cannot fail is not a check."""
    import json
    import tempfile

    from sweep_claim import TABLE, claim
    if not TABLE.exists():
        pytest.skip("the deployment table is not in this checkout")
    d = json.loads(TABLE.read_text())
    d["contrasts"]["15"]["whole bank - metatox"]["excludes_zero"] = True
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(d, fh)
        path = Path(fh.name)
    try:
        assert claim(path) != claim(), "the sentence ignored a change in the artifact"
    finally:
        path.unlink()


def test_the_writer_refuses_when_the_preregistration_s_anchors_are_gone(tmp_path, monkeypatch):
    """The block has a place in the prose, and where that place is cannot be guessed.

    The writer finds the block between two sentences. If the prose around it is rewritten and
    one of those sentences goes, writing anyway would drop the generated claim somewhere
    arbitrary in a preregistration. It has to stop instead.
    """
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "scripts"))
    import sweep_claim as S

    prereg = tmp_path / "preregistration.md"
    claim_tex = tmp_path / "claim.tex"
    monkeypatch.setattr(S, "PREREG", prereg)
    monkeypatch.setattr(S, "CLAIM_TEX", claim_tex)

    # Both anchors present: the writer places the block and is idempotent.
    prereg.write_text(f"intro\n\n{S.OPENS}\n\n> stale\n\n{S.CLOSES} the artifact.\n")
    claim_tex.write_text("stale\n")
    assert S.write("> one\n> two"), "the writer reported no change on a stale pair"
    assert "> one\n> two" in prereg.read_text()
    assert claim_tex.read_text() == "one\ntwo\n"
    assert S.write("> one\n> two") == [], "the writer is not idempotent"

    # One anchor gone: refuse rather than guess.
    for dropped in (S.OPENS, S.CLOSES):
        prereg.write_text(
            f"intro\n\n{S.OPENS}\n\n> one\n> two\n\n{S.CLOSES} the artifact.\n".replace(
                dropped, "a sentence that replaced it"))
        with pytest.raises(SystemExit):
            S.write("> three\n> four")
