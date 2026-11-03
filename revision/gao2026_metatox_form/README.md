# MetaTox on the radiolabelled human ADME benchmark

Eleven drugs whose human metabolites are known from radiolabelled ADME studies, from the
benchmark of Gao and co-workers (JCIM 2026, 66, 2918-2928, doi:10.1021/acs.jcim.5c03045).
That paper scores five predictors on these substrates. MetaTox is not one of them, so this
run adds a column the published table does not have.

## What to run

The same configuration as the submission the paper reports: the SMIRKS mode, one step,
whatever score the service returns per predicted structure. Nothing else changes.

Upload either file:

- `substrates.smi` - one `<SMILES>\t<id>` per line
- `substrates.sdf` - the same molecules, `_Name` set to the id

## What to return

One row per predicted structure, keyed by the id:

    id, predicted_smiles, score

## Two things to know before running

**The drawing is deliberately not canonicalised.** Each string is the one the benchmark's own
input scripts pass, because that is what the five published columns were produced from. If the
service canonicalises on the way back, key the answer by the id and not by the returned
substrate string.

**One name is an inference.** The published table calls a drug Fovinaciclib; the deposit calls its
files FCN-437c. They are the only unmatched names on either side, so the pairing is near
certain, and it is still worth a look before the answer is scored.

## How big the job is

11 substrates, against 97 published metabolites in all. Per drug:

- Encorafenib: 12
- Fovinaciclib: 10
- Iberdomide: 12
- Isavuconazole: 7
- LY3202626: 6
- Nemiralisib: 7
- Opicapone: 16
- Pamiparib: 8
- Rezafungin: 3
- Sotorasib: 5
- Tinengotinib: 11

## What it is for

This paper's strongest stated limitation is that no measurement in it is external: everything is
measured on a corpus assembled for it, whose selection cannot be reconstructed. These eleven
substrates are *in vivo* human data on exactly the population this work predicts. A run here is
the first measurement in the paper that is not ours.

One caveat on what the answer can be scored against. The benchmark publishes its metabolites as
drawings, and a substantial part of them are not single structures: a region is marked with a
bracket or a dashed box and labelled with a mass change, which states that something of that mass
happened in that neighbourhood and not where. Of the ninety-two metabolite rows drawn in the
Supporting Information, fifty-three are drawn in full, twenty-two are marked, and seventeen carry
one signal of being marked and not the other. So part of this set can only be scored by formula,
and the run itself is unaffected: it is the scoring that has to say which rows it used.
