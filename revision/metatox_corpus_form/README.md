# MetaTox on the corpus drawing

336 substrates, in the drawing the corpus stores and every other arm of the comparison was
given. The first submission re-tautomerised these to the natural form, which was the right call
for the service and is why this control is missing.

## What to run

The same configuration as the submission the paper reports: the SMIRKS mode, one step, whatever
score the service returns per predicted structure. Nothing else changes.

Upload either file:

- `substrates.smi` — one `<SMILES>\t<id>` per line
- `substrates.sdf` — the same molecules, `_Name` set to the id

## What to return

One row per predicted structure, keyed by the molecule id above or by the SMILES in
`corpus_smiles`:

    id, predicted_smiles, score

Keyed by id is safer: the corpus drawing is an imidic tautomer and a service may canonicalise it
on the way back, in which case the returned string will not match the one sent.

## What it decides

The paper reports that the MetaTox column is read at a drawing that favours this work by an
amount it cannot bound. These runs bound it. If the recalls come back where they are, the
asymmetry costs nothing and the paper says so; if they come back higher, every MetaTox cell moves
and the paper says that instead.
