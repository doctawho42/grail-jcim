# A machine-readable reference set for the radiolabelled human ADME benchmark

## Why

The strongest limitation this paper states is that no measurement in it is external: every
figure is measured on one corpus, assembled here, whose selection cannot be recovered. The
radiolabelled human ADME data of Gao and co-workers (JCIM 2026, 66, 2918-2928,
doi:10.1021/acs.jcim.5c03045) is *in vivo* human data on exactly the population this work
predicts, and it would answer that limitation. It has not been used because its known
metabolites appear only as drawings.

Ninety-seven structures across eleven drugs is a bounded job. What comes out of it is three
things at once: a run of every arm on human *in vivo* data, an answer to "everything is measured
on a corpus you assembled and cannot reconstruct", and a citable resource the field does not
have and whose absence this paper itself reports.

## What is already here, and where it came from

| file | what | source |
|---|---|---|
| `substrates.csv`, `substrates.smi` | the eleven parent structures | the string each of the benchmark's own SyGMa input scripts passes to RDKit, in `artifacts/external/gao2026/*.py` |
| `metabolites.csv` | the sheet to fill: one empty row per published metabolite | row counts are the per-drug reference-set sizes the benchmark's Table S12 publishes, transcribed in `results/external_budget_confound.json` |
| `manifest.json` | the above, with digests and provenance | written by `scripts/external_reference_set.py` |

Nothing in this directory was guessed. No metabolite structure is filled in, because reading one
off a figure is the thing a chemist does and a script must not.

**One thing to confirm before drawing.** The published table names a drug *Fovinaciclib*; the
deposit names its files *FCN-437c*. Those are the only unmatched names on either side and
FCN-437c is the development code, so they are paired here, with the pairing recorded rather than
merged in silence. A wrong pairing would attach one drug's metabolite count to another drug's
structure and nothing downstream would catch it.

## The job

Fill the `smiles` column of `metabolites.csv`, one row per metabolite, drawing from the
benchmark's figures. The `note` column is free text: put the metabolite identifier the paper
gives it there, so a reader can check a row against the source.

The row count per drug is fixed in advance and must not change:

| drug | metabolites |
|---|---|
| Opicapone | 16 |
| Encorafenib | 12 |
| Iberdomide | 12 |
| Tinengotinib | 11 |
| Fovinaciclib | 10 |
| Pamiparib | 8 |
| Isavuconazole | 7 |
| Nemiralisib | 7 |
| LY3202626 | 6 |
| Sotorasib | 5 |
| Rezafungin | 3 |

Then:

```
python scripts/external_reference_set.py --check
```

It refuses a sheet with the wrong number of rows for a drug, a structure that does not parse,
the same structure twice within one drug, a metabolite equal to its own substrate, a drug it
does not know, and an empty cell. It reports every problem at once rather than the first, and
for each accepted row it prints the formula change from the substrate, which is where a
mis-drawn ring shows up.

## What the run then needs

Four of the arms come free: the benchmark deposited each tool's own output for all eleven drugs.

| arm | state | file |
|---|---|---|
| SyGMa | in the deposit, 11 of 11 | `artifacts/external/gao2026/<drug>.txt` |
| MetaPredictor | in the deposit, 11 of 11 | `artifacts/external/gao2026/<drug>_MP.txt` |
| BioTransformer | in the deposit, 11 of 11 | `artifacts/external/gao2026/<drug>.csv` |
| GLORYx | in the deposit, 11 of 11 | `artifacts/external/gao2026/<drug>-gloryx-*.csv` |
| GRAIL exhaustive | to run here | the deployed checkpoints, as everywhere else |
| GRAIL interactive | to run here | the same, at the deployed rule budget |
| GLORYxR, default and strict | to run here | the local build |
| MetaTox | a submission | the web service, as for the 1170 |

The eleven substrates are in `substrates.smi` in the form the benchmark's own tools were given,
which is the form each arm should receive, so the drawing axis this paper declares is held fixed
across the external set as well.
