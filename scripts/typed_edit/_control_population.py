#!/usr/bin/env python3
"""Which files make up each population the comparison CONTROLS run on, in one place.

Named _control_population because scripts/_population.py already names the two
populations the convention and engine measurements use, and a second module of that
name shadows it on sys.path.

Four controls -- matched list length, the transformation classes, precision and the criterion
sweep -- were each written against the comparison set, with the pool paths and the comparator
prediction files typed into the producer. A reviewer asked for the controls that do not need the
web-service comparator to move onto the whole evaluated test set, and with the paths typed in
four times that is four chances for one of them to read a 291-substrate file while the other
three read a 1170-substrate one, producing a control nobody could tell was mixed.

So the population is a name, and the name resolves to the pools and the predictions together.
A producer takes --population and nothing else about where its inputs live.

One arm does not move. SyGMa re-run on the drawing the declared standardiser produces exists for
the comparison set alone, because the re-run was done on the substrates that had been submitted.
It is listed as absent from the whole split rather than dropped, so a control computed there
reports a roster one column shorter and says which column.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# (path, the key holding the per-substrate map, or None when the file is that map)
_COMPARISON = {
    "metatox": ("results/metatox_smirks_preds.json", "predictions"),
    "sygma": ("results/sygma_fulltest_predictions.json", None),
    "metapredictor": ("artifacts/tier2_1170/metapredictor_preds.json", None),
    "biotransformer": ("results/biotransformer_allhuman_one_step_preds.json", None),
    "gloryx": ("results/gloryx_service_preds.json", "predictions"),
    "sygma on the standardised drawing":
        ("results/sygma_standardised_predictions.json", "predictions"),
    "gloryxr_default": ("results/gloryxr_local_preds_default.json", "predictions"),
    "gloryxr_strict": ("results/gloryxr_local_preds_strict.json", "predictions"),
}

_WHOLE = {
    "metatox": ("results/metatox_smirks_preds_evaluated1170.json", "predictions"),
    "sygma": ("results/sygma_fulltest_predictions.json", None),
    "metapredictor": ("artifacts/tier2_1170/metapredictor_preds.json", None),
    "biotransformer": ("results/biotransformer_fulltest_preds.json", None),
    "gloryx": ("results/gloryx_service_preds_evaluated1170.json", "predictions"),
    "gloryxr_default": ("results/gloryxr_local_preds_default.json", "predictions"),
    "gloryxr_strict": ("results/gloryxr_local_preds_strict.json", "predictions"),
}

POPULATIONS = {
    "comparison": {
        "name": "the comparison set",
        "describes": ("the substrates submitted to the one comparator that runs as a web "
                      "service; the rule by which the list was drawn was not recorded"),
        "exhaustive": "results/widepools_implicit/w*.json",
        "interactive": "results/widepools_k30/all.json",
        "comparators": _COMPARISON,
        "absent": (),
        "suffix": "",
    },
    "whole": {
        "name": "the whole evaluated test set",
        "describes": "every test substrate with a known metabolite",
        "exhaustive": "results/widepools_fulltest/w*.json",
        "interactive": "results/widepools_k30_fulltest/w*.json",
        "comparators": _WHOLE,
        # Named rather than omitted: the corrected-drawing re-run was done on the submitted
        # substrates and exists nowhere else, so a control here is one column shorter and the
        # artifact has to say which column that is.
        "absent": ("sygma on the standardised drawing",),
        "suffix": "_1170",
    },
}


def population(name: str) -> dict:
    if name not in POPULATIONS:
        raise SystemExit(f"unknown population {name!r}; the names are "
                         f"{', '.join(sorted(POPULATIONS))}")
    spec = POPULATIONS[name]
    missing = [rel for rel, _ in spec["comparators"].values()
               if not (ROOT / rel).exists()]
    if missing:
        raise SystemExit(f"population {name!r} names prediction files that are not in this "
                         f"checkout: {missing}")
    dropped = set(_COMPARISON) - set(spec["comparators"]) - set(spec["absent"])
    if dropped:
        raise SystemExit(f"population {name!r} has no entry for {sorted(dropped)} and does not "
                         f"list them as absent, so a control here would compare against fewer "
                         f"systems than the comparison set does and say nothing")
    return spec


def out_path(stem: str, name: str) -> str:
    """results/<stem><suffix>.json, so the two populations cannot overwrite each other.

    The suffix itself comes from `_acs_table`, which the figures and the number generator also
    read, so a producer and its consumers cannot disagree about which file a population writes.
    """
    from _acs_table import control_artifact

    assert POPULATIONS[name]["suffix"] == control_artifact("", name)[:-5], (
        f"the suffix this map records for {name!r} and the one _acs_table derives disagree; "
        f"they are the same fact and must come from one place")
    return str(ROOT / "results" / control_artifact(stem, name))


# The producers spell the comparators two ways: the sweep's slugs and the precision table's
# display names. Resolving both here means a producer keeps the spelling its artifact already
# publishes while still taking its files from one place.
_ALIAS = {
    "metatox": "metatox", "sygma": "sygma", "metapredictor": "metapredictor",
    "biotransformer": "biotransformer", "gloryx": "gloryx",
    "gloryxr_default": "gloryxr_default", "gloryxr_strict": "gloryxr_strict",
    "sygma on the standardised drawing": "sygma on the standardised drawing",
    "MetaTox": "metatox", "SyGMa": "sygma", "MetaPredictor": "metapredictor",
    "BioTransformer": "biotransformer", "GLORYx": "gloryx",
    "GLORYxR default SoM": "gloryxr_default", "GLORYxR strict SoM": "gloryxr_strict",
    "GRAIL exhaustive": None, "GRAIL interactive": None,
}


def resolve(comparators: dict, name: str) -> dict:
    """The producer's own map, with each path replaced by the population's file for that arm.

    Keys and their order are kept, because they are what the artifact publishes and what the
    figures read. An arm the population does not carry is dropped from the returned map and is
    in the population's `absent` list, which the artifact records.
    """
    spec = population(name)
    out = {}
    for label, (rel, key) in comparators.items():
        slug = _ALIAS.get(label)
        if slug is None and label not in _ALIAS:
            raise SystemExit(f"no population entry for the comparator {label!r}; add it to "
                             f"_ALIAS so a run on another population cannot silently keep the "
                             f"file this one was written with")
        if slug is None:
            out[label] = (rel, key)          # one of our own arms, not a comparator
            continue
        if slug not in spec["comparators"]:
            continue                          # listed in `absent`, and the artifact says so
        out[label] = spec["comparators"][slug]
    return out


def absent_from(comparators: dict, name: str) -> list:
    """Of the arms THIS producer reads, the ones the population does not carry.

    The population's own `absent` list is a property of the population; what an artifact needs to
    record is narrower -- a column it would have had and does not. Naming the population's whole
    absence beside a table that never carried that arm reads as a missing column, so each producer
    records the intersection with its own roster.
    """
    spec = population(name)
    mine = {_ALIAS.get(label, label) for label in comparators}
    return [a for a in spec["absent"] if a in mine]
