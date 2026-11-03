"""The paper's own gates have to run, or they rot without saying so.

`audit_claim_words.py` had been exiting non-zero for some time before this file existed: the
survey moved from the appendices into the body, the sentences it keys on moved with it, and
nothing ran the script, so a generated table stayed in the manuscript while the check that
produces it was failing. A gate nobody runs is not a gate.

These are slow enough to be worth naming and fast enough to keep in the default suite. They
need the manuscript and the committed artifacts, not the dataset.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

GATES = [
    ("audit_claim_words.py", []),      # every `certified' traces to a declared family
    ("check_prereg.py", ["--self-test"]),
    # the registry itself has to stay valid: a hypothesis that loses its failure condition or
    # its family size stops being registered, and nothing else would say so
    ("check_prereg.py", ["--prereg", "paper2/preregistration.md"]),
    ("polish_audit.py", []),           # no injected instruction, reader address or diary prose
    # every number the registration leans on still traces to the code that wrote it
    # Both of these WRITE a tracked artifact when run with no arguments, so the suite was
    # regenerating results/artifact_provenance.json and results/withheld_template_carriers.json
    # every time it ran -- a test producing the artifacts other tests verify against. It cost an
    # hour of two people cross-checking a census neither had deliberately regenerated. Both
    # verdicts are computed before the write and neither reads its file back, so the output goes
    # to a scratch name under results/, which .gitignore already covers.
    # Consequence worth stating rather than discovering: `make test` no longer refreshes those two
    # artifacts. That is the point -- regenerating them is a producer's job and a decision, not a
    # side effect of running the tests.
    ("audit_artifact_provenance.py",
     ["--out", str(ROOT / "results" / ".gate_scratch_provenance.json")]),
    # a swept row whose numbers move with the clock names which ones, and the SI says so
    ("check_wallclock_fields.py", []),
    # the word around a number makes a claim too: superlatives and separation verdicts
    ("check_quantifiers.py", []),
    # Both documents compile, resolve every reference and overrun no column. This gate was
    # written, was correct, and was not on this list, so a manuscript shipped a cross-reference
    # that printed ?? through a green suite: three referees found it and the checker that would
    # have caught it had never been run. A gate nothing invokes is not a gate.
    ("check_paper2_build.py", []),
    # LICENSE, NOTICE.md and the package configuration describe the bank that ships, not
    # the one the paper measures. Both files went on describing the wrong one for a week.
    ("check_licence_files.py", []),
    # An input digest has to be the digest a READER computes. git normalises line endings on
    # commit and reports nothing, so eight tracked data files carried bytes here that no clone
    # would ever have, and three artifacts verified in this tree and reported a moved input in a
    # fresh one. The guarantee the manuscript quotes has to hold on the reader's side.
    ("check_working_tree_matches_index.py", []),
    # The manuscript's voice packs a claim, its qualification and its evidence into one sentence,
    # which is why it read heavily; splitting them cost nothing and does not stay done, because
    # every new paragraph is written in the same voice and no single edit ever looks wrong.
    ("check_prose_density.py", []),
    # no document may claim the withheld templates are not redistributed while a tracked file
    # carries them
    ("check_no_withheld_templates.py",
     ["--out", str(ROOT / "results" / ".gate_scratch_withheld.json")]),
    # the ignore rules name what the repository deposits, instead of being overridden by a
    # flag 372 times, which is how a released artifact goes missing from a release
    ("sync_tracked_artifacts.py", ["--check"]),
    # The prose counts the register's verdicts. One verdict cell was weakened from a confirmation
    # to a measurement and the two sentences that count confirmations were not, so the manuscript
    # said seven where its own table said six, a page apart, and no gate could see it because a
    # spelled-out word is invisible to the numbers gate.
    ("check_register_tally.py", []),
    ("check_register_tally.py", ["--self-test"]),
    # How often the prose reaches for two constructions, against what eight comparable papers do.
    # A reviewer called the manuscript machine-written; the reply that each hedge is individually
    # defensible answers a different question, because the complaint is about a rate. Measured,
    # "rather than" runs at 5.5 per 1000 words against a corpus range of 0.00-0.57.
    ("check_prose_rate.py", []),
]


# What a gate reads that a fresh clone may not have. A missing input is a skip, not a failure.
NEEDS = {
    "check_paper2_build.py": ("paper2/si.log", "paper2/grail_jcim.log"),
}

# A gate may be red on purpose, and that has to be said here rather than left to whoever reads
# the suite. This one was written to fail: the rate gate exists precisely because the rate is out.
# A red gate nobody has declared is indistinguishable from a broken one, and a suite that is
# permanently red stops being read at all -- which is the same defect as a gate nobody runs, one
# step further along.
#
# The list is not a licence. If a declared gate PASSES, this test fails and demands its removal,
# so a debt cannot be paid and left on the books, and cannot be added to silence a real
# regression: the moment the prose reaches the ceiling, the entry has to go.
#
# check_prose_density.py was here and has been removed, which is what paying a debt looks like.
# Its entry read: paper2/si.tex, 12 per cent of sentences over 45 words against a ceiling of 10,
# longest 96 against 75, and four sections over the section mean ceiling of 32, closing in W4.
# W4 closed it by splitting twenty-two sentences at joints they already carried, deleting nothing:
# the share is now 9 per cent of 1,126 sentences, the longest is 75, no section exceeds the mean
# ceiling, and the file mean fell 27.4 -> 26.3. The registry stayed whole across the pass -- every
# key that changed paired with a new one and kept the marker that registers it.
DECLARED_DEBT = {
    "audit_artifact_provenance.py":
        "THREE pinned artifacts are not current, two of them for reasons outside this repository "
        "and one recorded here rather than repaired. Neither of the two can be made current "
        "without changing a number the paper prints. A THIRD was closed by measurement and has left this entry; what it was is set out below, because a debt that quietly loses a line is indistinguishable from one that was miscounted. The gate was red with no entry here, which is "
        "the one condition this mechanism exists to forbid: a red gate nobody has declared is "
        "indistinguishable from a broken one.\n"
        "results/uspto_type_overlap.json. Its input, grail_metabolism/uspto_templates.csv.gz, is a "
        "zero-byte placeholder in every checkout, was never tracked, and no producer in this "
        "repository writes it, so the artifact cannot be regenerated at all. The reasoning is set "
        "out at length in scripts/audit_artifact_provenance.py and not repeated here.\n"
        "results/gloryx_service_preds.json. The arm is a run of the authors' web service, pinned by "
        "its job identifiers. Re-running the producer would make a NEW run against a service whose "
        "version may have moved, not reproduce the recorded one, so currency here would mean "
        "replacing the data rather than checking it.\n"
        "results/benchmark_report_depth2.json, CLOSED, and how it closed is the part worth keeping. "
        "This entry declared it unclosable on the ground that it records no seed, so a re-run would "
        "draw a different 150-substrate sample and return a different lift. Nobody had opened the "
        "producer. scripts/run_benchmark.py takes --seed with a default of 42 and draws with "
        "random.Random(seed).shuffle(subs) over a pool that sorted() fixes first, so the draw is "
        "determined by (sample, seed) alone; load_test_map(150, 42) returns 150 substrates and 325 "
        "reference pairs against the artifact's recorded true_total of 325, and 231/325 is its "
        "recorded recall_ceiling to sixteen digits. Re-running the producer reproduced all 22 "
        "recorded fields with nothing differing. The file's silence had been read as the run's "
        "irreproducibility, which is a different claim: what was missing was the record, never the "
        "property. The producer now records its own invocation -- stamp, seed, sample, beam, node "
        "budget and input digests -- and the artifact verifies current with its inputs unchanged. "
        "The same false premise had been copied into scripts/audit_artifact_provenance.py, into a "
        "registry reason, and into paper2/body.tex, which told a reader the figure stood outside "
        "the provenance apparatus; all four are corrected. A justification repeated in four files "
        "is one claim with one origin, and the count of places it appears is evidence of copying "
        "and not of checking.\n"
        "THIS ENTRY SAID THE SWEEP COULD NOT DIAGNOSE THESE, AND THAT WAS A DEFECT IN THE SWEEP. "
        "It read: for all three, verify() cannot recover the recorded source, so the sweep cannot "
        "say whether the change was cosmetic. recorded_source() asked git for the producer AT THE "
        "COMMIT THE STAMP NAMES and gave up otherwise, while the stamp also carries the producer's "
        "sha256 -- a stronger key, since a blob that was ever committed is findable by content "
        "wherever it landed. Measured over results/**.json: 271 artifacts carry a stamp, 252 were "
        "written from a dirty tree, and 62 name a commit that does not contain their own producer, "
        "because a script written and run before it was committed stamps the HEAD it ran against. "
        "So the undiagnosable state this entry reported for three artifacts was the state of "
        "sixty-two. With _source_by_digest, 35 of the 62 recover exactly and the other 27 become a "
        "distinguishable class: their digest matches no committed version, so those producers ran "
        "in a state that was never committed, which is a different and worse fact than a wrong "
        "commit and was invisible while the two looked alike. Two pins that had been pushed red by "
        "an edit to nothing but their docstrings came back cosmetic_only on the same mechanism. "
        "WHAT THE THREE ARE NOW, each measured rather than asserted. "
        "results/gloryx_service_preds.json and results/uspto_type_overlap.json recover their "
        "sources (at 7dd9ef31d20d and 43f1e1dc3f46) and are diagnosed: the changes are substantive, "
        "not cosmetic. results/benchmark_report_depth2.json is not producer_changed at all but "
        "UNSTAMPED -- it carries five numbers and no provenance block, and the sweep reaches it "
        "through infer(). It has since been repaired: the producer records its own invocation and "
        "the artifact verifies current, so it has left this list. CLOSES for the other two never, "
        "the obstacles being an upstream file nobody can regenerate and someone else's web "
        "service.\n"
        "THE THIRD IS NEW AND IS AN INPUT, NOT A PRODUCER. "
        "results/metatox_outside_submission.json records scripts/typed_edit/population_definition.py "
        "among its inputs and that file moved when GLORYxR was admitted to WHOLE_TEST. What the "
        "ingest takes from it is two things and both were re-read here rather than assumed: whether "
        "metatox is in the whole-population axis, which is still True, and the coverage floor, which "
        "is still 0.99. So the answer the artifact carries is unchanged and the sweep is right that "
        "nobody has re-derived it. It cannot be re-derived here: the two delivered SDFs total about "
        "1.1 GB, are not in the repository, and are not on this machine, which the artifact itself "
        "says of them. CLOSES when the deliveries are to hand and the ingest is re-run; check_inputs "
        "has no equivalent of semantic_equal, so an input that changed in a part this producer never "
        "reads cannot be told from one that changed under it.",
    # check_prose_rate.py carried an entry here twice, and both are paid. The first was the
    # length target, closed on a rewrite with every recorded concession relocated verbatim. The
    # second was the length target again, reopened by the material two reviews asked for -- the
    # headline on the whole evaluated split, precision as a Results table, a second worked
    # example, the control the drawing asymmetry needs, a precision-recall curve, and the
    # criterion grid cut to the three criteria this work defends. It closed when the co-author
    # chose where the words would come from: Limitations, 1465 words to 980, with eighteen
    # disclosures re-keyed, none deleted, and three given their hedge back after compression had
    # quietly taken them out of the register's reach. The body is at 8349 words against a target
    # of 8349.

    # Both entries argued the gap could not be closed without removing content. Both were
    # wrong, and in the same way: the first closed on a rewrite with every recorded concession
    # relocated verbatim, the second on a compression that lost none either. What each recorded
    # is in the history of the commits that closed it. An entry describing a state that is gone
    # is what the check beside this file forbids, which is why neither is still here.
}


@pytest.mark.parametrize("script,args", GATES,
                         ids=[f"{g[0]}{'-' + g[1][0].lstrip('-') if g[1] else ''}"
                              for g in GATES])
def test_paper_gate_exits_zero(script, args):
    path = ROOT / "scripts" / script
    if not path.exists():
        pytest.skip(f"{script} is not in this checkout")
    for a in args:
        if a.endswith(".md") and not (ROOT / a).exists():
            pytest.skip(f"{a} is not in this checkout")
    # Some gates read a build the repository does not carry: the manuscripts' LaTeX logs are not
    # committed, so a clone that has never compiled them has nothing for the build gate to check.
    # Skipping there is right -- the gate has no input, it has not passed -- and failing there
    # would make continuous integration red for a reason that says nothing about the code.
    for needed in NEEDS.get(script, ()):
        if not (ROOT / needed).exists():
            pytest.skip(f"{script} needs {needed}, which this checkout has not built")
    run = subprocess.run([sys.executable, str(path), *args], cwd=ROOT,
                         capture_output=True, text=True, timeout=600)

    # A crash and a refusal both exit non-zero, so this has to come BEFORE the debt branch.
    # Without it, a gate that cannot even be parsed exits non-zero, matches its declared debt, and
    # is recorded as the failure it was expected to have: the suite would stop distinguishing "the
    # prose is unfixed" from "the gate is unparseable", and the debt mechanism -- written to keep
    # red gates honest -- would be the thing hiding a broken one. That is not hypothetical; a
    # docstring edit left check_prose_rate.py with two closing quote triples and a SyntaxError,
    # and this branch is what separates that from an unpaid debt.
    crashed = "Traceback (most recent call last)" in run.stderr or "SyntaxError" in run.stderr
    assert not crashed, (
        f"{script} did not run at all -- it crashed rather than reaching a verdict, so this tells "
        f"you nothing about the paper.\n--- stderr ---\n{run.stderr[-2000:]}")

    debt = DECLARED_DEBT.get(script)
    if debt is not None:
        assert run.returncode != 0, (
            f"{script} passes, so it is no longer a declared debt: remove its entry from "
            f"DECLARED_DEBT in this file. Leaving a paid debt on the books is how a gate stops "
            f"meaning anything.\nThe entry said: {debt}")
        pytest.xfail(f"declared debt -- {debt}")

    assert run.returncode == 0, (
        f"{script} exited {run.returncode}\n"
        f"--- stdout ---\n{run.stdout[-4000:]}\n--- stderr ---\n{run.stderr[-2000:]}")


STRATA = [
    # (artifact, in-arm file, complement file, the row flag that means `in the arm')
    ("h1_stratum.json", "sparse_at_rule_dense_at_type.txt",
     "sparse_at_rule_dense_at_type_complement.txt", "in_stratum"),
    ("h6_stratum.json", "trivial_automorphism.txt", "nontrivial_automorphism.txt", "trivial"),
]

ORBIT_ARM = ("h6_stratum.json", "orbit_ge3.txt", "orbit_ge3_complement.txt")


def test_h6_treatment_arm_is_the_orbit_three_substrates():
    """H6 registers its treatment prediction on this file, so it must be exactly that arm."""
    import json

    art = ROOT / "results" / ORBIT_ARM[0]
    txt, comp = ROOT / "strata" / ORBIT_ARM[1], ROOT / "strata" / ORBIT_ARM[2]
    if not art.exists() or not txt.exists():
        pytest.skip("the H6 arms have not been built in this checkout")
    d = json.loads(art.read_text())
    wanted = sorted(r["substrate"] for r in d["rows"] if r["largest_orbit"] >= 3)
    listed = [l for l in txt.read_text().splitlines() if l.strip()]
    other = [l for l in comp.read_text().splitlines() if l.strip()]
    assert listed == wanted, f"the arm holds {len(listed)}, orbit>=3 is {len(wanted)}"
    assert len(listed) == d["n_orbit_ge3"]
    assert len(listed) + len(other) == d["n_substrates"], "the arm and its complement do not partition"


@pytest.mark.parametrize("artifact,arm,complement,flag", STRATA,
                         ids=[s[1].replace(".txt", "") for s in STRATA])
def test_stratum_file_matches_its_artifact(artifact, arm, complement, flag):
    """A membership file and the run that produced it cannot drift apart.

    Each hypothesis is registered on a file of substrate SMILES. If one were edited, or
    regenerated under a changed definition, the hypothesis would quietly become a different
    one. Each file has to be exactly the in-arm substrates of its committed artifact, and the
    two files have to partition the split.
    """
    import json

    art = ROOT / "results" / artifact
    txt, comp = ROOT / "strata" / arm, ROOT / "strata" / complement
    if not art.exists() or not txt.exists() or not comp.exists():
        pytest.skip(f"{artifact} has not been built in this checkout")
    d = json.loads(art.read_text())
    listed = [l for l in txt.read_text().splitlines() if l.strip()]
    other = [l for l in comp.read_text().splitlines() if l.strip()]
    from_rows = sorted({r["substrate"] for r in d["rows"] if r[flag]})
    assert listed == from_rows, (
        f"{arm} holds {len(listed)} substrates, the artifact {len(from_rows)}")
    assert len(listed) + len(other) == d["n_substrates"], f"{arm} and {complement} do not partition"
    assert not set(listed) & set(other), f"{arm} and {complement} overlap"


def test_split_manifest_still_matches_the_data():
    """The freeze is a claim about data the repository does not hold; verify it holds anyway.

    If the external dataset is absent this skips, which is the honest outcome: nothing was
    checked. If it is present and any fingerprint moved, the preregistration is registered
    against a split that no longer exists.
    """
    manifest = ROOT / "paper2" / "split_manifest.json"
    data = ROOT / "grail_metabolism" / "data" / "test_triples_clean.txt"
    if not manifest.exists() or not data.exists():
        pytest.skip("the split manifest or the external dataset is not in this checkout")
    run = subprocess.run([sys.executable, str(ROOT / "scripts" / "typed_edit" / "freeze_split.py"),
                          "--verify"], cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert run.returncode == 0, f"the split moved since the freeze\n{run.stdout[-3000:]}"


def test_h1_primary_stratum_is_the_intersection():
    """The primary membership file must be exactly the pairs every join key agrees on.

    H1 names this file as its primary definition in advance, so it cannot be the file that
    happened to come out best. The two files also have to partition the substrates that carry
    at least one typeable reference -- not the whole split, because 14 substrates carry none.
    """
    import json

    art = ROOT / "results" / "h1_join_sensitivity.json"
    txt = ROOT / "strata" / "sparse_at_rule_dense_at_type_intersection.txt"
    comp = ROOT / "strata" / "sparse_at_rule_dense_at_type_intersection_complement.txt"
    if not art.exists() or not txt.exists():
        pytest.skip("the join sensitivity has not been computed in this checkout")
    d = json.loads(art.read_text())
    keys = d["primary"]["keys"]
    wanted = sorted({r["substrate"] for r in d["rows"]
                     if all(r["in_stratum"][k] for k in keys)})
    listed = [l for l in txt.read_text().splitlines() if l.strip()]
    other = [l for l in comp.read_text().splitlines() if l.strip()]
    assert listed == wanted, f"the primary file holds {len(listed)}, the intersection {len(wanted)}"
    assert len(listed) == d["primary"]["substrates"]
    typeable = {r["substrate"] for r in d["rows"]}
    assert len(listed) + len(other) == len(typeable), "the two files do not partition"
    assert not set(listed) & set(other)
    # the ceiling the registration quotes has to be the one the arithmetic gives
    assert d["feasibility"]["max_gain_for_K"]["2.5"] == int(d["n_typeable_pairs"] // 2.5)


# --refresh-text rewrites the `text` snapshot in the concession registry for keys whose identity
# has not changed. That is a writer pointed at the one artifact this project has already destroyed
# once, so the refusals matter more than the feature: refreshing on a tree whose disclosures have
# MOVED would leave a green --check and a freshened snapshot, removing both signals a retraction
# leaves behind, and rewriting reviewed_and_accepted would rewrite what a human agreed to and the
# text they agreed it against. Asserting the flag works proves nothing about either; the test
# therefore perturbs the artifact and demands a refusal. It restores the bytes in a finally.
def test_refresh_text_refuses_what_it_must():
    import json
    art = ROOT / "results" / "disclosure_inventory.json"
    if not art.exists():
        pytest.skip("the concession registry is not in this checkout")
    orig = art.read_bytes()

    def run():
        return subprocess.run([sys.executable, "scripts/disclosure_inventory.py", "--refresh-text"],
                              cwd=ROOT, capture_output=True, text=True)
    try:
        # a disclosure the documents no longer hold: a retraction, and never a text refresh
        d = json.loads(orig)
        d["disclosures"]["a key no document holds any more, recorded so this cannot pass"] = {
            "text": "A sentence that was retracted and must not be refreshed away.",
            "in": ["paper2/si.tex"]}
        art.write_text(json.dumps(d, indent=1))
        r = run()
        assert r.returncode == 1, f"a retracted disclosure was not refused:\n{r.stdout}"
        assert "no longer agree" in r.stderr and "gone:" in r.stderr, r.stderr

        # a disclosure the record does not hold: the key sets disagree the other way
        d = json.loads(orig)
        d["disclosures"].pop(next(iter(d["disclosures"])))
        art.write_text(json.dumps(d, indent=1))
        r = run()
        assert r.returncode == 1, f"an unrecorded disclosure was not refused:\n{r.stdout}"
        assert "no longer agree" in r.stderr, r.stderr

        # the decisions and the text they were taken against are never rewritten
        d = json.loads(orig)
        if d.get("reviewed_and_accepted"):
            keep = "DELIBERATELY STALE record of what was agreed, which must survive a refresh."
            d["reviewed_and_accepted"][0]["text"] = keep
            art.write_text(json.dumps(d, indent=1))
            r = run()
            assert r.returncode == 0, r.stderr
            back = json.loads(art.read_text())
            assert back["reviewed_and_accepted"][0]["text"] == keep, \
                "--refresh-text rewrote what a human accepted"
            assert len(back["reviewed_and_accepted"]) == len(d["reviewed_and_accepted"])
    finally:
        art.write_bytes(orig)
        assert art.read_bytes() == orig, "the registry was not restored"
