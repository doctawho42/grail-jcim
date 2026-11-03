#!/usr/bin/env python3
"""The eleven radiolabelled-ADME substrates, packaged for a run that adds a column to their table.

The benchmark of Gao and co-workers scores five published predictors on eleven drugs whose human
metabolites are known from radiolabelled ADME studies. It is the one dataset that would answer
this paper's own stated limitation, that every measurement in it is made on a corpus assembled
here. Adding this work's arms to that table needs the substrates run, and MetaTox is not among
the five, so running it adds a column the benchmark does not have.

What matters in the packaging is that nothing is redrawn. Each of the five published columns was
produced from the parent structure as the benchmark's own input scripts write it, and a column
measured on a re-tautomerised or desalted drawing of the same molecule is a measurement of
something else that looks like it belongs in the same table. So the strings here are copied, not
canonicalised, and the test beside this producer asserts that character for character.

    python scripts/make_gao_metatox_form_input.py

Writes revision/gao2026_metatox_form/: substrates.smi, substrates.sdf, substrate_map.csv,
manifest.json and README.md.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _provenance import record_inputs, stamp  # noqa: E402

HELD = ROOT / "revision" / "gao2026_reference_set" / "substrates.csv"
TABLES = ROOT / "revision" / "gao2026_reference_set" / "si_tables.json"
OUT = ROOT / "revision" / "gao2026_metatox_form"

# The deposit names one drug by its development code and the published table by its generic name.
# They are the only unmatched names on either side, so the pairing is near certain and is still an
# inference; it travels with the file rather than being resolved here.
UNCONFIRMED = ("Fovinaciclib", "FCN-437c")


def rows() -> list:
    with HELD.open() as fh:
        return list(csv.DictReader(fh))


def write(out: Path, substrates: list) -> dict:
    from rdkit import Chem
    from rdkit.Chem import AllChem

    out.mkdir(parents=True, exist_ok=True)
    redrawn = {}
    with (out / "substrates.smi").open("w") as fh:
        for r in substrates:
            fh.write(f"{r['smiles']}\t{r['drug']}\n")

    writer = Chem.SDWriter(str(out / "substrates.sdf"))
    for r in substrates:
        mol = Chem.MolFromSmiles(r["smiles"])
        if mol is None:
            raise SystemExit(f"REFUSING: {r['drug']} does not parse, so the file would carry a "
                             f"substrate no service can read")
        mol.SetProp("_Name", r["drug"])
        AllChem.Compute2DCoords(mol)
        writer.write(mol)
        canonical = Chem.MolToSmiles(mol)
        if canonical != r["smiles"]:
            redrawn[r["drug"]] = canonical
    writer.close()

    with (out / "substrate_map.csv").open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["id", "submitted_smiles", "rdkit_canonical_smiles",
                    "metabolites_published", "deposit_file"])
        for r in substrates:
            w.writerow([r["drug"], r["smiles"], redrawn.get(r["drug"], r["smiles"]),
                        r["metabolites_published"], r["deposit_file"]])
    return redrawn


def manifest(substrates: list, redrawn: dict) -> dict:
    published = {r["drug"]: int(r["metabolites_published"]) for r in substrates}
    read = {}
    if TABLES.exists():
        blob = json.loads(TABLES.read_text())
        read = {"drawn_in_the_supporting_information": blob["n_metabolites"],
                "readable_as_one_structure": blob["by_verdict"],
                "scored_without_a_table_here": blob["scored_without_a_table"]}
    return {
        "provenance": stamp(__file__),
        "inputs": record_inputs([HELD] + ([TABLES] if TABLES.exists() else [])),
        "question": "what MetaTox returns on the eleven substrates of the radiolabelled human "
                    "ADME benchmark, which scores five other predictors and not this one",
        "n_substrates": len(substrates),
        "published_metabolites": published,
        "n_published_metabolites": sum(published.values()),
        "reference_set": read,
        "drawing": "the string the benchmark's own input scripts pass, copied and not "
                   "canonicalised, because the five published columns were produced from it",
        "redrawn_by_rdkit": redrawn,
        "unconfirmed_name_pairing": {"published_table": UNCONFIRMED[0],
                                     "deposit_files": UNCONFIRMED[1],
                                     "status": "inferred from being the only unmatched name on "
                                               "either side, not confirmed"},
        "join": "the id, which is the drug name in the published table",
    }


README = """# MetaTox on the radiolabelled human ADME benchmark

Eleven drugs whose human metabolites are known from radiolabelled ADME studies, from the
benchmark of Gao and co-workers (JCIM 2026, 66, 2918-2928, doi:10.1021/acs.jcim.5c03045).
That paper scores five predictors on these substrates. MetaTox is not one of them, so this
run adds a column the published table does not have.

## What to run

The same configuration as the submission the paper reports: the SMIRKS mode, one step,
whatever score the service returns per predicted structure. Nothing else changes.

Upload either file:

- `substrates.smi` - one `<SMILES>\\t<id>` per line
- `substrates.sdf` - the same molecules, `_Name` set to the id

## What to return

One row per predicted structure, keyed by the id:

    id, predicted_smiles, score

## Two things to know before running

**The drawing is deliberately not canonicalised.** Each string is the one the benchmark's own
input scripts pass, because that is what the five published columns were produced from. If the
service canonicalises on the way back, key the answer by the id and not by the returned
substrate string.

**One name is an inference.** The published table calls a drug {published}; the deposit calls its
files {deposit}. They are the only unmatched names on either side, so the pairing is near
certain, and it is still worth a look before the answer is scored.

## How big the job is

{n} substrates, against {m} published metabolites in all. Per drug:

{table}

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
"""


def main(argv=None) -> int:
    substrates = rows()
    redrawn = write(OUT, substrates)
    blob = manifest(substrates, redrawn)
    (OUT / "manifest.json").write_text(json.dumps(blob, indent=1))
    table = "\n".join(f"- {r['drug']}: {r['metabolites_published']}" for r in substrates)
    (OUT / "README.md").write_text(README.format(
        published=UNCONFIRMED[0], deposit=UNCONFIRMED[1],
        n=blob["n_substrates"], m=blob["n_published_metabolites"], table=table))
    print(f"{blob['n_substrates']} substrates, {blob['n_published_metabolites']} published "
          f"metabolites, written to {OUT.relative_to(ROOT)}")
    if redrawn:
        print(f"  {len(redrawn)} whose RDKit canonical form differs from the string sent: "
              f"{', '.join(sorted(redrawn))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
