# GRAIL

GRAIL (Graph-scored Rule Application with Inspectable Localisation) predicts the **structures** of
the metabolites a xenobiotic will produce, and says which reaction template produced each one and
which atoms it acted on. It runs in three stages:

1. a multi-label generator scores biotransformation SMIRKS templates against the substrate graph
   and selects which to apply;
2. RDKit applies the selected templates and enumerates candidate products;
3. a binary filter scores each (substrate, product) pair, and the candidates are ordered by a
   reciprocal rank fusion of the two scores (K = 60), which is the ranking a caller receives.

Every prediction therefore arrives with its provenance: not a score alone but the template and
the site, so a chemist can reject a candidate on mechanistic grounds.

This repository accompanies one paper and contains what that paper is made of: the package, the
manuscript sources, the artifacts every figure is read from, the scripts that produced those
artifacts, and the checks that hold the three together.

## Running it

```
make install          # pip install -r requirements.txt and the package
make test             # the unit and regression suite; no dataset needed
make smoke            # a CLI prediction and a preset export
grail predict "CCO" --rules grail_metabolism/resources/example_rules.txt
```

The training corpus is not redistributed here. `docs/DATASETS.md` says what it is and where the
parts come from; `grail_metabolism/data/` is where they go.

## Reproducing the paper

One command regenerates every number, table and figure, re-stamps the artifacts whose inputs
moved, runs the provenance and prose gates, and compiles both documents:

```
bash scripts/finish_revision_pass.sh
```

It refuses rather than writing when a figure in the manuscript no longer matches the artifact it
came from, when an artifact's producer has changed since the artifact was written, or when a
number appears in the text that is not generated from one.

The comparison can also be rebuilt without the corpus. The known metabolites are not released as
structures; what is released is the set of descriptors the matching criteria are decided by, one
per metabolite, in `results/test_reference_descriptors.json`.
`scripts/typed_edit/reproduce_from_descriptors.py` rebuilds the whole comparison from them under
every criterion, reading no corpus structure at any point.

## What is here

| path | what |
|---|---|
| `grail_metabolism/` | the package: data assembly, featurisation, the two models, workflows, CLI |
| `paper2/` | the manuscript and its Supporting Information, and `preregistration.md`, the register of predictions with the threshold and falsification condition each was fixed under |
| `results/` | every artifact a figure or a number is read from, each recording the script that wrote it and the digest of that script's source |
| `scripts/` | the producers of those artifacts and the checks over them; `scripts/README.md` describes the chain |
| `artifacts/full5000_released/` | the deployed generator and filter checkpoints |
| `artifacts/tier2/`, `artifacts/tier2_1170/` | the comparators' prediction files as they were scored |
| `revision/` | the reference sets, submission forms and calibrations built during revision, with their own tests |
| `configs/` | the experiment presets as YAML |

The train and validation candidate pools are too large for a repository and are deposited
separately; every substrate and metabolite in them is replaced by its tautomer-canonical InChIKey
before the archive is built, so the deposit holds no source structure.

## Third-party material

The rule bank contains templates published by others, and `NOTICE.md` states the terms of each,
including one obligation that remains outstanding. Comparator tools are cited rather than
redistributed; their prediction files are here because they are the output this work scored, not
the tools themselves.

## Licence

See `LICENSE` for this work and `NOTICE.md` for everything in it that belongs to somebody else.
