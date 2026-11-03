"""A debt entry that stamps a digest must stamp the file's current one, or it is dating a ghost.

Run: python -m pytest revision/tests/test_a_declared_debt_cannot_describe_a_state_that_is_gone.py -q

DECLARED_DEBT in grail_metabolism/tests/test_paper_gates.py records, for each gate that is red on
purpose, what it measures and how far off it is. Several of those figures are stamped with the
sha256 of the file they were read from -- a mechanism the entry itself explains was introduced
because two readers of one file, minutes apart, reported 79 and 82, and only a file identity settles
which state was read.

The stamp makes a reading placeable. It does not make it current, and the difference bit.

The prose-rate entry carried "paper2/si.tex 259 of 1097 (23.61%) against 24 at digest 83ac498e".
That digest is si.tex three commits back. The very next commit took the same file to 30 carriers and
the working tree stood at 31 against a ceiling of 24 -- over by seven, where the entry reported an
excess of 235. The number was not merely old. It described the state BEFORE the work that fixed it,
and it overstated the live gap by a factor of thirty-three in the direction that makes the debt look
unclosable. In the same sentence the body.tex half was current, so the entry was not a deliberate
historical record; half of it tracked the live file and half of it had rotted.

An entry like that is the exact failure this project objects to in other people's papers: the work
was done and the passage explaining how far there was to go stayed. It is also self-refuting, since
the entry's own text says "A number a reader cannot re-derive is a number that stays wrong" and this
one re-derives in under a second.

So: every digest a debt entry stamps must be the current digest of the file it names. The entry may
still be red, and may still be long, and may still argue -- but it may not argue from a state that
is gone.
"""
from __future__ import annotations

import hashlib
import re
import sys

