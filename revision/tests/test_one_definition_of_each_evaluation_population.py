"""Each evaluation population is one definition, and a comparator it loses is named.

Run: python -m pytest revision/tests/test_one_definition_of_each_evaluation_population.py -q

Four controls were each written against the comparison set with their pool paths and their
comparator prediction files typed into the producer. Moving them onto the whole evaluated test
set means changing, in four files, which pools are read and which of two prediction files each
comparator contributes -- and the two files differ per comparator, so MetaTox's whole-split
predictions live under one name and its comparison-set predictions under another. Four copies of
that mapping is four chances for one control to read a 291-substrate file while the other three
read a 1170-substrate one, and nothing in the artifact would say the control was mixed.

The mapping is therefore one object. What this checks is that it stays one: that every file it
names exists, that each population's pools really carry the substrates it claims, and above all
that a comparator present for one population and absent for the other is listed as absent rather
than quietly missing. One is: SyGMa re-run on the standardiser's drawing exists only for the
substrates that were submitted, so a control on the whole split is one column shorter, and the
population has to say which column instead of leaving a reader to count.
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "typed_edit"))


@pytest.fixture
def pop():
    import _control_population as m
    return m


def test_every_file_each_population_names_exists(pop):
    for name in pop.POPULATIONS:
        pop.population(name)          # refuses on a missing prediction file
        for key in ("exhaustive", "interactive"):
            pat = str(ROOT / pop.POPULATIONS[name][key])
            assert glob.glob(pat), f"{name}: no pool file matches {pat}"


def test_a_comparator_one_population_loses_is_named_absent(pop):
    base = set(pop.POPULATIONS["comparison"]["comparators"])
    for name, spec in pop.POPULATIONS.items():
        lost = base - set(spec["comparators"])
        assert lost == set(spec["absent"]), (
            f"{name}: loses {sorted(lost)} against the comparison set and lists "
            f"{sorted(spec['absent'])} as absent")


def test_the_pools_carry_the_substrates_the_population_is_for(pop):
    seen = {}
    for name, spec in pop.POPULATIONS.items():
        got = {}
        for key in ("exhaustive", "interactive"):
            subs = set()
            for f in sorted(glob.glob(str(ROOT / spec[key]))):
                subs |= set(json.loads(Path(f).read_text())["pools"])
            got[key] = subs
        assert got["exhaustive"] == got["interactive"], (
            f"{name}: the two arms' pools cover different substrates, "
            f"{len(got['exhaustive'])} against {len(got['interactive'])}")
        seen[name] = len(got["exhaustive"])
    assert seen["whole"] > seen["comparison"], (
        f"the whole split ({seen['whole']}) is not larger than the comparison set "
        f"({seen['comparison']}), so one of the two is pointed at the wrong pools")


def test_each_comparator_file_covers_the_population_it_is_listed_for(pop):
    """A 291-substrate file listed for the whole split is the mix this map exists to prevent."""
    sizes = {}
    for name, spec in pop.POPULATIONS.items():
        n = 0
        for f in sorted(glob.glob(str(ROOT / spec["exhaustive"]))):
            n += len(json.loads(Path(f).read_text())["pools"])
        for comp, (rel, key) in spec["comparators"].items():
            blob = json.loads((ROOT / rel).read_text())
            preds = blob[key] if key else blob
            sizes[(name, comp)] = len(preds)
            # A comparator may answer for fewer substrates than the population holds -- that is
            # measured and scored zero -- but it may not be a file built for a smaller one.
            assert len(preds) >= n * 0.9, (
                f"{name}/{comp}: {rel} carries {len(preds)} substrates against a population of "
                f"{n}, which is a file for the other population")


def test_the_two_populations_write_to_different_artifacts(pop):
    for stem in ("matched_length", "precision_table", "error_by_chemistry", "criterion_sweep"):
        a = pop.out_path(stem, "comparison")
        b = pop.out_path(stem, "whole")
        assert a != b, f"{stem}: both populations would write to {a}"


# ---------------------------------------------------------------------------
# The four producers keep their own comparator rosters, because the keys are what their artifacts
# publish and what the figures read; only the file behind each key moves with the population. That
# split is the thing worth checking: a roster the map does not recognise, or an absence recorded
# from the population rather than from the roster, both leave an artifact saying something false
# about its own columns.

def _producers():
    """Every producer that takes its paths from the population map, found by its import.

    Globbed rather than typed, so a fifth control wired the same way is checked without anyone
    remembering to add it to a list here.
    """
    out = {}
    for f in sorted(glob.glob(str(ROOT / "scripts" / "typed_edit" / "*.py"))):
        src = Path(f).read_text()
        if "_control_population" in src and "COMPARATORS" in src:
            out[Path(f).name] = src
    return out


def _roster(src):
    """The module-level COMPARATORS of a producer, read without importing it.

    Importing would pull in torch through bank_without_selection, which costs more than this
    whole file and is not what is being checked.
    """
    import ast

    tree = ast.parse(src)
    node = next((n.value for n in tree.body
                 if isinstance(n, ast.Assign)
                 and getattr(n.targets[0], "id", None) == "COMPARATORS"), None)
    assert node is not None, "no module-level COMPARATORS"
    return {ast.literal_eval(k): ast.literal_eval(v) for k, v in zip(node.keys, node.values)}


def test_the_producers_wired_to_the_map_were_found():
    """Guards the glob: a resolver nothing reaches is a check that passes by finding nothing."""
    found = _producers()
    assert len(found) >= 4, f"expected the four controls, found {sorted(found)}"


def test_every_producer_roster_resolves_under_both_populations(pop):
    for name, src in _producers().items():
        roster = _roster(src)
        for which in pop.POPULATIONS:
            resolved = pop.resolve(roster, which)
            assert resolved, f"{name}/{which}: resolved to no arms at all"
            for label, (rel, _key) in resolved.items():
                assert (ROOT / rel).exists(), f"{name}/{which}/{label}: {rel} is missing"


def test_a_producer_records_the_absence_its_own_roster_would_show(pop):
    """The population's whole absence beside a table that never had that arm reads as a gap."""
    def offends(src):
        return 'list(spec["absent"])' in src or "list(spec['absent'])" in src

    # The check first fails on the form it exists to reject, so a producer passing it means
    # something.
    assert offends('"comparators_absent": list(spec["absent"])')
    assert not offends('"comparators_absent": absent_from(COMPARATORS, args.population)')

    for name, src in _producers().items():
        assert not offends(src), (
            f"{name} records the population's whole absence; it should record only the arms its "
            f"own roster names, through absent_from")
        assert "absent_from(" in src, f"{name} records no absence at all"


def test_absent_from_names_only_what_the_roster_carries(pop):
    with_arm = {"sygma": 1, "sygma on the standardised drawing": 1}
    without = {"MetaTox": 1, "SyGMa": 1}
    assert pop.absent_from(with_arm, "whole") == ["sygma on the standardised drawing"]
    assert pop.absent_from(without, "whole") == []
    for roster in (with_arm, without):
        assert pop.absent_from(roster, "comparison") == []


def test_resolve_refuses_a_comparator_the_map_does_not_know(pop):
    """Otherwise a newly added arm silently keeps the file the other population reads."""
    with pytest.raises(SystemExit):
        pop.resolve({"SomeNewTool": ("results/test_references.json", None)}, "whole")
