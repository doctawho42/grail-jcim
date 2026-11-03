#!/usr/bin/env python3
"""How much of this manuscript is written as a denial, measured per section.

A referee read the submission and reported that 44% of its prose sentences carry a negation, that
the rate per thousand words had risen while the paper shrank, and that the two worst sections are
the two a referee reads last. The objection is not that denials are wrong. Several of them are the
findings: no system leads across the sweep, and this work does not lead at the tight budgets. The
objection is that a reader who meets a denial where a statement would do has to build the
statement themselves, and the manuscript asked that of them in two sentences out of three in
Limitations.

So this counts them, per section, before and after. Two quantities and not one: the share of
sentences carrying any denial, and the rate per thousand words. They separate exactly on the
sentences carrying more than one, which is the population a rewriting pass is aimed at, and a
report giving only the first would call the pass finished while the doubled sentences stood.

The ceiling is measured rather than chosen. The eight comparison papers that ground every other
prose gate here are refetched and counted the same way, and the extraction is checked against the
per-paper word counts the existing corpus artifact records, so a ceiling is only written when this
file's extraction reproduces the one those gates were built on.

    python scripts/negation_density.py                 # the manuscript, against the corpus
    python scripts/negation_density.py --build-corpus  # refetch the eight and measure them too
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

BODY = ROOT / "paper2" / "body.tex"
CORPUS = ROOT / "results" / "prose_rate_corpus.json"
OUT = ROOT / "results" / "negation_density.json"

# The narrow set: a word whose job in the sentence is to deny. `\b` at both ends, so `norm`,
# `nothing` inside `notwithstanding` and `cannon` are not among them; `nevertheless` is a
# concession and not a denial of anything in its own clause, so it is out by construction.
NARROW = r"\b(?:not|n't|no|none|never|neither|nor|cannot|nothing|nowhere)\b"
# The referee quotes a second, wider rate. These deny by lexical content rather than by syntax,
# and they read very differently: `the rule fails` is a statement about what happened, and
# `without the reactant` is a condition rather than a denial of the sentence it sits in. They are
# counted apart so the two rates the referee quotes can both be reproduced, and so a pass that
# moves one of them cannot be reported as having moved the other.
BROAD = r"\b(?:without|fails?|failed|absent|lacking|lacks?|unable|impossible)\b"
_NARROW_RE = re.compile(NARROW, re.I)
_BROAD_RE = re.compile(BROAD, re.I)


def negations(sentence: str, broad: bool = False) -> list:
    """Every denial in one sentence, in order, lower-cased.

    `broad=False` is the narrow syntactic set and is what the share and the rate are built on;
    `broad=True` returns only the lexical ones, so the two can be added or reported apart rather
    than silently pooled.
    """
    pat = _BROAD_RE if broad else _NARROW_RE
    out = []
    for m in pat.finditer(sentence):
        w = m.group(0).lower()
        out.append("not" if w == "n't" else w)
    return out


def _sentences(text: str) -> list:
    import check_prose_density as cpd

    return [s for b in cpd.blocks(text) for s in cpd.sentences(b)]


def _words(s: str) -> int:
    return len([w for w in re.split(r"\s+", s.strip()) if w])


def measure(text: str, pre_split: list | None = None) -> dict:
    """The two rates and the shape of the sentences they are measured over."""
    sents = pre_split if pre_split is not None else _sentences(text)
    sents = [s for s in sents if _words(s) >= 3]
    words = sum(_words(s) for s in sents)
    if not sents or not words:
        raise SystemExit(
            "REFUSING: no prose to measure. A rate over no words is a number that cannot be "
            "wrong, which is the one kind this file exists to avoid producing.")
    per = [negations(s) for s in sents]
    broad = [negations(s, broad=True) for s in sents]
    lens = [_words(s) for s in sents]
    return {
        "words": words,
        "sentences": len(sents),
        "median_sentence_words": int(statistics.median(lens)),
        "sentences_at_least_35_words": sum(1 for n in lens if n >= 35),
        "sentences_with_a_negation": sum(1 for p in per if p),
        "sentences_with_two_or_more": sum(1 for p in per if len(p) >= 2),
        "sentences_with_three_or_more": sum(1 for p in per if len(p) >= 3),
        "negations": sum(len(p) for p in per),
        "negations_broad_only": sum(len(b) for b in broad),
        "share_of_sentences": round(sum(1 for p in per if p) / len(sents), 4),
        "per_1000_words": round(1000 * sum(len(p) for p in per) / words, 2),
        "per_1000_words_narrow_and_broad":
            round(1000 * sum(len(p) + len(b) for p, b in zip(per, broad)) / words, 2),
    }


def by_section(src: str) -> dict:
    r"""The manuscript split at its own `\section{}` headings, which are read and not listed here.

    A typed section list is wrong the first time a heading is renamed, and the headings of this
    manuscript were rewritten once already in this revision.
    """
    import prose_metrics as pm

    cuts = [(m.start(), m.group(1)) for m in re.finditer(r"\\section\*?\{([^}]*)\}", src)]
    if not cuts:
        raise SystemExit(r"REFUSING: paper2/body.tex carries no \section{}, so there is nothing "
                         r"to split on and a per-section report would be the whole file once.")
    out = {}
    for i, (start, title) in enumerate(cuts):
        end = cuts[i + 1][0] if i + 1 < len(cuts) else len(src)
        body = pm.strip_latex(src[start:end])
        if not body.strip():
            continue
        try:
            out[title] = measure(body)
        except SystemExit:
            continue
    return out


def _as_latex_dialect(paragraphs: list) -> str:
    r"""Plain prose presented the way the shared splitter expects to receive it.

    The splitter is the manuscript's, and it reads LaTeX: its first act is to delete everything
    after an unescaped `%`. Handed a journal body as one line, the first "over 70% of" truncated
    a 7,538-word paper to six words, and the measurement came back clean because six words is a
    valid thing to measure. So a percent sign is written the way LaTeX writes one, and each
    paragraph is its own block, as it is in the manuscript, so no sentence spans two.
    """
    return "\n\n".join(par.replace("\\", " ").replace("%", "\\%") for par in paragraphs)


def _fetch_corpus() -> dict:
    """The eight comparison papers again, counted for this probe.

    Refetched rather than stored: the existing artifact records each paper's word count and no
    text, so the only honest way to add a probe is to obtain the same records and show that this
    file's extraction reproduces those counts before any ceiling is read off it.
    """
    import urllib.request
    import xml.etree.ElementTree as ET

    recorded = json.loads(CORPUS.read_text())
    probe = next(iter(json.loads(CORPUS.read_text())["per_paper"].values()))
    pmcids = sorted(probe)
    out, mismatched = {}, []
    for pid in pmcids:
        url = ("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&retmode=xml&id="
               + pid.replace("PMC", ""))
        with urllib.request.urlopen(url, timeout=90) as fh:
            xml = fh.read().decode("utf-8", "replace")
        root = ET.fromstring(xml)
        body = root.find(".//body")
        if body is None:
            mismatched.append(f"{pid}: no body element in the record returned")
            continue
        # Body paragraphs and headings only, as the recorded corpus says: a caption, a table
        # cell and a reference are not prose read in sequence. Without the exclusion every paper
        # came back one to two thousand words long, which the control below caught.
        parent = {c: el for el in body.iter() for c in el}
        skip = {"table-wrap", "fig", "caption", "ref-list", "table", "disp-formula",
                "fn-group", "supplementary-material", "graphic", "media"}

        def inside_excluded(el):
            """True when an ancestor already contributed this element's text.

            `skip` is the material the recorded corpus excludes. The `p` is separate and was the
            last 20% of the over-count: a journal body nests a list inside a paragraph and the
            list items are paragraphs of their own, so `itertext()` on the outer one and a visit
            to each inner one count the same prose twice.
            """
            while el in parent:
                el = parent[el]
                if el.tag in skip or el.tag == "p":
                    return True
            return False

        chunks = [re.sub(r"\s+", " ", "".join(el.itertext())).strip()
                  for el in body.iter()
                  if el.tag in ("p", "title") and not inside_excluded(el)]
        text = _as_latex_dialect([c for c in chunks if c])
        m = measure(text)
        want = probe[pid]["words"]
        # The control. Within 2%: the two extractions use different XML walks and will not agree
        # to the token, but a paper whose count moves more than that is a different extraction
        # and its rate is not comparable with the ceilings the other gates are built on.
        m["recorded_words"] = want
        m["reproduces_the_recorded_extraction"] = abs(m["words"] - want) <= 0.02 * want
        if not m["reproduces_the_recorded_extraction"]:
            mismatched.append(f"{pid}: this extraction reads {m['words']} words, the corpus "
                              f"artifact records {want}")
        out[pid] = m

    # A paper this file cannot extract the same way is not comparable with the records the other
    # gates were built on, so it is left out of the ceiling. Leaving it out is only harmless if
    # it could not have raised the ceiling, and that is checked rather than assumed: a paper
    # whose rate is above the maximum of the reproduced ones would mean the exclusion decided
    # the answer, and then there is no ceiling to write.
    good = {k: v for k, v in out.items() if v["reproduces_the_recorded_extraction"]}
    if not good:
        raise SystemExit("REFUSING: no comparison paper reproduces the recorded extraction, so "
                         "there is nothing to read a ceiling from.\n  " + "\n  ".join(mismatched))
    ceil_share = max(v["share_of_sentences"] for v in good.values())
    ceil_rate = max(v["per_1000_words"] for v in good.values())
    decisive = [k for k, v in out.items()
                if not v["reproduces_the_recorded_extraction"]
                and (v["share_of_sentences"] > ceil_share or v["per_1000_words"] > ceil_rate)]
    if decisive:
        raise SystemExit(
            "REFUSING to write a ceiling: " + ", ".join(decisive) + " could not be extracted the "
            "way the recorded corpus was, and would raise the ceiling if included, so leaving "
            "them out would be the thing that decided it.\n  " + "\n  ".join(mismatched))
    return {"per_paper": out,
            "in_the_ceiling": sorted(good),
            "left_out_of_the_ceiling": sorted(set(out) - set(good)),
            "why_left_out": mismatched,
            "leaving_them_out_cannot_raise_the_ceiling": True,
            "recorded_words": {p: probe[p]["words"] for p in probe},
            "how_obtained": recorded["corpus"]["how_obtained"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-corpus", action="store_true",
                    help="refetch the eight comparison papers and measure them for this probe")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    from _provenance import stamp

    src = BODY.read_text()
    import prose_metrics as pm

    whole = measure(pm.strip_latex(src))
    sections = by_section(src)

    report = {"provenance": stamp(__file__),
              "what_this_is": (
                  "the share of prose sentences carrying a denial and the rate per thousand "
                  "words, per section, with the sentences carrying two or more counted apart "
                  "because they are what a rewriting pass is aimed at"),
              "narrow_set": NARROW, "broad_set": BROAD,
              "whole": whole, "by_section": sections}

    prev = json.loads(Path(args.out).read_text()) if Path(args.out).exists() else {}
    if args.build_corpus:
        report["corpus"] = _fetch_corpus()
    elif prev.get("corpus"):
        # Kept rather than dropped: refetching on every run would make the ceiling depend on a
        # network, and silently dropping it would make the gate below vacuous.
        report["corpus"] = prev["corpus"]

    corpus = report.get("corpus", {}).get("per_paper")
    if corpus:
        keep = report["corpus"].get("in_the_ceiling") or sorted(corpus)
        used = {p: corpus[p] for p in keep}
        shares = [v["share_of_sentences"] for v in used.values()]
        rates = [v["per_1000_words"] for v in used.values()]
        report["ceiling"] = {
            "share_of_sentences": round(max(shares), 4),
            "per_1000_words": round(max(rates), 2),
            "basis": (f"the highest of {len(used)} of the {len(corpus)} comparison papers, each "
                      f"measured by this file over the records the other prose gates are built "
                      f"on; the rest could not be extracted the same way and are named in the "
                      f"corpus block, where it is also recorded that including them could not "
                      f"have raised either figure"),
            "per_paper_share": {p: v["share_of_sentences"] for p, v in sorted(corpus.items())},
            "per_paper_rate": {p: v["per_1000_words"] for p, v in sorted(corpus.items())},
        }

    Path(args.out).write_text(json.dumps(report, indent=1))

    head = f"{'section':28s}{'words':>7s}{'sent':>6s}{'med':>5s}{'>=35':>6s}{'any':>7s}{'2+':>5s}{'/1k':>7s}"
    print(head)
    for name, m in sections.items():
        print(f"{name[:28]:28s}{m['words']:7d}{m['sentences']:6d}{m['median_sentence_words']:5d}"
              f"{m['sentences_at_least_35_words']:6d}{m['share_of_sentences']:7.0%}"
              f"{m['sentences_with_two_or_more']:5d}{m['per_1000_words']:7.1f}")
    m = whole
    print(f"{'whole manuscript':28s}{m['words']:7d}{m['sentences']:6d}"
          f"{m['median_sentence_words']:5d}{m['sentences_at_least_35_words']:6d}"
          f"{m['share_of_sentences']:7.0%}{m['sentences_with_two_or_more']:5d}"
          f"{m['per_1000_words']:7.1f}")
    if report.get("ceiling"):
        c = report["ceiling"]
        print(f"\nceiling from the comparison papers: {c['share_of_sentences']:.0%} of sentences, "
              f"{c['per_1000_words']:.1f} per thousand words")
    else:
        print("\nno ceiling: run once with --build-corpus to measure the comparison papers")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