import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATES_FILE = ROOT / "grail_metabolism" / "tests" / "test_paper_gates.py"
sys.path.insert(0, str(ROOT / "scripts"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# "paper2/si.tex 259 of 1097 (23.61%) against 24 at digest 83ac498e"
STAMPED = re.compile(r"(?P<file>paper2/[\w./-]+\.\w+)[^\"]{0,120}?at digest (?P<digest>[0-9a-f]{8})")


def _debt() -> dict:
    import importlib.util
    spec = importlib.util.spec_from_file_location("_paper_gates", GATES_FILE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, "DECLARED_DEBT", {})



# A claim SHAPED like a stamp, read loosely enough to survive the drift the strict patterns above
# would not: a different joining word, a longer gap, sha256 written out instead of "digest".
LOOSE_STAMP = re.compile(r"paper2/[\w./-]+\.\w+.{0,200}?\b(?:digest|sha-?256)\b", re.S | re.I)
LOOSE_COUNT = re.compile(r"paper2/[\w./-]+\.\w+.{0,200}?\b\d+\s+of\s+\d+\b", re.S | re.I)


def _nothing_to_place(debt, checked, loose):
    """Whether no stamp parsed out because none is there, or because the pattern drifted.

    An empty declared-debt list is a legitimate state: the prose-rate entry left this file when
    its gate went green. With nothing stamped there is nothing to place, and refusing would make
    paying a debt look like breaking a check.

    The other case is a claim that is SHAPED like a stamp and that the strict pattern missed, and
    it still refuses, because that is the pattern going stale while the check reports success. The
    two are told apart by a looser read of the same shape, not by whether the entry mentions a
    manuscript file at all: the surviving entry names paper2/body.tex in passing, to say a false
    premise had been copied into it, and a mention is not a measurement. Keying on the mention
    made this guard refuse a legitimately empty state, which is the failure it was added to avoid.
    """
    if checked:
        return False
    drifted = [g for g, t in debt.items() if loose.search(t if isinstance(t, str) else str(t))]
    assert not drifted, (
        "a declared debt carries something shaped like a stamp and the strict pattern did not "
        "parse it, so this check verified nothing: " + ", ".join(drifted))
    return True

def test_every_digest_a_debt_entry_stamps_is_the_file_s_current_one():
    """The check that would have caught three commits of rot in under a second.

    Read from the entries rather than from a list here, so a debt entry added later is covered
    without anyone remembering to add it.
    """
    debt = _debt()
    assert debt, "DECLARED_DEBT is empty or could not be read"
    stale, checked = [], 0
    for gate, text in debt.items():
        for m in STAMPED.finditer(text if isinstance(text, str) else str(text)):
            path = ROOT / m.group("file")
            if not path.exists():
                stale.append(f"{gate}: names {m.group('file')}, which does not exist")
                continue
            now = hashlib.sha256(path.read_bytes()).hexdigest()[:8]
            checked += 1
            if now != m.group("digest"):
                stale.append(
                    f"{gate}: stamps {m.group('file')} at {m.group('digest')} and the file is now "
                    f"{now}; the figure beside that stamp describes a state that is gone")
    if _nothing_to_place(debt, checked, LOOSE_STAMP):
        pytest.skip("no declared debt stamps a manuscript file")
    assert not stale, (
        "a declared debt argues from a file state that no longer exists:\n  "
        + "\n  ".join(stale)
        + "\n\nRe-run the gate, put its live figures in the entry, and re-stamp. A debt may stay "
          "red; it may not stay red on yesterday's numbers.")


def test_a_debt_entry_does_not_promise_work_in_a_window_that_has_closed():
    """A plan is a claim about the future and expires like any other.

    The prose-rate entry promised its Supporting-Information half "for W4" after the commit titled
    "W4 closes, and its entry leaves the declared-debt list" had landed. A window named in a debt
    entry has to be one that is still open, or the entry is describing work as pending that its own
    history says is over.
    """
    debt = _debt()
    log = ROOT / ".git"
    if not log.exists():
        return  # nothing to check against outside a checkout
    import subprocess
    closed = set()
    r = subprocess.run(["git", "log", "--format=%s", "-200"], cwd=ROOT,
                       capture_output=True, text=True, timeout=30)
    for line in r.stdout.splitlines():
        m = re.search(r"\b(W\d+)\b.{0,40}\bcloses\b", line)
        if m:
            closed.add(m.group(1))
    offenders = []
    for gate, text in debt.items():
        for w in re.findall(r"\bW\d+\b", text if isinstance(text, str) else str(text)):
            if w in closed:
                offenders.append(f"{gate}: still names {w}, which the history records as closed")
    assert not offenders, (
        "a declared debt schedules work into a window that has already closed:\n  "
        + "\n  ".join(offenders))


# "paper2/body.tex 7 of 349 sentences (2.01%) against a ceiling of 7 at digest 6cf67c01"
COUNTED = re.compile(
    r"(?P<file>paper2/[\w./-]+\.\w+)\s+(?P<n>\d+)\s+of\s+(?P<tot>\d+)[^,]{0,70}?"
    r"against\s+(?:a\s+ceiling\s+of\s+)?(?P<cap>\d+)\s+at\s+digest\s+(?P<digest>[0-9a-f]{8})")


def test_the_figures_beside_a_stamp_are_the_live_ones_and_not_only_the_digest():
    """The half of this guarantee that was missing, and what it cost.

    The test above compares the digest a debt entry stamps against the file's current digest, and
    nothing compared the COUNTS printed beside it. So a restamp -- the ordinary move after any edit
    to the manuscript -- carried the old figures forward onto a new digest, four times in one
    session, while the body's carrier count went from 7 to 9 against a ceiling of 7. Every restamp
    passed. The entry said the criterion was closed and it was open by two.

    Presence of a digest without its figures is the same defect as a pattern read and never
    compared: the mechanism that makes the reading placeable also made it look checked.
    """
    import check_prose_rate as cpr  # noqa: E402
    debt = _debt()
    wrong, checked = [], 0
    for gate, text in debt.items():
        for m in COUNTED.finditer(text if isinstance(text, str) else str(text)):
            rel = m.group("file")
            if not (ROOT / rel).exists():
                continue
            n_sents, n_car, words = cpr.carriers(rel)
            cap, _ = cpr.carrier_ceiling(words)
            checked += 1
            said = (int(m.group("n")), int(m.group("tot")), int(m.group("cap")))
            live = (n_car, n_sents, cap)
            if said != live:
                wrong.append(
                    f"{gate}: says {rel} is at {said[0]} of {said[1]} against a ceiling of "
                    f"{said[2]} and it is at {live[0]} of {live[1]} against {live[2]}")
    if _nothing_to_place(debt, checked, LOOSE_COUNT):
        pytest.skip("no declared debt carries a counted figure")
    assert not wrong, (
        "a declared debt prints figures its own gate no longer reports:\n  "
        + "\n  ".join(wrong)
        + "\n\nRe-run scripts/check_prose_rate.py, put its live counts in the entry, and re-stamp. "
          "A stamp makes a reading placeable; it does not make it current.")


# A stamp as it is written, and four ways of writing the same claim that the strict patterns above
# do not parse. The skip has to survive the first and refuse all four.
GOOD = "paper2/body.tex 4 of 310 sentences (1.29%) against a ceiling of 6 at digest 6cf67c01"
DRIFTED = (
    "paper2/body.tex 4 of 310 sentences (1.29%) against a ceiling of 6, digest 6cf67c01",
    "paper2/body.tex 4 of 310 sentences (1.29%) against a ceiling of 6 at sha256 6cf67c01",
    "paper2/si.tex, measured on the tree as it stands today and not on the one the last pass left "
    "behind, 28 of 1097 sentences against a ceiling of 24, digest 83ac498e",
    "paper2/body.tex is at 4 of 310 and the ceiling is 6",
)
MENTION = (
    "the same false premise had been copied into paper2/body.tex, which told a reader the figure "
    "stood outside the provenance apparatus",
    "CLOSES when paper2/si.tex carries the sensitivity analysis in full.",
)


def test_an_empty_debt_skips_and_a_stamp_the_pattern_missed_does_not():
    """The guard's own control, because a guard that cannot fail is the defect it guards against.

    _nothing_to_place turns a parse of nothing into a skip. That is the shape of a check that
    passes because it ran on nothing, so the predicate deciding it needs its own known cases:
    a bare prose mention of a manuscript file skips, a stamp-shaped claim the strict pattern
    missed refuses, and anything actually checked is neither.
    """
    for text in MENTION:
        assert _nothing_to_place({"g": text}, 0, LOOSE_STAMP), (
            "a debt that only mentions a manuscript file has nothing to place and must skip: " + text)
        assert _nothing_to_place({"g": text}, 0, LOOSE_COUNT), text
    for text in DRIFTED:
        for loose in (LOOSE_STAMP, LOOSE_COUNT):
            if not loose.search(text):
                continue
            with pytest.raises(AssertionError):
                _nothing_to_place({"g": text}, 0, loose)
    assert any(LOOSE_STAMP.search(t) for t in DRIFTED), "no drifted form carries a digest shape"
    assert any(LOOSE_COUNT.search(t) for t in DRIFTED), "no drifted form carries a counted shape"
    assert STAMPED.search(GOOD) and COUNTED.search(GOOD), (
        "the strict patterns no longer parse a stamp as it is written, so the loose ones are "
        "standing in for a reader that has itself gone stale")
    assert not _nothing_to_place({"g": GOOD}, 1, LOOSE_STAMP), (
        "something was checked, so there is nothing to decide")
