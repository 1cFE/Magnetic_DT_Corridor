"""Evidence-tier ladder bar charts, one per 1cFE-authored corridor.

Standardized on the format used by the p-B11 and Helion dispatches: a grouped
vertical bar per tier, two series (the corridor's two anchors), cumulative left
to right, every bar directly labelled, with the 1 c/kWh target drawn in.

The two-colour series palette is the one already in use in those dispatches
(tab:blue / tab:green); it passes the categorical checks (deutan dE 23.5,
normal-vision dE 25.2, contrast > 3:1 on this surface), and every bar carries a
direct value label so identity never rests on colour alone.

Tier vocabulary follows the approved cost-down lever table:
  0 design basis / 1 applicable record / 2 extrapolation with a known
  mechanism / 3 speculation, no mechanism.  Cumulative left to right.

Reads corridor_tiers.json.  Writes:
  mature_tier_ladder.png / pulsed_tier_ladder.png / revenue_tier_ladder.png
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _os.environ.get("COSTINGFE_SRC", "1costingfe/src"))
import sys, types
sys.modules.setdefault("plistlib", types.ModuleType("plistlib"))

import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

D = json.load(open("corridor_tiers.json"))

SURFACE = "#fcfcfb"
C1, C2 = "#1f77b4", "#2ca02c"     # validated categorical pair, fixed order
INK, MUTED, RULE = "#1a1c20", "#6a6f78", "#c9c6bf"
TARGET = 10.0                      # $/MWh == 1 c/kWh

TIERS = ["0: design basis", "1: applicable record",
         "2: extrapolation", "3: speculation"]

DOT, MINUS, SUB2, TIMES = "·", "−", "₂", "×"


def ladder(fname, title, sub, s1_label, s1, s2_label, s2, notes, ymax=None):
    fig, ax = plt.subplots(figsize=(13.2, 6.0))
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    x = range(len(TIERS))
    w = 0.38
    b1 = ax.bar([i - w / 2 for i in x], s1, w, label=s1_label, color=C1, zorder=3)
    b2 = ax.bar([i + w / 2 for i in x], s2, w, label=s2_label, color=C2, zorder=3)

    lo = min(list(s1) + list(s2) + [0])
    hi = ymax if ymax else max(list(s1) + list(s2)) * 1.18
    for bars, vals in ((b1, s1), (b2, s2)):
        for bar, v in zip(bars, vals):
            off = hi * 0.015
            ax.text(bar.get_x() + bar.get_width() / 2,
                    v + off if v >= 0 else v - off * 2.4,
                    f"{v:,.1f}", ha="center",
                    va="bottom" if v >= 0 else "top",
                    fontsize=11.5, color=INK, fontweight="600", zorder=4)

    # target line, with a left gutter opened up so its label never sits on a bar
    ax.set_xlim(-0.92, len(TIERS) - 0.5)
    ax.axhline(TARGET, ls="--", lw=1.1, color="#b8891f", zorder=2)
    ax.text(-0.88, TARGET + hi * 0.014, "1 ¢/kWh\n($10/MWh)", fontsize=10,
            color="#b8891f", ha="left", va="bottom", zorder=5, linespacing=1.35)
    if lo < 0:
        ax.axhline(0, lw=0.9, color=RULE, zorder=2)

    # tier title and its lever notes are drawn separately so the title can carry
    # its own weight and size; notes hang below in a blended (data-x, axes-y) frame
    ax.set_xticks(list(x))
    ax.set_xticklabels(TIERS, fontsize=12.5, color=INK, fontweight="600")
    tr = ax.get_xaxis_transform()
    for i, n in enumerate(notes):
        ax.text(i, -0.125, n, transform=tr, ha="center", va="top",
                fontsize=9.6, color=MUTED, linespacing=1.6)

    ax.set_ylabel("LCOE  [$/MWh]", fontsize=12.5, color=INK, fontweight="600")
    ax.set_ylim(lo * 1.35 if lo < 0 else 0, hi)
    ax.set_title(title, fontsize=16, color=INK, fontweight="600", loc="left", pad=20)
    ax.text(0, 1.018, sub, transform=ax.transAxes, fontsize=11.5, color=MUTED,
            va="bottom")

    ax.grid(axis="y", color=RULE, lw=0.6, alpha=0.5, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(RULE)
    ax.tick_params(axis="y", colors=MUTED, labelsize=11.5, length=0)
    ax.tick_params(axis="x", colors=INK, labelsize=12.5, length=0, pad=8)
    leg = ax.legend(frameon=False, fontsize=12, loc="upper right", labelcolor=INK)
    for txt in leg.get_texts():
        txt.set_fontweight("600")

    fig.subplots_adjust(left=0.072, right=0.985, top=0.868, bottom=0.245)
    fig.savefig(fname, dpi=160, facecolor=SURFACE)
    plt.close(fig)
    print(f"wrote {fname}")


# Tier 1 carries no cost-of-capital record, so the 7% design basis is held there.
NOTE_T1 = (f"no WACC record (7% held)\n"
           f"0.92 avail {DOT} 60 yr life {DOT} 5 yr build\n"
           f"16% indirect {DOT} O&M {MINUS}31%")

# ------------------------------------------------------------------- mature D-T
M = D["mature"]
ladder(
    "figures/mature_tier_ladder.png",
    "Mature magnetic D-T: evidence-tier ladder, cumulative by tier",
    f"stellarator archetype {DOT} 1costingFE bottom-up {DOT} "
    f"each tier carries every entry below it",
    "1 GWe", [r[1] for r in M["stel_1g"]],
    "3 GWe", [r[1] for r in M["stel_3g"]],
    ["machine as designed,\ncommercial economics",
     NOTE_T1,
     f"5% WACC {DOT} 0.95 avail {DOT} 80 yr life\n"
     f"3.25 yr build {DOT} sCO{SUB2} {DOT} 12% indirect\n"
     f"REBCO $25/kA{DOT}m {DOT} parity coils {DOT} fluence {TIMES}2",
     f"3% WACC {DOT} 0.98 avail {DOT} 2.5 yr build\n"
     f"8% indirect {DOT} REBCO $10/kA{DOT}m\n"
     f"fluence {TIMES}3 {DOT} brownfield"],
)

# --------------------------------------------------------------- pulsed power
P = D["pulsed"]
ladder(
    "figures/pulsed_tier_ladder.png",
    "Pulsed power: evidence-tier ladder, cumulative by tier",
    f"1 GWe {DOT} both configurations at their design rep rate {DOT} "
    f"sCO{SUB2} from tier 2",
    "fiber / direct, 10 Hz", [r[1] for r in P["fiber"]],
    "KrF / hybrid, 1 Hz", [r[1] for r in P["krf"]],
    ["as-designed drivers,\ncommercial economics",
     NOTE_T1,
     f"5% WACC {DOT} 0.95 avail {DOT} 80 yr life\n"
     f"3.25 yr build {DOT} sCO{SUB2} {DOT} 12% indirect\n"
     f"half-step driver + targets",
     f"3% WACC {DOT} 0.98 avail {DOT} 2.5 yr build\n"
     f"8% indirect {DOT} optics {TIMES}3\n"
     f"targets {MINUS}90%/{MINUS}50% {DOT} 10 FTE"],
)

# ------------------------------------------------------------ alternate revenue
R = D["revenue"]
ladder(
    "figures/revenue_tier_ladder.png",
    "Alternate revenue: evidence-tier ladder, cumulative by tier",
    "co-product credited against one 1 GWe D-T tokamak held at its published NOAK baseline",
    "+ gold transmutation", [r[1] for r in R["gold"]],
    "+ high-grade heat", [r[1] for r in R["heat"]],
    ["electricity only,\n$110.5/MWh",
     "spot Au at plant WACC,\n200 MW-th at observed price",
     "ledger basis: 3% cooldown;\n200 MW-th + TES capacity",
     "Au fungible day one;\nheat-led, 1 GW-th offtake"],
)
