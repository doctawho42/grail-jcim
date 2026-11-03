"""The manuscript's figures, drawn from the artifacts that measured them.

A figure typed from a table falls behind the table, and a table typed from an artifact falls
behind the artifact; both happened in the first draft of this paper. These are regenerated from
results/ on every build, so a figure cannot outlive the run it describes.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

# The short names the comparison table prints in its header, imported rather than restated:
# the figure and the table must name one system once. A second copy of an arm list is the
# defect this project has now found in eleven files.
from paper2_tables import LABEL as SWEEP_SHORT  # noqa: E402
# The criteria the manuscript's grid draws, from the one place that defines them.
from _acs_table import DEFENSIBLE, HEADLINE, control_artifact  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "paper2"

# One categorical palette for every figure. It is not chosen by eye: the order below is the one
# that passes all five checks of the validator shipped with the dataviz guidance -- lightness
# band, chroma floor, adjacent-pair separation under simulated colour-vision deficiency, the
# normal-vision floor, and contrast against a light surface. Two orders that looked reasonable
# failed it: the ColorBrewer-style red/green pair separates by DeltaE 2.5 under deuteranopia, and
# swapping slots 2 and 4 puts vermillion beside amber at DeltaE 0.9. Legends therefore follow
# this order rather than any other.
#
# Adjacent luminances are as close as 0.01, so the palette is NOT sufficient in greyscale. Every
# figure carries a second encoding -- distinct markers, line styles and direct labels -- so
# identity is never colour alone, which is also what the guidance requires for a warning-band
# pair.
# Okabe-Ito, colour-blind safe. The seventh entry arrived with the fifth comparator; a
# modulo into a six-colour list had given it the first arm's blue.
PALETTE = ["#0072B2", "#D55E00", "#009E73", "#B07A00", "#AD5A87", "#56514C", "#7A5C3E",
           # An eighth, for GLORYxR's two settings, which share it. Chosen away from the mauve at
           # index 4 and the blue at index 0, the two it could be confused with.
           "#5B3FA8"]

# Polarity, for the outcome bands of the sweep. These are regions rather than entities, so
# they must not wear a series hue: the first draft shaded "GRAIL leads" in the same blue as
# the GRAIL exhaustive line, which makes one colour mean two things in one figure. Used at a
# low alpha behind the marks and always with a text label, never as the only signal.
BAND_TRAILS, BAND_LEADS = "#8c6bb1", "#41ab5d"

# Ink, replacing the seven different greys these figures used to mix. Text and rules wear ink;
# only marks wear a series colour.
INK, INK_MUTED, INK_FAINT = "#1a1a1a", "#666666", "#c9c9c9"

plt.rcParams.update({
    # ACS asks for Helvetica or Arial in figure lettering, at no less than 4.5 pt final size and
    # with no rule thinner than 0.5 pt
    # Type 3 is matplotlib's default for PDF text and ACS production returns it: the glyphs are
    # embedded as drawing programs with no ToUnicode map, so a figure label is neither searchable
    # nor extractable. 42 is TrueType, which embeds a real font with a character map.
    # PDF keeps Type 42, which embeds Helvetica correctly: pdffonts reports
    # "EDQXKT+Helvetica CID TrueType ... emb yes sub yes". EPS cannot. Helvetica resolves on this
    # machine to /System/Library/Fonts/Helvetica.ttc, a font COLLECTION, and matplotlib's Type 42
    # writer cannot name a face inside one: every EPS declared "/FontName /unknown def" while
    # every text run asked for "/Helvetica". A RIP given that substitutes. Type 3 embeds the
    # glyph procedures and names them /Helvetica, which is what ACS means by fonts embedded or
    # converted to outlines. Measured on a two-line probe: type 3 gives "/FontName /Helvetica",
    # type 42 gives "/FontName /unknown", with the same selectfont calls in both.
    "pdf.fonttype": 42, "ps.fonttype": 3,
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    # Matplotlib renders anything between dollar signs with its own math font, whose default is
    # DejaVu, so a figure whose lettering is Helvetica still shipped DejaVu for "$k$" and for
    # every sign in the criterion legend. Two typefaces in one figure is a house-style failure
    # and the second one is not the face ACS asks for. Binding the math faces to the text family
    # keeps a budget axis and its label in one typeface.
    "mathtext.fontset": "custom",
    "mathtext.rm": "Helvetica", "mathtext.it": "Helvetica:italic",
    "mathtext.bf": "Helvetica:bold", "mathtext.sf": "Helvetica",
    "mathtext.default": "it",
    "font.size": 8, "axes.linewidth": 0.6, "xtick.major.width": 0.6,
    "ytick.major.width": 0.6, "legend.frameon": False, "savefig.bbox": "tight",
    "savefig.dpi": 600, "figure.dpi": 600,
    "axes.spines.top": False, "axes.spines.right": False,
    "text.color": INK, "axes.labelcolor": INK, "axes.edgecolor": INK_MUTED,
    "xtick.color": INK_MUTED, "ytick.color": INK_MUTED,
})

# ACS: a single-column graphic is at most 240 pt (3.33 in) and a double-column one between 300
# and 504 pt (4.167 and 7 in). W was 3.35 in, which is 241 pt and over the single-column limit.
W = 3.33

# ACS asks for 300 dpi on colour artwork and 1200 on line art. The figures are vector except for
# the rendered structures, which are the one raster element; saving at 600 puts those comfortably
# past the colour bar without making the files unwieldy.
FIG_DPI = 600


def save(fig, stem):
    """The build's PDF and the format ACS accepts.

    ACS takes TIF, JPG, PNG and EPS and does not take PDF, so a submission built only from the
    file pdflatex needs has nothing to upload. These figures are vector apart from the rendered
    structures, so EPS is the format that keeps them vector; the PDF stays because the manuscript
    is compiled with pdflatex.
    """
    fig.savefig(OUT / f"{stem}.pdf")
    fig.savefig(OUT / f"{stem}.eps")


def art(name):
    return json.loads((ROOT / "results" / name).read_text())


# Hoisted out of fig_sweep so the band-labelling helper and its gate read the same map the plot
# draws from. Two copies of this map is exactly how a comparator went missing once.
SWEEP_STYLE = {"whole bank": ("GRAIL exhaustive", "-", "o", PALETTE[0]),
               "trained budget": ("GRAIL interactive", "-", "s", PALETTE[1]),
               "metatox": ("MetaTox", "--", "^", PALETTE[2]),
               "sygma": ("SyGMa", "--", "v", PALETTE[3]),
               "metapredictor": ("MetaPredictor", "--", "D", PALETTE[4]),
               "biotransformer": ("BioTransformer", "--", "*", PALETTE[5]),
               "gloryx": ("GLORYx", "--", "P", PALETTE[6]),
               # GLORYxR's two site-of-metabolism settings share one hue and differ in dash and
               # marker, because they are one system under one declared knob and not two systems.
               # Giving them separate hues would say the opposite, and the palette is out of hues
               # that stay apart in print at this size anyway.
               "gloryxr_default": ("GLORYxR, default SoM", "--", "X", PALETTE[7]),
               "gloryxr_strict": ("GLORYxR, strict SoM", ":", "<", PALETTE[7])}

# Derived from the style map, not restated beside it. Written as a literal pair, a third
# GRAIL arm would be styled as a curve and silently counted as a COMPARATOR by everything
# that asks "is this ours", which is the arm-list defect one step further in.
GRAIL_ARMS = tuple(a for a, (lab, *_) in SWEEP_STYLE.items() if lab.startswith("GRAIL"))
if not GRAIL_ARMS:
    raise SystemExit("no arm in SWEEP_STYLE is labelled as ours; the sweep has no GRAIL arm")


def strongest_comparator_runs(rec):
    """Which comparator each shaded band is read against, as contiguous runs of budgets.

    The bands are computed against the strongest comparator *at that budget*, and that is not one
    method: four hold the position across this sweep and it changes hands three times. Two bands
    side by side can therefore be verdicts about two different systems, and until these labels
    the figure did not say so -- a reader had to take the row maximum of Table 2 by hand and hope
    the figure had taken the same one.
    """
    out = []
    for k in sorted((int(k) for k in rec), key=int):
        row = rec[str(k)]
        unstyled = [a for a in row if a not in SWEEP_STYLE]
        if unstyled:
            raise SystemExit(f"deployment_table.json carries arms this figure has no style for: "
                             f"{', '.join(unstyled)}")
        comp = [a for a in row if a not in GRAIL_ARMS]
        best = max(comp, key=lambda a: row[a])
        if out and out[-1]["arm"] == best:
            out[-1]["budgets"].append(k)
        else:
            # The short label the table's header uses, so the two documents name one system once.
            out.append({"arm": best, "label": SWEEP_SHORT[best], "budgets": [k]})
    return out


# The headline population. The sweep figure and the sweep table read the same artifact, and the
# comparison set is the slice the controls were computed on rather than the population the
# comparison is reported over.
SWEEP_ARTIFACT = control_artifact("deployment_table", HEADLINE)
# The matched-length control is read at the same population as the sweep it controls: a
# control computed on a quarter of the substrates says nothing about the other three quarters
# of the figure beside it.
MATCHED_ARTIFACT = control_artifact("matched_length", HEADLINE)
# The other three controls follow the same population for the same reason: a figure and
# the sentence beside it have to be measured on the same substrates.
CHEMISTRY_ARTIFACT = control_artifact("error_by_chemistry", HEADLINE)
PRECISION_ARTIFACT = control_artifact("precision_table", HEADLINE)
CRITERION_ARTIFACT = control_artifact("criterion_sweep", HEADLINE)


def fig_sweep():
    d = art(SWEEP_ARTIFACT)
    rec, con = d["recall_micro"], d["contrasts"]
    ks = sorted((int(k) for k in rec), key=int)
    style = SWEEP_STYLE
    runs = strongest_comparator_runs(rec)

    # Taller than the data needs, because the legend sits under the axes. At seven series it
    # fitted inside the lower right; at nine it covered the curves it was naming and the curves
    # ran through its text, and its opaque background also cut a hole in the "leads" band.
    fig, ax = plt.subplots(figsize=(W, 3.15))
    for arm, (lab, ls, mk, col) in style.items():
        if arm not in rec[str(ks[0])]:
            continue
        y = [rec[str(k)][arm] for k in ks]
        ax.plot(ks, y, ls, marker=mk, ms=3, lw=1.1, color=col, label=lab,
                zorder=3 if arm.startswith(("whole", "trained")) else 2)

    # the three regions, from the contrasts rather than from the eye
    ours = GRAIL_ARMS
    others = [a for a in style if a not in ours and a in rec[str(ks[0])]]
    band = []
    for k in ks:
        bo = max(others, key=lambda a: rec[str(k)][a])
        bu = max(ours, key=lambda a: rec[str(k)][a])
        c = con[str(k)][f"{bu} - {bo}"]
        band.append("lose" if (c["gap"] < 0 and c["excludes_zero"])
                    else "win" if (c["gap"] > 0 and c["excludes_zero"]) else "tie")
    # Geometric midpoints, because the axis is logarithmic. Arithmetic ones put a band's edge
    # where the eye does not expect it: with budgets at 20 and 30 the arithmetic midpoint 25 sits
    # past the visual centre, and a referee read the band as reaching a budget it does not cover.
    edges = []
    for i, k in enumerate(ks):
        lo = ks[i - 1] if i else ks[0] * 0.75
        hi = ks[i + 1] if i < len(ks) - 1 else ks[-1] * 1.1
        left, right = (lo * k) ** 0.5, (k * hi) ** 0.5
        edges.append((left, right))
        if band[i] == "lose":
            ax.axvspan(left, right, color=BAND_TRAILS, alpha=0.10, lw=0, zorder=0)
        elif band[i] == "win":
            ax.axvspan(left, right, color=BAND_LEADS, alpha=0.10, lw=0, zorder=0)
    ax.set_xscale("log")
    ax.set_xticks(ks)
    ax.set_xticklabels([str(k) for k in ks])
    ax.minorticks_off()
    ax.set_xlabel("output budget $k$")
    ax.set_ylabel("micro recall@$k$")
    # Along the top, the comparator each stretch of the shading is read against. The bands are
    # computed against the strongest comparator at each budget and that is four different systems
    # here, so without this the figure shows verdicts without saying whom they are about.
    # Each name sits over a rule spanning the budgets it holds. Without the rule the two names in
    # the unshaded middle, whose runs are two budgets each, read as one label with a gap in it.
    at = {k: i for i, k in enumerate(ks)}
    drawn = []
    for r in runs:
        lo = edges[at[r["budgets"][0]]][0]
        hi = edges[at[r["budgets"][-1]]][1]
        ax.plot([lo * 1.02, hi * 0.98], [0.742, 0.742], "-", lw=0.6, color=INK_FAINT,
                solid_capstyle="butt", zorder=4, clip_on=False)
        ax.text((lo * hi) ** 0.5, 0.749, r["label"], ha="center", va="bottom", fontsize=5.6,
                color=INK_MUTED)
        drawn.append(r["label"])
    # ... and the polarity, so it never rests on colour alone. It sits at the foot of the band
    # rather than the head because the comparator names now hold the head.
    for lab, want in (("trails", "lose"), ("leads", "win")):
        xs = [k for k, b in zip(ks, band) if b == want]
        if xs:
            ax.text((min(xs) * max(xs)) ** 0.5, 0.012, lab, ha="center", va="bottom",
                    fontsize=6.2, color=INK_MUTED)
    # The legend is ordered by where the curves finish, so its top-to-bottom order is the order
    # of the lines at the right-hand edge. Declaration order matched no budget on the plot and a
    # reader checking the legend against the curves found neither in the other.
    handles, labels = ax.get_legend_handles_labels()
    by_label = {lab: (arm, h) for (arm, (lab, *_)), h in
                zip([(a, style[a]) for a in style if a in rec[str(ks[0])]], handles)}
    order = sorted(labels, key=lambda lab: -rec[str(ks[-1])][by_label[lab][0]])
    ax.legend([by_label[lab][1] for lab in order], order,
              loc="upper center", bbox_to_anchor=(0.5, -0.19), ncol=3, frameon=False,
              fontsize=6.2, handlelength=1.8, columnspacing=1.2, handletextpad=0.5)
    ax.set_ylim(0, 0.79)
    # Nine budgets on a logarithmic axis crowd where they are closest together, at 8 and 10.
    ax.tick_params(axis="x", labelsize=6.0)
    save(fig, "fig_sweep")
    plt.close(fig)
    return {"band": band, "comparator_labels": drawn}


def fig_ceiling():
    cen = art("novel_type_census.json")
    usp = art("uspto_type_overlap.json")
    cov = art("coverage_gap_types.json")
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(W * 2.06, 2.2),
                                 gridspec_kw={"width_ratios": [1.15, 1]})

    # left: where the unreached known metabolites go, and what a library supplies
    g = cov["gap"]
    labels = ["type absent\nfrom the bank", "type present,\nrule did not fire", "not typeable"]
    vals = [g["novel_type"], g["known_type"], g["untypeable"]]
    cols = [PALETTE[1], PALETTE[3], INK_FAINT]
    left = 0
    handles = []
    for v, c, lab in zip(vals, cols, labels):
        b = a1.barh(0, v, left=left, color=c, height=0.5, edgecolor="white", lw=0.6)
        a1.text(left + v / 2, 0, str(v), ha="center", va="center", fontsize=7,
                color="white" if c != INK_FAINT else INK)
        handles.append((b, lab.replace("\n", " ")))
        left += v
    # The three segments carried no key. `labels` was written above and never drawn -- the loop
    # bound `lab` and dropped it -- so the panel showed three numbers in three colours and the
    # caption named none of them. Drawn above the bar rather than inside it, because the narrowest
    # segment is forty known metabolites wide and no label fits in it.
    a1.legend([h[0] for h in handles], [h[1] for h in handles], loc="lower left",
              bbox_to_anchor=(0.0, 1.02), ncol=3, frameon=False, fontsize=6.2,
              handlelength=1.1, handleheight=0.7, columnspacing=1.1, handletextpad=0.4)
    hit = usp["overlap"]["misses_those_types_carry"]
    a1.barh(-0.75, hit, color=PALETTE[0], height=0.5)
    a1.text(hit + 8, -0.75, f"{hit} recoverable from "
            f"{usp['uspto']['templates']:,} synthetic templates", va="center", fontsize=6.6)
    a1.set_yticks([0, -0.75])
    a1.set_yticklabels([f"{cov['uncovered_pairs']} unreached\nknown metabolites", "of which"], fontsize=6.8)
    a1.set_xlim(0, cov["uncovered_pairs"] * 1.02)
    a1.set_xlabel("known metabolites")
    a1.spines["left"].set_visible(False)
    a1.tick_params(axis="y", length=0)

    # right: the specification curve
    cur = cen["granularity_curve"]
    x = np.arange(len(cur))
    share = [c["share_of_mass_in_singletons"] for c in cur]
    usable = [c["determines_a_product"] for c in cur]
    # Colour alone carried this distinction, which is the one thing a figure must not ask of a
    # reader who cannot see the difference or is holding a greyscale print. The bars that
    # determine a product are hatched as well as coloured.
    for xi, (s, u) in enumerate(zip(share, usable)):
        a2.bar(xi, s, width=0.6, color=PALETTE[1] if u else INK_FAINT,
               hatch="//" if u else None, edgecolor="white" if u else "none", lw=0.0)
    # The four bars are one sequence and not four categories: the definition of a type widens from
    # left to right and the share falls with it. Two referees in a row read them as independent,
    # so the reading is drawn rather than left to the axis order.
    a2.plot(x, share, "-", color=INK_MUTED, lw=0.8, marker="o", ms=2.2, zorder=4)
    # The label above a bar is the bar's own value. It used to be the number of distinct types at
    # that granularity, which is a different quantity on a different scale sitting in the place
    # the eye reads the height from; the type count now rides under the tick where it names the
    # axis position rather than the height.
    for i, c in enumerate(cur):
        # The line that draws the four bars as one sequence passes through its own markers, and
        # at 0.09 and 0.03 the value label sat on top of it: the marker landed on the digits. The
        # label is lifted clear and carries an opaque patch, so the line runs behind it either way.
        a2.text(i, share[i] + 0.055, f"{share[i]:.2f}", ha="center", fontsize=6.5, zorder=5,
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none"))
    a2.set_xticks(x)
    a2.set_xticklabels([f"exact\nmultiset\n{cur[0]['types']} types",
                        f"counts\ndropped\n{cur[1]['types']} types",
                        f"element\npairs\n{cur[2]['types']} types",
                        f"bond\ncount\n{cur[3]['types']} types"],
                       fontsize=6.5)
    a2.set_ylabel("share of misses in singleton types")
    # Headroom for the two annotations. Lifting the value labels clear of the connecting line
    # pushed the tallest of them into "the type definition widens", so the annotations move into a
    # band of their own above the bars instead of sharing the top of the data area with them.
    a2.set_ylim(0, 1.15)
    a2.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    a2.axhline(0.5, color=INK_FAINT, lw=0.6, ls=":")
    # The line marked half and said so nowhere, in the figure or the caption.
    a2.text(3.45, 0.515, "half the misses", fontsize=5.8, ha="right", va="bottom",
            color=INK_FAINT)
    a2.text(-0.35, 1.14, "the type definition widens, left to right", fontsize=6.2, ha="left",
            va="top", color=INK_MUTED)
    # Back inside the panel, over the two short bars, where it fits on its own. The header band
    # is one line wide at this figure's width and the two annotations ran into each other there.
    a2.text(3.45, 0.95, "hatched: the type names\na transformation", fontsize=6.2, ha="right",
            va="top", color=PALETTE[1])
    a2.text(3.35, 0.16, "plain: it does not", fontsize=6.2, ha="right", color=INK_MUTED)
    save(fig, "fig_ceiling")
    plt.close(fig)


def fig_cost():
    env = art("cost_envelope.json")["rows"]
    mt = art("mode_timings.json")
    # Taller than the other two-panel figures and with the scatter given more of the width: at
    # the previous size the left panel's points were below the resolution a printed page gives a
    # scatter of this density, which is a legibility failure and not a taste one.
    # Placed across both columns rather than in one, so the scatter is read at about twice the
    # width it had. A two-panel figure at a single column's width put this one below the size a
    # printed page can resolve, which a referee reported as illegible.
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(W * 2.06, 2.35),
                                 gridspec_kw={"width_ratios": [1.45, 1]})
    fin = [r for r in env if r["finished"]]
    bad = [r for r in env if not r["finished"]]
    dl = art("cost_envelope.json")["deadline_s"]
    a1.axhline(dl, color=INK_FAINT, lw=0.6, ls="--", zorder=0)
    a1.scatter([r["heavy"] for r in fin], [r["t_generate"] for r in fin], s=13, alpha=0.75,
               color=PALETTE[0], lw=0, label="finished")
    a1.scatter([r["heavy"] for r in bad], [dl] * len(bad), s=26, marker="x",
               color=PALETTE[1], lw=1.0, label=f"did not finish in {int(dl)} s")
    a1.set_yscale("log")
    # Both axes are logarithmic. On a linear x the substrates run 4 to 291 heavy atoms with one
    # peptide at the top, so nine tenths of the points were squeezed into the left fifth of the
    # panel and the trend they carry could not be read at print size.
    a1.set_xscale("log")
    a1.set_xticks([5, 10, 20, 50, 100, 200])
    a1.set_xticklabels(["5", "10", "20", "50", "100", "200"])
    a1.minorticks_off()
    a1.set_xlabel("heavy atoms in the substrate")
    a1.set_ylabel("generator seconds")
    a1.legend(fontsize=6.4, loc="upper left")

    i, e = mt["interactive"], mt["exhaustive"]
    # the four interactive statistics stay together so the bracket under them is true; the
    # slowest substrate is interactive too, and sat outside that bracket in the first draft
    bars = [("median", i["median_s"], PALETTE[0]),
            ("mean", i["mean_s"], PALETTE[0]),
            ("90th pct", i["p90_s"], PALETTE[0]),
            ("slowest", i["max_s"], PALETTE[1]),
            ("median", e["median_s"], PALETTE[2])]
    a2.bar(range(len(bars)), [b[1] for b in bars], color=[b[2] for b in bars], width=0.62)
    for j, b in enumerate(bars):
        a2.text(j, b[1] * 1.18, f"{b[1]}", ha="center", fontsize=6.2)
    a2.set_yscale("log")
    a2.set_xticks(range(len(bars)))
    # Five ticks in a narrow panel collide at any size that keeps them readable, so they lean.
    a2.set_xticklabels([b[0] for b in bars], fontsize=6.2, rotation=25, ha="right",
                       rotation_mode="anchor")
    # the arm each bar belongs to, named once under the group rather than repeated on every tick
    a2.text(1.5, -0.30, "interactive", ha="center", va="top", fontsize=6.6, color=INK_MUTED,
            transform=a2.get_xaxis_transform())
    a2.text(4, -0.30, "exhaustive", ha="center", va="top", fontsize=6.6, color=INK_MUTED,
            transform=a2.get_xaxis_transform())
    a2.plot([-0.35, 3.35], [-0.26, -0.26], color=INK_FAINT, lw=0.6, clip_on=False,
            transform=a2.get_xaxis_transform())
    a2.plot([3.65, 4.35], [-0.26, -0.26], color=INK_FAINT, lw=0.6, clip_on=False,
            transform=a2.get_xaxis_transform())
    a2.set_ylabel("seconds per substrate")
    a2.set_ylim(0.2, 600)
    save(fig, "fig_cost")
    plt.close(fig)


# The worked example's four annotated metabolites. Colour encodes the SITE, not the metabolite:
# the three phosphorylations fire on the same two substrate atoms under three different rules,
# which is the point the panel has to make, so giving each its own colour would hide it.
DEAMINATION, PHOSPHORYLATION = PALETTE[1], PALETTE[0]
CASE = [("FIRDBEQIJQERSE-UHFFFAOYSA-N", "dFdU", DEAMINATION),
        ("KNTREFQOVSMROS-UHFFFAOYSA-N", "dFdCMP", PHOSPHORYLATION),
        ("FRQISCZGNNXEMD-UHFFFAOYSA-N", "dFdCDP", PHOSPHORYLATION),
        ("YMOXEIOKAJSRQX-UHFFFAOYSA-N", "dFdCTP", PHOSPHORYLATION)]


def _rgb(h, tint=0.0):
    """The colour, optionally blended toward white.

    MolDraw2DCairo ignores a fourth alpha channel in this RDKit, so a pale highlight has to be a
    pale colour: the atom labels are drawn over the fill and must stay legible through it.
    """
    c = tuple(int(h[k:k + 2], 16) / 255 for k in (1, 3, 5))
    return tuple(v + (1.0 - v) * tint for v in c)


def _substrate_png(smiles, site_groups, width=2600, height=1500, placed_inches=1.757):
    """The substrate with each firing site shaded in its colour.

    Drawn from the atom indices the pipeline reported, not from a hand-marked depiction: the
    panel's claim is that the localisation is a computed field of the prediction.

    On resolution. Cairo rasterises, and matplotlib then resamples whatever it is given to the
    figure's own dpi. The first version rendered 900 by 520 and saved at matplotlib's default
    100 dpi, so what actually reached the PDF was a 211 by 122 bitmap at 100 ppi -- a third of
    the 300 dpi ACS asks for colour artwork, and visibly soft at print size. The render is now
    large enough that the figure's dpi, not the source, is the binding constraint, and the figure
    is saved at FIG_DPI.
    """
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    from rdkit.Chem.Draw import rdMolDraw2D

    mol = Chem.MolFromSmiles(smiles)
    highlight, colours = [], {}
    for atoms, rgb in site_groups:
        for a in atoms:
            if a < mol.GetNumAtoms():
                highlight.append(a)
                colours[a] = rgb
    d = rdMolDraw2D.MolDraw2DCairo(width, height)
    o = d.drawOptions()
    # Sized from the PRINTED size, not from the canvas. The old rule scaled with the render
    # (2 and 24 px per 900 px of canvas) and was a proportion of something the reader never sees:
    # at 2600 px placed 1.757 in wide, which is what pdfimages reports for this panel, it put the
    # bonds at 0.29 pt and the atom labels at 3.36 pt. ACS asks for no line thinner than 0.5 pt
    # and no lettering smaller than 4.5 pt IN THE FINAL PUBLISHED FORMAT, so the minima are
    # converted into pixels here and carry a little margin. A pixel is placed_inches/width inches,
    # so re-placing the panel at a different width changes these with it instead of silently
    # dropping the structure back under the floor.
    px_per_pt = width / (placed_inches * 72.0)
    o.bondLineWidth = max(2, math.ceil(0.6 * px_per_pt))
    o.highlightRadius = 0.36
    o.fixedFontSize = max(24, math.ceil(5.0 * px_per_pt))
    o.clearBackground = False
    rdMolDraw2D.PrepareAndDrawMolecule(d, mol, highlightAtoms=highlight,
                                       highlightAtomColors=colours)
    d.FinishDrawing()
    return d.GetDrawingText()


def fig_case():
    """The worked example: where the rules fire, and where the two arms put the four answers."""
    import io

    import matplotlib.image as mpimg
    from matplotlib.patches import Circle

    inter, exh = art("case_study.json"), art("case_study_exhaustive.json")
    inter_d, exh_d = art("case_study_drawn.json"), art("case_study_exhaustive_drawn.json")
    hits = {arm: {c["key"]: c for c in d["candidates"] if c["is_reference"]}
            for arm, d in (("i", inter), ("e", exh), ("id", inter_d), ("ed", exh_d))}

    # The structure drawn is the one a chemist draws, which is not the one the corpus stores.
    # An earlier version of this figure took the substrate from the stored artifact and so
    # printed a named drug as its minor 4-imino-2-hydroxy tautomer, with its single interactive
    # hit attributed to a template that cannot fire on the correct structure. The shading comes
    # from the run on that same drawing, so the atoms and the molecule are one molecule.
    sites = {DEAMINATION: set(), PHOSPHORYLATION: set()}
    for key, _, col in CASE:
        c = hits["ed"].get(key)
        if c:
            sites[col] |= set(c["firing_atoms"])
    n_phos_rules = len({hits["ed"][k]["rule_id"] for k, _, col in CASE
                        if col == PHOSPHORYLATION and k in hits["ed"]})

    # The right panel's row labels are three lines long and are drawn to the left of its axes,
    # so the gap between the two panels has to hold them: at the default spacing the structure
    # ran underneath them.
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(W * 2.12, 3.9),
                                 gridspec_kw={"width_ratios": [0.92, 1.45], "wspace": 0.42})
    png = _substrate_png(exh_d["substrate"],
                         [(sorted(atoms), _rgb(col, 0.68)) for col, atoms in sites.items()])
    a1.imshow(mpimg.imread(io.BytesIO(png), format="png"), interpolation="antialiased")
    a1.set_axis_off()
    a1.set_title("substrate as a chemist draws it,\nshaded by the atoms the rules fired on",
                 fontsize=7.5, pad=4)
    for i, (col, text) in enumerate((
            (DEAMINATION, "deamination, 1 rule"),
            (PHOSPHORYLATION, f"phosphorylation, {n_phos_rules} rules"))):
        a1.add_patch(Circle((0.055, -0.055 - 0.075 * i), 0.018, transform=a1.transAxes,
                            color=col, clip_on=False))
        a1.text(0.095, -0.055 - 0.075 * i, text, transform=a1.transAxes, fontsize=7,
                va="center", color=INK)

    # The ranks, for both arms under both drawings of the substrate. The paper treats the
    # drawing as a declared axis, and this is the axis at one molecule: the same system, the
    # same annotation, two tautomers of one drug, different answers.
    rows = [("exhaustive", exh_d, 3.0, "up"), ("exhaustive", exh, 2.0, "down"),
            ("interactive", inter_d, 1.0, "up"), ("interactive", inter, 0.0, "down")]
    for _, d, y, _ in rows:
        if d["n_candidates"]:
            a2.plot([c["rank"] for c in d["candidates"]], [y] * d["n_candidates"], "|",
                    color=INK_FAINT, ms=8, mew=0.8, zorder=2)
    # Labels point away from the pair they belong to and are lifted onto whichever height is
    # free. Alternating two heights by position was not enough: on the stored exhaustive row the
    # hits at ranks 16 and 20 landed on the same height and their two-line labels overprinted.
    # A level is taken only if the last label on it is far enough away along the axis, measured
    # in the axis's own log-ish coordinate rather than in ranks, since the scale is symlog.
    # Two heights, and a sideways nudge when both are taken. Alternating two heights by position
    # was not enough on its own: on the stored exhaustive row the hits at ranks 16, 18 and 20
    # overprinted each other. A third height is not the answer either, because the rows are one
    # data unit apart and a label lifted that far reads as belonging to the row below.
    LEVELS = (9, 23)
    MIN_SEPARATION = 0.115
    NUDGE = 20

    def axis_position(rank):
        return math.log10(max(rank, 1)) if rank <= 30 else 1.48 + (rank - 30) / 140.0

    for _, d, y, side in rows:
        found = sorted((c for c in d["candidates"] if c["is_reference"]),
                       key=lambda c: c["rank"])
        occupied, nudged = [None] * len(LEVELS), 0
        for c in found:
            col = next(x for k, _, x in CASE if k == c["key"])
            name = next(x for k, x, _ in CASE if k == c["key"])
            a2.plot([c["rank"]], [y], "o", ms=5.0, color=col, mec="white", mew=0.9, zorder=4)
            here = axis_position(c["rank"])
            free = [i for i, last in enumerate(occupied)
                    if last is None or here - last >= MIN_SEPARATION]
            level = free[0] if free else len(LEVELS) - 1
            dx = 0
            if not free:
                nudged += 1
                dx = NUDGE if nudged % 2 else -NUDGE
            occupied[level] = here
            off = LEVELS[level] if side == "up" else -LEVELS[level]
            # The text is opaque and sits above every line in the panel. Without that, two
            # lines ran THROUGH a label: the k=15 guide, which is drawn at zorder 0 but shows
            # through the gaps in the glyphs, and a neighbour's leader, which has to cross the
            # inner label band to reach the outer one. On the stored exhaustive row both crossed
            # "dFdCTP rule 1745" -- the leader struck the P and the 5 -- and a strike-through in
            # a second colour reads as a correction mark rather than as a connector.
            # The leader and the label are TWO artists, and that is the whole of the fix. An
            # annotation draws its text and its arrow together under one zorder, and the arrow is
            # drawn inside the annotation rather than as a child of the axes, so raising the text
            # or lowering ann.arrow_patch moves neither past the other -- both were tried. On the
            # stored exhaustive row dFdU sits at the outer level and dFdCTP at the inner one, so
            # dFdU's leader has to cross dFdCTP's text; it struck the P and the 5 in a second
            # colour, which reads as a correction mark and not as a connector. Nudging cannot
            # help: the leader must reach its point and the point is beyond the inner band. Drawn
            # apart, every leader is under every label and the labels are opaque.
            if level or dx:
                a2.annotate("", (c["rank"], y), textcoords="offset points", xytext=(dx, off),
                            arrowprops=dict(arrowstyle="-", lw=0.5, color=col,
                                            shrinkA=1, shrinkB=3), zorder=3)
            a2.annotate(f"{name}\nrule {c['rule_id']}", (c["rank"], y),
                        textcoords="offset points", xytext=(dx, off),
                        ha="center", va="bottom" if side == "up" else "top",
                        fontsize=6.0, color=col, linespacing=1.15, zorder=6,
                        bbox=dict(boxstyle="round,pad=0.08", fc="white", ec="none"))
    for k in (15, 30):
        a2.axvline(k, color=INK_FAINT, lw=0.7, ls=":", zorder=0)
        a2.annotate(f"$k={k}$", (k, -1.02), ha="center", fontsize=6.5, color=INK_MUTED)

    def _label(name, d, drawing):
        found = len(d["reference_ranks"])
        return (f"{name}, {drawing}\n{d['n_candidates']} returned, "
                f"{found} of {d['n_references']} found")

    a2.set_yticks([0, 1, 2, 3])
    a2.set_yticklabels([_label("interactive", inter, "as stored"),
                        _label("interactive", inter_d, "as drawn"),
                        _label("exhaustive", exh, "as stored"),
                        _label("exhaustive", exh_d, "as drawn")], fontsize=6.4)
    a2.set_xlabel("rank in the returned list")
    a2.set_xlim(0.3, max(exh["n_candidates"], 32) + 4)
    a2.set_ylim(-1.25, 3.75)
    a2.set_xscale("symlog", linthresh=30, linscale=1.6)
    a2.set_xticks([1, 5, 10, 15, 20, 30, 50, 100])
    a2.set_xticklabels(["1", "5", "10", "15", "20", "30", "50", "100"])
    a2.spines["left"].set_visible(False)
    a2.tick_params(axis="y", length=0)
    a2.set_title("where the four annotated metabolites land,\nunder each drawing of the substrate",
                 fontsize=7.5, pad=8)
    save(fig, "fig_case")
    plt.close(fig)


def fig_criterion(order=None, stem="fig_criterion"):
    """The verdict grid the manuscript used to print as a table of signs.

    Drawn over the criteria the paper defends unless a caller asks for others. A reviewer
    objected that a multiverse built partly on criteria known to be unreasonable inflates an
    instability it then reports; across all five the verdict moves at six of the nine budgets and
    across these three at one, so the grid the manuscript shows is this one and the supplement
    keeps all five.

    Table and figure carried the same nine by five grid, and the table read as arithmetic while
    the picture reads as a shape: two rows that never leave the trailing colour whatever the
    budget, three that cross once the list is long enough, and one column where the arm being
    compared is not even the same under all five criteria. That shape is the paper's claim.

    Everything here comes from the artifact's own verdicts rather than from a second reading of
    the recall values, so the figure cannot disagree with the sweep it draws.
    """
    d = art(CRITERION_ARTIFACT)
    order = list(order) if order is not None else [c for c in d["criteria"] if c in DEFENSIBLE]
    label = {"canonical": "canonical SMILES equality", "inchikey": "the full InChIKey",
             "inchi_no_stereo": "InChIKey, no stereo", "tanimoto1": "Tanimoto $=1$",
             "inchikey_tautomer": "tautomer-aware key (default)"}
    missing = [c for c in order if c not in d["by_criterion"]]
    if missing:
        raise SystemExit(f"{CRITERION_ARTIFACT} does not carry criteria this figure draws: "
                         f"{missing}")
    unnamed = [c for c in d["by_criterion"] if c not in label]
    if unnamed:
        raise SystemExit(f"{CRITERION_ARTIFACT} carries criteria this figure has no label for, "
                         f"so one could be dropped from the paper in silence: {unnamed}")

    budgets = sorted((int(k) for k in d["by_criterion"][order[0]]["verdict_by_budget"]), key=int)
    CODE = {"trails": -1, "neither": 0, "leads": 1}
    SIGN = {-1: "\u2013", 0: "\u00b7", 1: "+"}
    # One letter per comparator, and a name the figure cannot draw is a refusal rather than a
    # blank cell: the grid is read against a different comparator in almost every column.
    LETTER = {"MetaTox": "M", "SyGMa": "S", "MetaPredictor": "P", "GLORYx": "G",
              "BioTransformer": "B",
              # Two characters, because GLORYxR contributes two columns and a single letter would
              # collapse the setting the cell was read against -- which is the knob this paper
              # asks other papers to declare.
              "GLORYxR default SoM": "Rd", "GLORYxR strict SoM": "Rs"}

    grid, marks = [], []
    for crit in order:
        v = d["by_criterion"][crit]["verdict_by_budget"]
        m = d["by_criterion"][crit]["margin_by_budget"]
        bad = {x for x in v.values()} - set(CODE)
        if bad:
            raise SystemExit(f"{CRITERION_ARTIFACT} records verdicts this figure cannot draw: "
                             f"{sorted(bad)}")
        unknown = {m[str(b)]["theirs"] for b in budgets} - set(LETTER)
        if unknown:
            raise SystemExit(f"{CRITERION_ARTIFACT} names comparators this figure has no letter "
                             f"for: {sorted(unknown)}")
        grid.append([CODE[v[str(b)]] for b in budgets])
        marks.append([LETTER[m[str(b)]["theirs"]] for b in budgets])

    # The arm under comparison, taken per budget across the five criteria. Where they disagree the
    # cell says so rather than picking one, because a sign read against a different arm is a
    # different comparison.
    arms = []
    for b in budgets:
        ours = {d["by_criterion"][c]["margin_by_budget"][str(b)]["ours"] for c in order}
        arms.append("exh." if ours == {"GRAIL exhaustive"}
                    else "int." if ours == {"GRAIL interactive"} else "\u2013")

    import numpy as np
    from matplotlib.colors import ListedColormap

    fig, ax = plt.subplots(figsize=(W * 2.06, 2.35))
    cmap = ListedColormap(["#C7DCEA", "#F2F2F0", "#EBCDB4"])
    ax.imshow(np.array(grid), cmap=cmap, vmin=-1, vmax=1, aspect="auto")
    for r, row in enumerate(grid):
        for c, v in enumerate(row):
            ax.text(c - 0.10, r, SIGN[v], ha="center", va="center", fontsize=8, color=INK)
            ax.text(c + 0.17, r - 0.20, marks[r][c], ha="center", va="center",
                    fontsize=5.6, color=INK_MUTED)
    ax.set_xticks(range(len(budgets)))
    ax.set_xticklabels([str(b) for b in budgets], fontsize=7)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([label[c] for c in order], fontsize=7)
    ax.set_xlabel("candidates a system may return, $k$", fontsize=7, labelpad=2.0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0, pad=2.0)

    # The arm row sits under the grid rather than inside it: it is not a verdict.
    for c, a in enumerate(arms):
        ax.text(c, len(order) - 0.30, a, ha="center", va="top", fontsize=6.4, color=INK_MUTED,
                transform=ax.transData)
    ax.text(-0.6, len(order) - 0.30, "GRAIL arm", ha="right", va="top", fontsize=6.4,
            color=INK_MUTED)
    ax.set_ylim(len(order) - 0.05, -1.45)

    # The key sits above the grid: below it there is the arm row, the tick labels and the axis
    # label already, and a key placed there printed across the axis label.
    key = [("#C7DCEA", "GRAIL trails"), ("#F2F2F0", "neither separates"), ("#EBCDB4", "GRAIL leads")]
    for i, (col, lab) in enumerate(key):
        ax.add_patch(plt.Rectangle((0.9 + i * 2.6, -1.32), 0.30, 0.26,
                                   facecolor=col, edgecolor="none", clip_on=False))
        ax.text(1.32 + i * 2.6, -1.19, lab, ha="left", va="center",
                fontsize=6.4, color=INK_MUTED, clip_on=False)
    save(fig, stem)
    plt.close(fig)
    return {"budgets": budgets, "arms": arms, "criteria": order, "grid": grid,
            "leads": {c: g.count(1) for c, g in zip(order, grid)}}


# The two displays that replaced a grid of prose. Both take their roster from the artifact and
# refuse a name they cannot place, because a figure that silently omits a comparator is how the
# arm-list defect arrives one more time.
OURS = ("whole bank", "trained budget")
DRAWING_SUFFIX = " on the standardised drawing"


def _style_for(name):
    """The style entry for an artifact's own name for a system, or a refusal naming it.

    The artifacts spell the arms three ways -- the sweep's keys, the chemistry table's display
    names, and the comparator slugs -- and SWEEP_STYLE is keyed on the first. Resolving through
    the labels as well keeps one roster rather than three.
    """
    if name in SWEEP_STYLE:
        return SWEEP_STYLE[name]
    for key, entry in SWEEP_STYLE.items():
        if entry[0] == name:
            return entry
    return None


def fig_matched():
    """The controls on the wide-budget leads, which the Results used to enumerate in prose.

    One row per comparator, the budget taken from the comparator rather than from the experiment,
    and the gap read against zero. What the picture shows and a sentence cannot is that one row
    clears zero and the rest sit across it, two of them on the far side: the sweep at the widest
    budgets measures how much each system emits wherever the interval covers zero.

    SyGMa carries a third mark, the same comparator re-run on the drawing our standardiser
    produces. It belongs on SyGMa's row and not in the roster: it is one system under a declared
    presentation of the substrate, and listing it separately would say this work was compared
    against one more method than it was.
    """
    d = art(MATCHED_ARTIFACT)
    contrasts = d["contrasts"]
    rows, cells = [], {}
    for key, cell in contrasts.items():
        arm, _, comp = key.partition(" - ")
        if arm not in OURS:
            continue
        cells[key] = {"gap": cell["gap"], "ci95": cell["ci95"],
                      "excludes_zero": cell["excludes_zero"], "mean_slots": cell["mean_slots"]}
        if comp.endswith(DRAWING_SUFFIX):
            base = comp[:-len(DRAWING_SUFFIX)]
            if base not in [c for c in rows]:
                raise SystemExit(f"{MATCHED_ARTIFACT} carries {key} and the figure has no row "
                                 f"for {base} to put it on")
            continue
        if comp not in rows:
            rows.append(comp)
    unplaceable = [c for c in rows if _style_for(c) is None]
    if unplaceable:
        raise SystemExit(f"{MATCHED_ARTIFACT} names comparators this figure has no style for: "
                         f"{unplaceable}")

    # One line per contrast the figure shows, and the re-drawn comparator gets a line of its own
    # UNDER the comparator it is a re-drawing of, rather than a third and fourth mark stacked on
    # that comparator's line. Stacked, the lower two marks sat nearer the next comparator's label
    # than their own and read as its verdict. The line is muted and indented, and `rows` above is
    # still seven, so the roster does not gain a system.
    lines = []
    for comp in rows:
        lines.append((comp, comp, False))
        if any(f"{a} - {comp}{DRAWING_SUFFIX}" in cells for a in OURS):
            lines.append((f"{comp}{DRAWING_SUFFIX}", comp, True))

    fig, ax = plt.subplots(figsize=(W * 2.06, 2.95))
    ax.axvline(0.0, color=INK, lw=0.8, zorder=1)
    # The arms differ in marker and in fill, so the reading survives greyscale: a filled mark is
    # an interval clear of zero and a hollow one is an interval across it.
    ARM = {"whole bank": ("exhaustive", "o", -0.14), "trained budget": ("interactive", "s", 0.14)}
    for r, (key_comp, _, muted) in enumerate(lines):
        for arm, (armlab, marker, dy) in ARM.items():
            c = cells.get(f"{arm} - {key_comp}")
            if c is None:
                continue
            y = r + dy
            lo, hi = c["ci95"]
            colour = INK_MUTED if muted else _style_for(arm)[3]
            ax.plot([lo, hi], [y, y], color=colour, lw=1.1, solid_capstyle="butt", zorder=2)
            ax.plot([c["gap"]], [y], marker=marker, ms=4.2, zorder=3,
                    color=colour, mfc=colour if c["excludes_zero"] else "white",
                    mew=0.9, mec=colour)

    ax.set_yticks(range(len(lines)))
    ax.set_yticklabels(
        [("    the same, re-drawn" if muted else _style_for(key_comp)[0])
         for key_comp, _, muted in lines], fontsize=7)
    for lab, (_, _, muted) in zip(ax.get_yticklabels(), lines):
        if muted:
            lab.set_color(INK_MUTED)
            lab.set_fontsize(6.4)
    ax.set_ylim(len(lines) - 0.5, -0.7)
    ax.set_xlabel("recall of this work minus recall of the comparator, at the comparator's own "
                  "list length", fontsize=7, labelpad=2.0)
    ax.tick_params(labelsize=6.8, length=0, pad=2.0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    # The length the control gave each comparator, printed on its line: it is the quantity the
    # control is, and the prose used to carry seven of these numbers in one sentence. The column
    # is made by widening the axis rather than by drawing at the current right edge, which put
    # the text over the last interval and clipped it against the frame.
    lo, hi = ax.get_xlim()
    ax.set_xlim(lo, hi + (hi - lo) * 0.22)
    for r, (key_comp, _, muted) in enumerate(lines):
        c = cells.get(f"whole bank - {key_comp}") or cells.get(f"trained budget - {key_comp}")
        ax.text(ax.get_xlim()[1], r, f"{c['mean_slots']:.1f} slots", ha="right", va="center",
                fontsize=6.0, color=INK_MUTED)
    handles = [plt.Line2D([], [], color=_style_for(a)[3], marker=m, ms=4.2, lw=1.1,
                          label=f"GRAIL {lab}")
               for a, (lab, m, _) in ARM.items()]
    # Only where a re-drawn comparator exists. On the whole evaluated test set it does not: the
    # re-run on the standardiser's drawing was obtained for the submitted substrates alone, so a
    # legend entry here would name a series the figure does not draw.
    if any(muted for *_, muted in lines):
        handles.append(plt.Line2D([], [], color=INK_MUTED, marker="o", ms=4.2, lw=1.1,
                                  label="comparator re-drawn"))
    # Above the axes, in one row. Inside it, the only clear corner is the lower right, and that
    # is where the column of list lengths ends: the key printed over the last two of them.
    ax.legend(handles=handles, fontsize=6.2, loc="lower center", bbox_to_anchor=(0.5, 1.0),
              ncol=3, frameon=False, handlelength=1.6, columnspacing=1.4, borderaxespad=0.1)
    save(fig, "fig_matched")
    plt.close(fig)
    return {"comparators": rows, "cells": cells}


def fig_chemistry():
    """Recall within each transformation class, which the Results used to read off in prose.

    A headline recall figure aggregates over transformations of very different kinds, and the
    shape of the disagreement is the finding: this work takes the largest class and trails on
    several classical ones, and no system reaches far into the class the vocabulary does not name.
    Classes are ordered by how many known metabolites they carry, so the rows a reader should
    weigh are at the top.
    """
    d = art(CHEMISTRY_ARTIFACT)
    classes = d["classes"]
    budget = 15
    if budget not in d["budgets"]:
        raise SystemExit(f"{CHEMISTRY_ARTIFACT} does not carry a budget of {budget}: "
                         f"{d['budgets']}")
    order = [k for k, _ in sorted(classes.items(), key=lambda kv: (-kv[1]["references"], kv[0]))]
    systems, drawn = [], {}
    for cls in order:
        rec = classes[cls]["recall"]
        drawn[cls] = {s: rec[s][str(budget)] for s in rec}
        for s in rec:
            if s not in systems:
                systems.append(s)
    unplaceable = [s for s in systems if _style_for(s) is None]
    if unplaceable:
        raise SystemExit(f"{CHEMISTRY_ARTIFACT} names systems this figure has no style for: "
                         f"{unplaceable}")

    fig, ax = plt.subplots(figsize=(W * 2.06, 3.45))
    # A fixed vertical offset per system, so two systems that agree to the digit -- which happens
    # on the classical classes, where most of them do -- stay two marks rather than one.
    span = 0.28
    offset = {s: span * (i / (len(systems) - 1) - 0.5) for i, s in enumerate(systems)} \
        if len(systems) > 1 else {systems[0]: 0.0}
    for r, cls in enumerate(order):
        ax.axhline(r, color=INK_FAINT, lw=0.4, zorder=1)
        for s in systems:
            v = drawn[cls].get(s)
            if v is None:
                continue
            lab, _, marker, colour = _style_for(s)
            ours = lab.startswith("GRAIL")
            ax.plot([v], [r + offset[s]], marker=marker, ms=4.6 if ours else 3.4, zorder=3,
                    color=colour, mfc=colour if ours else "white", mew=0.8, mec=colour,
                    linestyle="none")
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([f"{c}  ({classes[c]['references']})" for c in order], fontsize=6.4)
    ax.set_ylim(len(order) - 0.4, -0.6)
    ax.set_xlim(-0.02, 1.02)
    ax.set_xlabel(f"micro recall within the class at a budget of {budget}, with the known "
                  f"metabolites each class carries in brackets", fontsize=7, labelpad=2.0)
    ax.tick_params(labelsize=6.8, length=0, pad=2.0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    handles = [plt.Line2D([], [], color=_style_for(s)[3], marker=_style_for(s)[2],
                          ms=4.6 if _style_for(s)[0].startswith("GRAIL") else 3.4, lw=0,
                          mfc=_style_for(s)[3] if _style_for(s)[0].startswith("GRAIL") else "white",
                          mec=_style_for(s)[3], label=_style_for(s)[0])
               for s in systems]
    ax.legend(handles=handles, fontsize=6.0, ncol=3, loc="lower center",
              bbox_to_anchor=(0.5, -0.30), frameon=False, handlelength=1.0, columnspacing=1.0)
    save(fig, "fig_chemistry")
    plt.close(fig)
    return {"classes": order, "systems": systems, "budget": budget, "recall": drawn}


def fig_toc():
    """The graphic for the table of contents: the thesis, not the system.

    The specification constrains this more than the figures do. It must give the essence "without
    providing specific results", and it must avoid artwork that already appears in the text. An
    earlier version drew one substrate and two of its metabolites, which is a picture of the
    instrument; under a title about what undeclared choices do to an ordering, the essence is the
    ordering itself changing. So this draws the verdict grid: the same pair of systems compared on
    the same substrates, read under five ways of deciding whether a prediction matches and nine
    budgets, with the sign of the verdict in each cell. No recall value is printed, which is what
    the specification asks, and no artwork from the text is reused, since Table~4 is a table.

    Hard requirements, from the ACS guidelines of 2024-02-28: at most 3.25 by 1.75 inches at the
    size submitted, sans-serif type at 8 pt and never below 6, and TIFF at 300 dpi or EPS with
    fonts embedded, so both are written.
    """
    # The specification, stated once and never used to build anything. The canvas below is sized
    # from it today, but the two must stay separate names: an assertion that compares the output
    # against the same constant that produced it can only catch a process failure, never a wrong
    # constant, and would pass unchanged if someone widened the canvas.
    ACS_MAX_W, ACS_MAX_H, ACS_MIN_DPI, ACS_MIN_PT = 3.25, 1.75, 300, 6.0
    TOC_W, TOC_H, DPI, MIN_PT = 3.25, 1.75, 600, 6.0
    # The guideline prefers 8 pt and forbids below 6. Nothing here now sits at the floor: the
    # smallest type is the key, and it is a full point above it.
    CELL_PT, AXIS_PT, TITLE_PT, KEY_PT = 7.5, 7.0, 8.0, 7.0
    FONTS_PT = (CELL_PT, AXIS_PT, TITLE_PT, KEY_PT)

    # The headline population, not the slice. This graphic stands for the paper, and it was
    # drawn from the comparison set while the comparison it illustrates moved to the whole
    # evaluated test set, so it showed a reshuffling on a quarter of the substrates the title's
    # claim is about.
    d = art(SWEEP_ARTIFACT)
    rec = d["recall_micro"]
    budgets = sorted((int(k) for k in rec), key=int)
    LABEL = {"whole bank": "GRAIL exh.", "trained budget": "GRAIL int.",
             "metatox": "MetaTox", "sygma": "SyGMa", "metapredictor": "MetaPred.",
             "biotransformer": "BioTrans.", "gloryx": "GLORYx",
             "gloryxr_default": "GLORYxR d.", "gloryxr_strict": "GLORYxR s."}
    COLOUR = {"whole bank": PALETTE[0], "trained budget": PALETTE[1], "metatox": PALETTE[2],
              "sygma": PALETTE[3], "metapredictor": PALETTE[4], "biotransformer": PALETTE[5],
              "gloryx": PALETTE[6], "gloryxr_default": PALETTE[7], "gloryxr_strict": PALETTE[7]}
    arms = sorted(rec[str(budgets[0])])
    unlabelled = [a for a in arms if a not in LABEL]
    if unlabelled:
        raise SystemExit(f"deployment_table.json carries arms this graphic has no name for: "
                         f"{', '.join(unlabelled)}")

    # Ranks, not recalls. The specification asks for the essence and not for specific results, and
    # a rank is the essence here: the paper's claim is that the ORDER is an artifact of a declared
    # choice, so the quantity that carries the claim is position and not level. No recall value is
    # printed anywhere in this graphic.
    rank = {a: [] for a in arms}
    for k in budgets:
        for i, a in enumerate(sorted(arms, key=lambda x: -rec[str(k)][x]), 1):
            rank[a].append(i)
    leaders = {a for a in arms if 1 in rank[a]}
    if len(leaders) < 2:
        raise SystemExit("one system holds rank 1 at every budget, so this graphic would assert a "
                         "reshuffling the sweep does not show; redraw it or drop it")

    fig, ax = plt.subplots(figsize=(TOC_W, TOC_H))
    ours = ("whole bank", "trained budget")
    for a in arms:
        # GLORYxR's two settings share a hue and differ in dash, as they do in Figure 1: one
        # system under one declared knob, not two systems.
        ax.plot(budgets, rank[a], marker="o", ms=2.0,
                lw=1.3 if a in ours else 0.8,
                color=COLOUR[a],
                ls=":" if a == "gloryxr_strict" else "-",
                zorder=3 if a in ours else 2)
        # the name at the end of its own line, so no key is needed and no line is unnamed
        ax.text(budgets[-1] * 1.09, rank[a][-1], LABEL[a], va="center", ha="left",
                fontsize=KEY_PT - 1.0, color=COLOUR[a] if a in ours else INK_MUTED)
    # Where the lead changes hands, marked on the line rather than described beside it.
    for i, k in enumerate(budgets):
        top = next(a for a in arms if rank[a][i] == 1)
        if i == 0 or top != next(a for a in arms if rank[a][i - 1] == 1):
            ax.plot([k], [1], marker="o", ms=4.2, mfc="none", mew=0.9,
                    color=COLOUR[top], zorder=4)
    ax.set_xscale("log")
    ax.set_xticks([1, 3, 5, 10, 20, 50])
    ax.set_xticklabels(["1", "3", "5", "10", "20", "50"], fontsize=AXIS_PT)
    ax.minorticks_off()
    ax.set_yticks([1, len(arms)])
    ax.set_yticklabels(["1st", f"{len(arms)}th"], fontsize=AXIS_PT)
    ax.set_ylim(len(arms) + 0.5, 0.4)
    ax.set_xlim(0.9, budgets[-1] * 1.06)
    ax.set_xlabel("candidates a system may return", fontsize=AXIS_PT, labelpad=1.5)
    ax.set_title(f"{len(leaders)} of {len(arms)} systems lead, on one set of substrates",
                 fontsize=TITLE_PT, pad=3.0, color=INK)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=2.0, width=0.5, pad=1.5)
    fig.subplots_adjust(left=0.10, right=0.72, top=0.86, bottom=0.20)

    with matplotlib.rc_context({"savefig.bbox": "standard", "savefig.pad_inches": 0.0}):
        # tif and eps are what ACS accepts for this graphic; the pdf exists only so pdflatex can
        # place it in the manuscript, since pdflatex reads neither of the other two
        for f, kw in (("fig_toc.tif", {"pil_kwargs": {"compression": "tiff_lzw"}}),
                      ("fig_toc.eps", {}), ("fig_toc.pdf", {})):
            fig.savefig(OUT / f, dpi=DPI, facecolor="white", **kw)
    plt.close(fig)

    # ACS asks for RGB; matplotlib writes RGBA, and an alpha channel in a submitted TIFF is a
    # production problem rather than an error anyone would see here
    from PIL import Image
    with Image.open(OUT / "fig_toc.tif") as im:
        if im.mode != "RGB":
            im.convert("RGB").save(OUT / "fig_toc.tif", compression="tiff_lzw",
                                   dpi=(DPI, DPI))

    # The specification is checked rather than trusted: a graphic over the limit is rejected at
    # submission, and nothing else here would notice.
    with Image.open(OUT / "fig_toc.tif") as im:
        w_in, h_in = im.size[0] / DPI, im.size[1] / DPI
        assert im.mode == "RGB", f"TOC graphic is {im.mode}, not RGB"
        assert w_in <= ACS_MAX_W + 1e-6 and h_in <= ACS_MAX_H + 1e-6, (
            f"TOC graphic is {w_in:.2f} by {h_in:.2f} in, over the ACS maximum of "
            f"{ACS_MAX_W} by {ACS_MAX_H}")
        assert im.info.get("dpi", (0, 0))[0] >= ACS_MIN_DPI, (
            f"TOC graphic is under {ACS_MIN_DPI} dpi")
    assert min(FONTS_PT) >= ACS_MIN_PT, (
        f"a TOC label is set at {min(FONTS_PT)} pt, under the ACS floor of {ACS_MIN_PT}")
    return w_in, h_in, DPI


def digest():
    """A hash of the numbers the figures draw.

    Two runs of matplotlib do not produce byte-identical PDFs, so a test cannot compare the files.
    It can compare what went into them, which is the property that matters: a figure is stale when
    its artifact has moved, not when its timestamp has.
    """
    import hashlib
    d = art("deployment_table.json")
    cen = art("novel_type_census.json")
    usp = art("uspto_type_overlap.json")
    mt = art("mode_timings.json")
    env = art("cost_envelope.json")
    payload = json.dumps({
        "sweep": d["recall_micro"], "contrasts": d["contrasts"],
        # The sweep figure draws the whole evaluated test set, so a digest over the comparison
        # set alone could not see it go stale.
        "sweep_whole": art(SWEEP_ARTIFACT)["recall_micro"],
        "contrasts_whole": art(SWEEP_ARTIFACT)["contrasts"],
        # The three Supporting Information figures draw from artifacts of their own, and a digest
        # that does not cover them cannot tell a stale one from a current one.
        "si_budget": art("budget_curve.json")["by_budget"],
        "si_rarefaction": art("mining_rarefaction.json")["rarefaction"],
        "si_external": art("external_budget_confound.json")["counted_cells"],
        "grain": cen["granularity_curve"], "gap": art("coverage_gap_types.json")["gap"],
        "uspto": usp["overlap"], "modes": {"i": mt["interactive"], "e": mt["exhaustive"]},
        # The two displays that replaced a grid of prose draw from artifacts of their own.
        "matched": art(MATCHED_ARTIFACT)["contrasts"],
        "precision": art(PRECISION_ARTIFACT)["precision_micro"],
        "chemistry": {c: v["recall"] for c, v in art(CHEMISTRY_ARTIFACT)["classes"].items()},
        "env": [(r["heavy"], r["finished"], r.get("t_generate")) for r in env["rows"]],
        # both drawings of the substrate, and the substrate string itself. The digest covered
        # only the stored-dialect runs, so it could not see the staleness that mattered most:
        # the figure went on drawing a named drug as its minor tautomer after the paper had
        # stopped claiming that drawing was the right one, and the gate stayed green.
        "case": {a: {"substrate": art(f)["substrate"],
                     "refs": [(c["rank"], c["key"], c["rule_id"], c["firing_atoms"])
                              for c in art(f)["candidates"] if c["is_reference"]]}
                 for a, f in (("i", "case_study.json"),
                              ("e", "case_study_exhaustive.json"),
                              ("id", "case_study_drawn.json"),
                              ("ed", "case_study_exhaustive_drawn.json"))},
    }, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


# The Supporting Information is single-column at 12 pt, so a figure there has about six inches of
# measure rather than the manuscript's 3.33. It carried 93 pages and no figure at all: twenty-two
# tables, and three quantities whose shape is the finding and which a table cannot show.
W_SI = 5.6


def fig_pr():
    """Precision against recall as the output budget sweeps, which is how the field reads a list.

    A reviewer asked for the comparison in a familiar form, and for a ranked list that is this
    curve: each arm traces one line as the budget widens, recall rising and precision falling,
    and a method is better where its line sits above and to the right of another. No run was
    needed -- recall at every budget is the deployment table and precision at the same budgets
    is the precision table, both at the population the comparison is read on.

    The pairing is the whole risk. The two artifacts name their arms differently and carry
    different arm lists, so an arm present in one and absent from the other is where a figure
    quietly shows fewer methods than the text counts. Arms that cannot be paired are returned by
    name and printed in the caption instead of disappearing.
    """
    prec = art(PRECISION_ARTIFACT)["precision_micro"]
    # The same population as the precision it is plotted against. These were PRECISION_ARTIFACT
    # and a named comparison-set file, so each point paired a precision measured on 1,170
    # substrates with a recall measured on 291 of them.
    rec = art(SWEEP_ARTIFACT)["recall_micro"]
    ks = sorted((int(k) for k in rec), key=int)
    kp = sorted((int(k) for k in prec[next(iter(prec))]), key=int)
    if ks != kp:
        raise SystemExit(f"recall is swept at {ks} and precision at {kp}, so a point on this "
                         f"curve would pair two different budgets")

    # Resolve both namings through the one style map, so neither artifact's spelling is a roster.
    points, pkey, dkey, absent = {}, {}, {}, []
    for arm in rec[str(ks[0])]:
        entry = _style_for(arm)
        if entry is None:
            raise SystemExit(f"the sweep carries an arm this figure has no style for: {arm}")
        label = entry[0]
        match = next((a for a in prec if a == label or a == arm), None)
        if match is None:
            absent.append(arm)
            continue
        points[label] = {k: (rec[str(k)][arm], prec[match][str(k)]) for k in ks}
        pkey[label], dkey[label] = match, arm

    fig, ax = plt.subplots(figsize=(W, 3.0))
    for label, pts in points.items():
        entry = next(e for e in SWEEP_STYLE.values() if e[0] == label)
        _, ls, mk, col = entry
        xs = [pts[k][0] for k in ks]
        ys = [pts[k][1] for k in ks]
        ours = label.startswith("GRAIL")
        ax.plot(xs, ys, ls, marker=mk, ms=3.0, lw=1.6 if ours else 1.0, color=col,
                mfc=col if ours else "white", mew=0.7, label=label, zorder=3 if ours else 2)
    ax.set_xlabel("micro recall", fontsize=7, labelpad=2.0)
    ax.set_ylabel("micro precision", fontsize=7, labelpad=2.0)
    ax.tick_params(labelsize=6.8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(fontsize=6.0, ncol=2, loc="upper right", frameon=False, handlelength=1.8)
    # The budget runs along each line and is the quantity the paper sweeps, so it is labelled on
    # one line rather than left to the caption.
    anchor = "GRAIL exhaustive" if "GRAIL exhaustive" in points else next(iter(points))
    for k in (1, 15, 50):
        if k in points[anchor]:
            x, y = points[anchor][k]
            ax.annotate(f"$k={k}$", (x, y), textcoords="offset points", xytext=(4, 5),
                        fontsize=5.8, color=INK_MUTED)
    save(fig, "fig_pr")
    plt.close(fig)
    return {"points": points, "precision_key": pkey, "recall_key": dkey,
            "absent": absent, "budgets": ks}


def fig_si_criterion_all():
    """Every declared criterion, including the two the manuscript's grid does not draw.

    The manuscript shows the three that answer "are these the same compound". The other two are
    declared, swept and kept here, because the paper's argument is that a choice of this kind has
    to be declared and its consequences shown, and dropping them from the paper rather than from
    the grid would be the opposite of that argument.
    """
    return fig_criterion(order=art(CRITERION_ARTIFACT)["criteria"],
                         stem="fig_si_criterion_all")


def fig_si_budget():
    """Recall against the rule budget, one line per output budget.

    The manuscript says the two operating modes are two points on one continuous setting and that
    which to run follows from the output budget answered at. The table of this sweep prints thirty
    numbers and the crossing is invisible in it: at a tight output budget the whole bank is worse
    than a budget of thirty, and at a wide one it is far better. That is one line crossing another.
    """
    d = art("budget_curve.json")["by_budget"]
    rbs = sorted((int(b) for b in d), key=int)
    ks = sorted((int(k) for k in d[str(rbs[0])]["recall_micro"]), key=int)
    style = {1: ("-", "o"), 5: ("-", "s"), 10: ("-", "^"), 15: ("-", "v"),
             30: ("-", "D"), 50: ("-", "P")}
    missing = [k for k in ks if k not in style]
    if missing:
        raise SystemExit(f"budget_curve.json carries output budgets this figure has no style for: "
                         f"{missing}")

    fig, ax = plt.subplots(figsize=(W_SI, 3.0))
    for i, k in enumerate(ks):
        ls, mk = style[k]
        y = [d[str(b)]["recall_micro"][str(k)] for b in rbs]
        ax.plot(rbs, y, ls, marker=mk, ms=3.4, lw=1.1, color=PALETTE[i % len(PALETTE)],
                label=f"$k={k}$")
    dep = art("budget_curve.json")["deployed_budget"]
    ax.axvline(dep, color=INK_FAINT, lw=0.6, zorder=0)
    ax.text(dep, ax.get_ylim()[0], " deployed", fontsize=6.2, color=INK_MUTED,
            va="bottom", ha="left")
    ax.set_xscale("log")
    ax.set_xticks(rbs)
    ax.set_xticklabels([f"{b:,}".replace(",", "\u2009") for b in rbs], fontsize=6.8)
    ax.set_xlabel("templates the generator may apply (rule budget)")
    ax.set_ylabel("micro recall")
    ax.legend(fontsize=6.4, ncol=3, loc="upper left", handlelength=1.8)
    ax.tick_params(labelsize=6.8)
    save(fig, "fig_si_budget")
    plt.close(fig)
    return {k: [d[str(b)]["recall_micro"][str(k)] for b in rbs] for k in (1, 50)}


def fig_si_rarefaction():
    """Templates mined against training pairs, with the spread over the draws at each point.

    The manuscript says template discovery from this corpus is not finished and gives the slope.
    A slope is a claim about a shape, and the shape is the evidence for it.
    """
    r = art("mining_rarefaction.json")
    pts = sorted(r["rarefaction"].values(), key=lambda v: v["pairs"])
    x = [v["pairs"] for v in pts]
    y = [v["templates_mean"] for v in pts]
    sd = [v["templates_sd"] for v in pts]
    fig, ax = plt.subplots(figsize=(W_SI, 2.7))
    ax.fill_between(x, [a - b for a, b in zip(y, sd)], [a + b for a, b in zip(y, sd)],
                    color=PALETTE[0], alpha=0.18, lw=0)
    ax.plot(x, y, "-", marker="o", ms=3.4, lw=1.2, color=PALETTE[0])
    ax.plot([r["distinct_training_pairs"]], [r["mined_templates"]], marker="*", ms=8,
            color=PALETTE[1], lw=0, zorder=4)
    ax.annotate(f"the whole corpus:\n{r['mined_templates']:,} templates".replace(",", "\u2009"),
                xy=(r["distinct_training_pairs"], r["mined_templates"]),
                xytext=(-10, 14), textcoords="offset points", ha="right", va="bottom",
                fontsize=6.4, color=INK_MUTED)
    ax.set_xlabel("annotated substrate-product pairs the bank was mined from")
    ax.set_ylabel("distinct templates")
    ax.tick_params(labelsize=6.8)
    save(fig, "fig_si_rarefaction")
    plt.close(fig)
    return len(pts), r["draws_per_point"]


def fig_si_external():
    """Recall against how much each tool emitted, in a benchmark that is not ours.

    The manuscript's one external check says the arms that emit more score higher. It states a
    rank correlation and a permutation test; the scatter is what those two numbers describe, and
    it also shows the reader that the association is within a drug and not only across drugs.
    """
    e = art("external_budget_confound.json")
    cells = e["counted_cells"]
    tools = sorted({c["tool"] for c in cells})
    MARK = ["o", "s", "^", "v", "D", "P", "X", "*"]
    if len(tools) > len(MARK):
        raise SystemExit(f"external_budget_confound.json carries {len(tools)} tools and this "
                         f"figure has {len(MARK)} markers")
    fig, ax = plt.subplots(figsize=(W_SI, 3.0))
    for i, t in enumerate(tools):
        pts = [c for c in cells if c["tool"] == t]
        ax.scatter([c["counted_emitted"] for c in pts], [c["recall"] for c in pts],
                   s=22, marker=MARK[i], facecolor="none", linewidths=0.9,
                   color=PALETTE[i % len(PALETTE)], label=t)
    ax.set_xscale("log")
    ax.set_xlabel("candidates the tool emitted for that drug, counted from the deposit")
    ax.set_ylabel("recall reported for that drug")
    ax.legend(fontsize=6.2, ncol=2, loc="upper left", handlelength=1.4)
    ax.tick_params(labelsize=6.8)
    rho = e["spearman_recall_against_counted_emission"]
    within = e["association_within_the_arms"][
        "spearman_after_removing_the_arm_effect_and_the_drug_effect"]
    ax.text(0.98, 0.03,
            f"Spearman {rho} over {len(cells)} cells;\n{within} with the arm\n"
            f"and drug effects removed",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=6.2, color=INK_MUTED)
    save(fig, "fig_si_external")
    plt.close(fig)
    return len(cells), len(tools)



if __name__ == "__main__":
    band = fig_sweep()["band"]
    fig_ceiling()
    fig_cost()
    fig_case()
    crit = fig_criterion()
    crit_all = fig_si_criterion_all()
    pr = fig_pr()
    mat = fig_matched()
    chem = fig_chemistry()
    toc = fig_toc()
    sib = fig_si_budget()
    sir = fig_si_rarefaction()
    sie = fig_si_external()
    (OUT / "figures.sha256").write_text(digest() + "\n")
    print("  fig_sweep.pdf, fig_ceiling.pdf, fig_cost.pdf, fig_case.pdf")
    print(f"  fig_toc.tif, fig_toc.eps, fig_toc.pdf  {toc[0]}x{toc[1]} in at {toc[2]} dpi, RGB")
    print(f"  fig_criterion  {len(crit['criteria'])} defensible criteria, "
          f"leads per criterion {crit['leads']}")
    print(f"  fig_si_criterion_all  all {len(crit_all['criteria'])} declared criteria")
    print(f"  fig_pr         {len(pr['points'])} arms paired over {len(pr['budgets'])} budgets; "
          f"not in the precision table: {', '.join(pr['absent']) or 'none'}")
    print(f"  fig_matched    {len(mat['comparators'])} comparators, {len(mat['cells'])} contrasts; "
          f"intervals clear of zero: "
          f"{sum(1 for c in mat['cells'].values() if c['excludes_zero'])}")
    print(f"  fig_chemistry  {len(chem['classes'])} classes by {len(chem['systems'])} systems "
          f"at a budget of {chem['budget']}")
    print("  fig_si_budget, fig_si_rarefaction, fig_si_external (Supporting Information)")
    print(f"    the budget curve crosses: at k=1 {sib[1][0]:.4f} -> {sib[1][-1]:.4f}, "
          f"at k=50 {sib[50][0]:.4f} -> {sib[50][-1]:.4f}")
    print(f"    rarefaction {sir[0]} points, {sir[1]} draws each; "
          f"external {sie[0]} cells over {sie[1]} tools")
    print(f"  the sweep's shaded regions, from the contrasts: {band}")
    print(f"  data digest {digest()[:24]}")
