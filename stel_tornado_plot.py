"""Sensitivity of stellarator LCOE at 1 GWe, one cost-down lever at a time.

Every bar is a row of the approved cost-down lever table, taken from its tier-0
design basis to the DEEPEST value the evidence ladder reaches for it.  That
makes this chart read directly against the tier ladder: the ladder shows the
levers applied cumulatively, this shows each one alone.

Deliberately excluded: the CAS22/CAS50 account re-pricings (first wall, shield,
vessel, remote handling, assembly labour, insurance, decommissioning and the
rest).  They were retired from the evidence ladder, so pricing them here would
show the reader levers the ladder no longer contains.  Also excluded is the
disruption-rate term, which is identically zero for a stellarator (drate = 0 --
stellarators do not disrupt).

Two bars are coloured because they change the MACHINE rather than re-pricing a
fixed one: reactor scale re-solves at 3 GWe, and the coil term retires the two
stellarator-specific magnet constants.

matplotlib's font_manager imports plistlib -> xml.parsers.expat -> pyexpat,
which is blocked by an Application Control policy on this machine. plistlib is
used only on macOS, so a stub lets the rest of matplotlib load.
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

D = json.load(open("stel_anchors_data.json"))["data"]
BASE = D["rankine_base"][0]        # 1 GWe, tier-0 design basis
BIG = D["rankine_base"][1]         # 3 GWe, for the reactor-scale term
SCO2 = D["sco2_fixed"][0]          # sCO2 cycle solved at fixed geometry

L0 = t.levers()
baseline = t.calc(BASE, L0)["lcoe"]

# Stellarator magnet penalty: 2.0 coil-path multiplier x (5.87/3.09) markup.
# "Tokamak parity" retires BOTH, which is the x3.8 the lever table describes.
COIL_PARITY = 1.0 / (2.0 * (5.87 / 3.09))
REBCO_FLOOR = 10.0 / 50.0          # $10/kA.m against the $50 NOAK baseline


def d(**lev):
    """LCOE reduction from applying one lever to the tier-0 machine."""
    L = dict(L0)
    L.update(lev)
    return baseline - t.calc(BASE, L)["lcoe"]


def d_slice(data):
    """LCOE reduction from swapping the solved data slice."""
    return baseline - t.calc(data, L0)["lcoe"]


# one entry per row of the cost-down lever table, at its deepest tier value
rows = [
    ("Cost of capital  7% $\\rightarrow$ 3%",          d(wacc=0.03),        "lever"),
    ("Book life  30 $\\rightarrow$ 80 yr",             d(life=80.0),        "lever"),
    (f"Construction  {BASE['constr']:.0f} $\\rightarrow$ 2.5 yr",
                                                       d(constr=2.5),       "lever"),
    ("Availability  0.85 $\\rightarrow$ 0.98",         d(av=0.98),          "lever"),
    ("Fixed O&M  $-$55%",                              d(om=0.45),          "lever"),
    ("Indirect cost  20% $\\rightarrow$ 8%",           d(indir=0.08),       "lever"),
    ("Brownfield siting",                              d(bld=0.65, elec=0.40,
                                                         hr=0.60),          "lever"),
    ("Power cycle  Rankine $\\rightarrow$ sCO$_2$ Brayton", d_slice(SCO2),       "lever"),
    ("REBCO  \\$50 $\\rightarrow$ \\$10/kA$\\cdot$m",  d(coil=REBCO_FLOOR), "lever"),
    ("First-wall fluence  $\\times$3",                 d(flu=3.0),          "lever"),
    ("Coil markup $\\rightarrow$ tokamak parity ($\\times$3.8)",
                                                       d(coil=COIL_PARITY), "coil"),
    ("Reactor scale  1 $\\rightarrow$ 3 GWe",          d_slice(BIG),        "scale"),
]

rows.sort(key=lambda r: r[1])
labels = [r[0] for r in rows]
vals = [r[1] for r in rows]
kinds = [r[2] for r in rows]

GREEN = "#2f7d52"
colors = [GREEN] * len(vals)

fig, ax = plt.subplots(figsize=(10.4, 7.6))
fig.subplots_adjust(left=0.40, right=0.955, top=0.875, bottom=0.275)
y = range(len(rows))
ax.barh(list(y), vals, color=colors, height=0.72,
        edgecolor="white", linewidth=0.6)

for i, v in enumerate(vals):
    ax.text(v + max(vals) * 0.011, i, f"{v:.1f}", va="center", ha="left",
            fontsize=9, color="0.25")

ax.set_yticks(list(y))
ax.set_yticklabels(labels, fontsize=9.5)

ax.set_xlabel("reduction in LCOE  [$/MWh]", fontsize=10.5)
ax.set_xlim(0, max(vals) * 1.085)
ax.grid(axis="x", alpha=.25)
ax.set_axisbelow(True)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)

# title in FIGURE coordinates: the axes start far right of the long y-labels,
# so an axes-anchored title runs off the canvas
fig.text(0.022, 0.972, "What moves the cost of a 1 GWe stellarator",
         fontsize=13.5, color="0.1", ha="left", va="top", fontweight="600")
fig.text(0.022, 0.940,
         f"baseline ${baseline:.0f}/MWh  ·  each cost-down lever applied alone, "
         "at its deepest evidence tier",
         fontsize=9.8, color="0.42", ha="left", va="top")

FOOT = "\n".join([
    "One bar per row of the cost-down lever table, from the tier-0 design basis to the deepest value the",
    "evidence ladder reaches. The ladder applies these cumulatively; here each acts alone, so the bars do",
    "not sum to its descent. Two of them change the machine rather than re-pricing a fixed one: reactor scale",
    "re-solves the plant at 3 GWe, and coil markup retires both stellarator magnet constants — a 2.0",
    "coil-path multiplier and a ~1.9x manufacturing markup, together ~3.8. Neither has been calibrated",
    "against a built stellarator.",
])
fig.text(0.022, 0.012, FOOT, fontsize=8.4,
         color="0.42", linespacing=1.7, ha="left")

fig.savefig("figures/stel_tornado.png", dpi=155)
print(f"wrote figures/stel_tornado.png   baseline ${baseline:.2f}/MWh")
print(f"\n  {'cost-down lever':<52}{'d LCOE':>9}")
for lab, v, k in sorted(rows, key=lambda r: -r[1]):
    clean = (lab.replace("$_2$", "2").replace("$\\rightarrow$", "->")
                .replace("$\\times$", "x").replace("$\\cdot$", ".")
                .replace("$-$", "-").replace("\\$", "$"))
    print(f"  {clean:<52}{v:+9.2f}")
