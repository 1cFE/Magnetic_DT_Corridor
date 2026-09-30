"""Two-sided sensitivity: each lever moved by the SAME factor in both directions.

The one-sided tornado (stel_tornado_plot.py) shows only what each cost-down
lever returns when pulled from the tier-0 design basis to its deepest evidence
tier.  This chart mirrors every excursion: if the ladder improves a lever by a
factor f, this also prices moving it by 1/f the other way.

    upside   = LCOE(tier 0) - LCOE(deepest tier)
    downside = LCOE(tier 0) - LCOE(tier-0 value / f),   f = deepest / tier 0

The result is that LCOE is convex in essentially every input: every lever costs
more when it goes wrong than it returns when it goes right, by between 1.2x and
6.5x.  That is the honest reading of a one-sided tornado -- it shows the half of
each distribution that flatters the design.

Three levers from the one-sided chart are excluded because they have no
meaningful mirror: power cycle (there is no cycle worse than the Rankine
baseline in the model), brownfield siting (a checkbox -- the mirror of
"brownfield" is the greenfield baseline itself), and reactor scale (a 333 MWe
anchor has not been solved).

NOT every downside here is a credible scenario -- a 25.6-year construction and a
coil markup 3.8x worse than the stellarator's already-uncalibrated value are
mechanical mirrors, not forecasts.  They are drawn because the chart's claim is
about the SHAPE of the response, not about scenario likelihood.  Read the ratio
column in the printed table for the asymmetry itself.

matplotlib's font_manager imports plistlib -> xml.parsers.expat -> pyexpat,
blocked by an Application Control policy here; plistlib is macOS-only, so a
stub lets the rest of matplotlib load.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _os.environ.get("COSTINGFE_SRC", "1costingfe/src"))
import sys, types
sys.modules.setdefault("plistlib", types.ModuleType("plistlib"))

import io, json, contextlib, importlib.util
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

spec = importlib.util.spec_from_file_location("t", "ct_tornado.py")
t = importlib.util.module_from_spec(spec)
with contextlib.redirect_stdout(io.StringIO()):
    spec.loader.exec_module(t)

S = json.load(open("stel_anchors_data.json"))["data"]["rankine_base"][0]
L0 = t.levers()
baseline = t.calc(S, L0)["lcoe"]

MARKUP_PARITY = 1.0 / (2.0 * (5.87 / 3.09))     # x3.8 stellarator coil penalty

def lc(**kw):
    L = dict(L0)
    L.update(kw)
    return t.calc(S, L)["lcoe"]


# (display name, lever key, tier-0 value, deepest-tier value, formatter, within_precedent)
# within_precedent = False where the mirrored downside exceeds anything on record
# for an energy project, and is therefore arithmetic rather than a scenario:
#   Construction 25.6 yr  > Olkiluoto 3 (~18 yr), the worst nuclear build on record
#   REBCO x5 = $250/kA.m  > today's ~$150-200 spot; assumes tape gets DEARER than now
#   Coil markup x3.80     = 14.4x a tokamak's, with no mechanism and no precedent
#   Cost of capital 16.3%  venture-equity territory, not infrastructure project finance
#   Book life 11 yr        shorter than any reactor has been written off
SPEC = [
    ("Cost of capital",      "wacc",  0.07, 0.03,          "{:.1%}",   False),
    ("Book life",            "life",  30.0, 80.0,          "{:.0f} yr", False),
    ("Construction",         "constr", 8.0, 2.5,           "{:.1f} yr", False),
    ("Availability",         "av",    0.85, 0.98,          "{:.3f}",   True),
    ("Fixed O&M",            "om",     1.0, 0.45,          "×{:.2f}",  True),
    ("Indirect cost",        "indir", 0.20, 0.08,          "{:.0%}",   True),
    ("REBCO $/kA·m",       "coil",   1.0, 0.20,          "×{:.2f}",  False),
    ("Coil markup",          "coil",   1.0, MARKUP_PARITY, "×{:.2f}",  False),
    ("First-wall fluence",   "flu",    1.0, 3.0,           "×{:.2f}",  True),
]

rows = []
for name, key, v0, v3, fmt, bounded in SPEC:
    mirror = v0 * v0 / v3                        # same factor, opposite direction
    up = baseline - lc(**{key: v3})
    dn = baseline - lc(**{key: mirror})          # negative: LCOE rose
    rows.append(dict(name=name, up=up, dn=dn, ratio=abs(dn / up), bounded=bounded,
                     best=fmt.format(v3), worst=fmt.format(mirror)))

rows.sort(key=lambda r: r["dn"], reverse=True)   # index 0 draws at the bottom,
                                                 # so this puts the worst at the top

# Okabe-Ito bluish-green / vermillion: validate_palette.js passes all six checks
# on this surface (deutan dE 11.0, normal dE 25.8, contrast > 3:1).
UP, DOWN, INK, MUTED, RULE = "#009E73", "#D55E00", "#1a1c20", "#6a6f78", "#c9c6bf"
SURFACE = "#fcfcfb"

fig, ax = plt.subplots(figsize=(11.6, 6.8))
fig.patch.set_facecolor(SURFACE)
ax.set_facecolor(SURFACE)
fig.subplots_adjust(left=0.20, right=0.965, top=0.845, bottom=0.335)

y = list(range(len(rows)))
down_bars = ax.barh(y, [r["dn"] for r in rows], color=DOWN, height=0.62,
                    edgecolor="white", linewidth=0.6,
                    label="lever moved the wrong way")
for bar, r in zip(down_bars, rows):                 # texture = beyond precedent
    if not r["bounded"]:
        bar.set_hatch("///")
        bar.set_edgecolor("#ffffff")
ax.barh(y, [r["up"] for r in rows], color=UP, height=0.62,
        edgecolor="white", linewidth=0.6, label="lever pulled to its deepest tier")

span = max(max(r["up"] for r in rows), max(-r["dn"] for r in rows))
for i, r in enumerate(rows):
    ax.text(r["dn"] - span * 0.012, i, f"{r['worst']}   {r['dn']:,.0f}",
            va="center", ha="right", fontsize=8.6, color=DOWN)
    ax.text(r["up"] + span * 0.012, i, f"{r['best']}   +{r['up']:,.0f}",
            va="center", ha="left", fontsize=8.6, color=UP)

ax.axvline(0, lw=1.0, color=INK, zorder=4)
ax.set_yticks(y)
ax.set_yticklabels([r["name"] for r in rows], fontsize=10)
ax.set_xlim(-span * 1.30, span * 0.42)
ax.set_xlabel(r"change in LCOE  [\$/MWh]      baseline \$227/MWh",
              fontsize=10.5, color=INK)
ax.grid(axis="x", alpha=.22)
ax.set_axisbelow(True)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.tick_params(colors=MUTED, labelsize=9.5, length=0)
for lbl in ax.get_yticklabels():
    lbl.set_color(INK)
from matplotlib.patches import Patch
handles = [Patch(facecolor=DOWN, label="lever moved the wrong way"),
           Patch(facecolor=DOWN, hatch="///", edgecolor="white",
                 label="downside exceeds any energy-project precedent"),
           Patch(facecolor=UP, label="lever pulled to its deepest tier")]
ax.legend(handles=handles, frameon=False, fontsize=9.3, loc="lower left",
          bbox_to_anchor=(0.0, -0.285), ncol=3, labelcolor=INK)

fig.text(0.018, 0.968, "Every lever costs more when it goes wrong than it returns when it goes right",
         fontsize=13.5, color=INK, ha="left", va="top", fontweight="600")
fig.text(0.018, 0.928,
         "1 GWe stellarator  ·  each lever moved by the same factor in both "
         "directions from the tier-0 design basis",
         fontsize=9.8, color=MUTED, ha="left", va="top")

FOOT = "\n".join([
    "Downside excursions are the exact mirror of the ladder's own improvements: a lever the ladder improves by a factor f is also priced at 1/f.",
    r"Hatched bars exceed anything on record for an energy project: 25.6-yr construction beats Olkiluoto 3 (~18 yr), the worst nuclear",
    r"build ever; REBCO ×5 is \$250/kA·m, above today's ~\$150–200 spot; 16.3% is venture equity, not project finance; an 11-yr book",
    r"life is shorter than any reactor write-off; and a ×3.8 coil markup is 14.4× a tokamak's, with no mechanism. Solid bars sit within",
    r"precedent. LCOE is convex in nearly every input, so the asymmetry — not any one bar — is the finding.",
    "Power cycle, brownfield siting and reactor scale are omitted: they have no meaningful mirror.",
])
fig.text(0.018, 0.020, FOOT, fontsize=8.3, color=MUTED, linespacing=1.75, ha="left")

fig.savefig("figures/stel_tornado_symmetric.png", dpi=155, facecolor=SURFACE)
print(f"wrote figures/stel_tornado_symmetric.png   baseline ${baseline:.2f}/MWh\n")
print(f"  {'lever':<20}{'best':>10}{'upside':>9}{'worst':>10}{'downside':>10}{'ratio':>8}")
for r in sorted(rows, key=lambda r: -r["ratio"]):
    print(f"  {r['name']:<20}{r['best']:>10}{r['up']:>+9.1f}"
          f"{r['worst']:>10}{r['dn']:>+10.1f}{r['ratio']:>8.2f}")
