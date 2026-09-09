"""Tornado sensitivity + lever map -> cost floor, compact tokamak, 1 GWe.

Consumes ct_corridor_data.json (corrected model, fixed-geometry cycle/coupling).
Reproduces the reduced-CAS model of mature_corridor_report.py, with two changes:
  * the cycle and coupling levers now bank extra OUTPUT at fixed geometry rather
    than shrinking the machine, so they enter as alternative design points;
  * first-wall life is charged on PEAK wall load (q_n_peak), not the plant
    average, so CAS72 is no longer over-credited by the peaking factor.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _os.environ.get("COSTINGFE_SRC", "1costingfe/src"))
import json, math

D = json.load(open("ct_corridor_data.json"))
META, DATA = D["meta"], D["data"]
SCALE = META["scale"]
SI1 = SCALE.index(1000)
TARGET = 10.0

# Plant-economics constants are architecture-independent; carried over unchanged
# from the published corridor dataset so the two runs stay comparable.
M = dict(inflation=0.02, fluence=18.0, indir=0.2, ref_constr=6.0, ref_p=1000.0,
         owner=41.2, om=54.9, ship=0.015, spares=0.03, tax=0.01, ins=0.015,
         startup=40.0, decom=272.0, av=META["av"], life=META["life"],
         wacc=META["wacc"])

AGG = dict(wacc=0.03, life=60.0, indir=0.10, constr=3.0, av=0.95, flu=3.0,
           disr=0.167, coil=0.60, heat=0.40, fw=0.70, shield=0.70, vessel=0.60,
           assembly=0.65, rh=0.55, fuelh=0.65, coolant=0.60, iandc=0.60,
           startup=0.33, bld=0.65, elec=0.40, hr=0.60, om=0.45, ins=0.33,
           decom=0.50)
BASE = dict(wacc=M["wacc"], life=M["life"], indir=M["indir"], constr=None,
            av=M["av"], flu=1.0, disr=1.0, coil=1.0, heat=1.0, fw=1.0,
            shield=1.0, vessel=1.0, assembly=1.0, rh=1.0, fuelh=1.0,
            coolant=1.0, iandc=1.0, startup=1.0, bld=1.0, elec=1.0, hr=1.0,
            om=1.0, ins=1.0, decom=1.0)
LABEL = dict(wacc="WACC 7%->3%", life="Plant life 30->60 yr",
             indir="Indirect cost 20%->10%", constr="Construction 6->3 yr",
             av="Availability 85%->95%", flu="Fluence limit x3",
             disr="Disruption rate x0.167", coil="Magnets -40%",
             heat="Heating & CD -60%", fw="First wall + divertor -30%",
             shield="Shield -30%", vessel="Vacuum vessel -40%",
             assembly="Assembly labor -35%", rh="Remote handling -45%",
             fuelh="Tritium plant -35%", coolant="Coolant loops -40%",
             iandc="I&C -40%", startup="Start-up cost -67%",
             bld="Buildings -35%", elec="Electrical plant -60%",
             hr="Heat rejection -40%", om="O&M -55%", ins="Insurance -67%",
             decom="Decommissioning -50%")


def crf(i, n):
    return i * (1 + i) ** n / ((1 + i) ** n - 1)


def lev_annual(a, i, g, n, tc):
    a1 = a * (1 + g) ** tc
    pv = (a1 * n / (1 + i) if abs(i - g) < 1e-9
          else a1 * (1 - ((1 + g) / (1 + i)) ** n) / (i - g))
    return crf(i, n) * pv


def lev_repl(ev, t, i, n):
    if t <= 0 or ev <= 0:
        return 0.0
    s = (1 + i) ** (-t)
    nr = max(0.0, math.ceil(n / t) - 1.0)
    if nr <= 0:
        return 0.0
    pv = ev * (s * (1 - s ** nr) / (1 - s) if abs(1 - s) > 1e-12 else ev * nr)
    return crf(i, n) * pv


def calc(b, L, zero_core=False):
    P, n_mod = b["P"], b["n_mod"]
    Tc = b["constr"] if L["constr"] is None else L["constr"]
    # PEAK wall load sets first-wall life; the plant average over-credits it.
    raw = min(max(M["fluence"] * L["flu"] / b["q_n_peak"], 0.5), L["life"] * L["av"])
    coreL = raw / (1 + b["drate"] * b["dmg"] * raw)
    av = L["av"] * (1 - b["drate"] * b["ddown"] * L["disr"] / 8760.0)
    fwL, divL = b["fw"] * L["fw"], b["divertor"] * L["fw"]
    cas22 = (fwL + divL + b["shield"] * L["shield"] + b["coil"] * L["coil"]
             + b["heat"] * L["heat"] + b["struct"] + b["vessel"] * L["vessel"]
             + b["power"] + b["rh"] * L["rh"] + b["assembly"] * L["assembly"]
             + b["coolant"] * L["coolant"] + b["cryo"] + b["radwaste"]
             + b["fuelhandling"] * L["fuelh"] + b["other22"]
             + b["iandc"] * L["iandc"] + b["rest22"])
    if zero_core:
        cas22, fwL, divL = 0.0, 0.0, 0.0
    cas21, cas24, cas26 = b["cas21"] * L["bld"], b["cas24"] * L["elec"], b["cas26"] * L["hr"]
    c23_28 = b["cas23"] * L.get("turb", 1.0) + cas24 + b["cas25"] + cas26 + b["cas27"] + b["cas28"]
    cas20 = cas21 + cas22 + c23_28
    cas30 = L["indir"] * cas20 * (Tc / M["ref_constr"])
    sc = math.sqrt(P / M["ref_p"])
    cas40 = M["owner"] * sc
    cas50 = (M["ship"] * cas20 + M["spares"] * c23_28 + M["tax"] * cas20
             + M["ins"] * L["ins"] * (cas20 + cas30)
             + (M["startup"] * L["startup"] + M["decom"] * L["decom"]) * (P / M["ref_p"]))
    overnight = b["cas10"] + cas20 + cas30 + cas40 + cas50
    fidc = ((1 + L["wacc"]) ** Tc - 1) / (L["wacc"] * Tc) - 1
    cap = overnight * (1 + fidc)
    cas90 = crf(L["wacc"], L["life"]) * cap
    cas71 = lev_annual(M["om"] * sc * L["om"], L["wacc"], M["inflation"], L["life"], Tc)
    cas72 = lev_repl(fwL + divL, coreL / av, L["wacc"], L["life"])
    k = 1e6 / (8760 * P * av)
    return dict(lcoe=(cas90 + cas71 + cas72 + b["cas80"]) * k, cap=cap, av=av,
                coreL=coreL, capkw=cap * 1000 / P)


def levers(on=(), zero=()):
    L = dict(BASE)
    for k in on:
        L[k] = AGG[k]
    for k in zero:
        L[k] = 0.0
    return L


B1 = DATA["rankine_base"][SI1]
base = calc(B1, levers())["lcoe"]
print("=" * 78)
print(f"COMPACT TOKAMAK, 1 GWe — baseline LCOE ${base:.2f}/MWh "
      f"(1costingFE full run: ${B1['lcoe_full']:.2f})")
print(f"  R0 {B1['R0']:.2f} m · B0 {B1['B']:.2f} T · q_n {B1['q_n']:.2f} avg / "
      f"{B1['q_n_peak']:.2f} peak · FW life {calc(B1, levers())['coreL']:.1f} FPY")
print("=" * 78)
print("\nTORNADO — one lever at a time, 1 GWe\n")
rows = sorted(((LABEL[k], base - calc(B1, levers((k,)))["lcoe"]) for k in AGG),
              key=lambda r: -r[1])
# the two fixed-geometry design-point levers
for tag, key in (("sCO2 cycle (fixed geometry)", "sco2_fixed"),
                 ("Heating coupling 0.83->0.95", "cpl_fixed")):
    rows.append((tag, base - calc(DATA[key][SI1], levers())["lcoe"]))
rows.sort(key=lambda r: -r[1])
wmax = max(abs(v) for _, v in rows)
for name, v in rows:
    bar = "#" * max(1, int(round(abs(v) / wmax * 42)))
    print(f"  {name:<30}{v:+7.2f}  {bar}")
print(f"\n  baseline ${base:.2f}  ->  all levers together: "
      f"${calc(DATA['both_fixed'][SI1], levers(tuple(AGG)))['lcoe']:.2f}/MWh")

print("\n" + "=" * 78)
print("COST FLOOR — cumulative, best design point at each scale")
print("=" * 78)
for si, P in enumerate(SCALE):
    if P == 4000:
        continue  # cycle lever loses bisection monotonicity here; excluded
    b_all = DATA["both_fixed"][si]
    full = calc(b_all, levers(tuple(AGG)))
    free = calc(b_all, levers(tuple(AGG)), zero_core=True)
    print(f"  {P:5d} MWe  ->  all levers ${full['lcoe']:7.2f}   "
          f"free core ${free['lcoe']:7.2f}   core costs ${full['lcoe']-free['lcoe']:6.2f}")

print("\n  FREE-CORE CROSS-CHECK vs 1cf.energy 'what if the core were free?'")
b1 = DATA["rankine_base"][SI1]
print(f"    baseline finance, 1 GWe, D-T:  this model ${calc(b1, levers(), zero_core=True)['lcoe']:.1f}"
      f"/MWh   |  published $29/MWh")
