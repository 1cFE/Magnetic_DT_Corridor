"""Shared evidence-tier ladder across the three 1cFE-authored corridors.

One tier vocabulary, applied to whichever levers each corridor's model actually
exposes, so the three ladders are read on the same footing as the p-B11 and
Helion dispatches:

  tier 0  design baseline   machine as designed, ordinary commercial economics
  tier 1  records           every knob at a value some real project has held
  tier 2  extrapolations    labelled steps past the records, each with a mechanism
  tier 3  speculation       past any evidence base, labelled as such

Tiers are CUMULATIVE: tier N carries every entry from the tiers below it.

Models
  mature   ct_tornado.calc() over stel_anchors_data.json (selected archetype)
           and ct_corridor_data.json (compact tokamak, reference)
  pulsed   Python port of the reduced model shipped in corridor_tool.html,
           validated to reproduce 1costingFE to 0.00 $/MWh at baseline
  revenue  gold / heat co-product ledger over the 1 GWe D-T tokamak base plant

Writes corridor_tiers.json and prints the ladder tables.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _os.environ.get("COSTINGFE_SRC", "1costingfe/src"))
import io
import json
import contextlib
import importlib.util

# ---------------------------------------------------------------- mature model
spec = importlib.util.spec_from_file_location("t", "ct_tornado.py")
T = importlib.util.module_from_spec(spec)
with contextlib.redirect_stdout(io.StringIO()):
    spec.loader.exec_module(T)

STEL = json.load(open("stel_anchors_data.json"))["data"]
_CT = json.load(open("ct_corridor_data.json"))
CT, CT_SCALE = _CT["data"], _CT["meta"]["scale"]
CT_I1, CT_I2 = CT_SCALE.index(1000), CT_SCALE.index(2000)

# Coil account = kA.m x $/kA.m x markup, so conductor price and manufacturing
# markup are both pure multipliers on the whole magnet account.
REBCO_BASE = 50.0
MARKUP = {"stellarator": 5.87, "tokamak": 3.09}
# f_path in cas22._COIL_DEFAULTS: the coil account carries BOTH a path
# multiplier and a manufacturing markup, and "tokamak parity" means retiring
# both -- 2.0 x (5.87/3.09) = 3.80 for a stellarator, not the markup alone.
PATH = {"stellarator": 2.0, "tokamak": 1.0}


def coil_mult(rebco, planar=False, concept="stellarator"):
    m = rebco / REBCO_BASE
    if planar:
        m *= (MARKUP["tokamak"] / MARKUP[concept]) * (PATH["tokamak"] / PATH[concept])
    return m


# Universal record / extrapolation / speculation values, keyed to ct_tornado's
# lever names.  See the markdown appendices for the citation behind each entry.
# Each stop is the best value some real project has held at that grade; see the
# markdown appendices for the citation behind every entry.
T1_REC = {"av": 0.92, "life": 60.0, "constr": 5.0,
          "indir": 0.16, "om": 0.69}
T2_EXT = {"wacc": 0.05, "indir": 0.12,
          "av": 0.95, "life": 80.0, "constr": 3.25, "flu": 2.0,
          "om": 0.45}
# Brownfield siting is a scenario choice, not an evidence grade: one package
# (buildings, interconnection, heat rejection) that the tier-3 preset adopts.
T3_SPEC = {"wacc": 0.03, "indir": 0.08,
           "av": 0.98, "constr": 2.5, "flu": 3.0, "disr": 0.167,
           "bld": 0.65, "elec": 0.40, "hr": 0.60}


def mature_ladder(data, idx, concept):
    """Cumulative tier ladder for one magnetic archetype at one power anchor."""
    def L(cur):
        d = dict(T.BASE)
        d.update(cur)
        return d

    rows, cur = [], {}
    rows.append(["0: design baseline", T.calc(data["rankine_base"][idx], L(cur))["lcoe"]])

    cur.update(T1_REC)
    rows.append(["1: records", T.calc(data["rankine_base"][idx], L(cur))["lcoe"]])

    # tier 2 also turns on the two fixed-geometry design points (sCO2 cycle and
    # heating coupling), which live in the "both_fixed" slice rather than in L.
    cur.update(T2_EXT)
    cur["coil"] = coil_mult(25.0, planar=True, concept=concept)
    rows.append(["2: extrapolations", T.calc(data["both_fixed"][idx], L(cur))["lcoe"]])

    cur.update(T3_SPEC)
    cur["coil"] = coil_mult(10.0, planar=True, concept=concept)
    rows.append(["3: speculation", T.calc(data["both_fixed"][idx], L(cur))["lcoe"]])

    free = T.calc(data["both_fixed"][idx], L(cur), zero_core=True)["lcoe"]
    return rows, free


# ---------------------------------------------------------------- pulsed model
P = json.load(open("corridor_data.json"))
PMETA = P["meta"]
SCO2 = {"BLF": 0.80, "Xcimer": 0.84}
OPT = {"BLF": 9, "Xcimer": 3}          # 10 Hz fiber/direct, 1 Hz KrF/hybrid
PBASE = {"wacc": 0.07, "av": 0.85, "life": 30.0, "constr": 5.0, "indir": 0.20,
         "tgt": 1.0, "tfac": 1.0, "om": 1.0, "drv": 1.0, "vessel": 1.0,
         "shield": 1.0, "iandc": 1.0, "rh": 1.0, "hr": 1.0, "sco2": False,
         "bld": 1.0, "elec": 1.0, "startup": 40.0}


def _lerp(a, b, f):
    return a + (b - a) * f


def plcoe(concept, ri, L, eta_f, wear_f):
    """eta_f and wear_f are INCREMENTS between the two stored slices.

    corridor_data.json carries the laser wall-plug at its as-costed value and at
    its published ceiling, and the driver optics/foil life at 3e8 and 9e8 shots.
    An intermediate tier therefore takes the midpoint between those endpoints --
    an increment, not an independently sourced operating point.
    """
    b0, b1 = P[concept][0][ri], P[concept][1][ri]
    b = {k: _lerp(b0[k], b1[k], eta_f) for k in b0}
    eff = SCO2[concept] if L["sco2"] else 1.0
    cas22 = (b["driver"] * L["drv"] + b["estore"] + b["fw"]
             + b["shield"] * L["shield"] + b["vessel"] * L["vessel"]
             + b["structure"] + b["tfactory"] * L["tfac"] + b["rh"] * L["rh"]
             + b["iandc"] * L["iandc"] + b["rest22"])
    cas20 = (b["buildings"] * L["bld"] + cas22 + b["turbine"]
             + b["electric"] * L["elec"] + b["misc"] + b["heatrej"] * L["hr"]
             + b["materials"] + b["dtwin"])
    cas30 = L["indir"] * cas20 * (L["constr"] / 6)
    cas50 = (b["cas50"] - PMETA["startup"]) * (cas20 / b["cas20"]) + L["startup"]
    overnight = b["cas10"] + cas20 + cas30 + b["owner"] + cas50
    fidc = ((1 + L["wacc"]) ** L["constr"] - 1) / (L["wacc"] * L["constr"]) - 1
    crf = (L["wacc"] * (1 + L["wacc"]) ** L["life"]
           / ((1 + L["wacc"]) ** L["life"] - 1))
    amwh, amwhb = 1000 * 8760 * L["av"], 1000 * 8760 * 0.85
    repl = _lerp(b["replace"], b["replace_agg"], wear_f)
    capom = (crf * overnight * (1 + fidc) + b["om"] * L["om"]) * 1e6 / amwh
    shot = (repl + b["targets"] * L["tgt"]) * 1e6 / amwhb
    return (capom + shot) * eff


PT1 = {"av": 0.92, "life": 60.0, "constr": 5.0,
       "indir": 0.16, "om": 0.69}
# Driver capital, target factory and target opex have a sourced baseline and a
# sourced endpoint but nothing in between, so the tier-2 value is simply the
# midpoint of the two -- an increment between baseline and ceiling, not a
# separately sourced operating point.  Same convention as the wall-plug and
# shot-life increments above.
PT2 = {"wacc": 0.05, "indir": 0.12,
       "av": 0.95, "life": 80.0, "constr": 3.25,
       "sco2": True, "om": 0.45, "tfac": 0.825,
       "drv": {"BLF": 0.834, "Xcimer": 0.813},
       "tgt": {"BLF": 0.55, "Xcimer": 0.75}}
# tier 3 replaces the fleet-staffing O&M step with lights-out operation (~10 FTE)
PT3 = {"wacc": 0.03, "indir": 0.08,
       "av": 0.98, "constr": 2.5, "om": 0.0855, "tfac": 0.65,
       "drv": {"BLF": 0.667, "Xcimer": 0.625},
       "tgt": {"BLF": 0.10, "Xcimer": 0.50},
       "bld": 0.65, "elec": 0.40, "hr": 0.60}


def pulsed_ladder(concept):
    ri = OPT[concept]

    def L(cur):
        d = dict(PBASE)
        for k, v in cur.items():
            d[k] = v[concept] if isinstance(v, dict) else v
        return d

    # eta and shot-life increments by tier: none, none, midpoint, full
    rows, cur = [], {}
    rows.append(["0: design baseline", plcoe(concept, ri, L(cur), 0.0, 0.0)])
    cur.update(PT1)
    rows.append(["1: records", plcoe(concept, ri, L(cur), 0.0, 0.0)])
    cur.update(PT2)
    rows.append(["2: extrapolations", plcoe(concept, ri, L(cur), 0.5, 0.5)])
    cur.update(PT3)
    rows.append(["3: speculation", plcoe(concept, ri, L(cur), 1.0, 1.0)])
    return rows


# --------------------------------------------------------------- revenue model
# This corridor's premise is a MARKET, not a machine, so its ladder grades the
# revenue evidence while the plant is pinned at the published NOAK baseline
# (1 GWe D-T tokamak, eta_gen 0.40, availability 0.85, CRF 7%/30 yr).  Stacking
# aggressive plant levers under aggressive co-product prices would multiply two
# independent optimisms and make the bars unreadable; the plant's own lever
# stack is the mature corridor's result and is carried in the master lever map.
ANN_BASE = 821.87           # M$/yr all-in cost of the base plant (gold ledger)
LCOE_BASE = 110.536         # $/MWh, electricity only
AV_R, ETA_R, CRF_R = 0.85, 0.40, 0.0806
MWH_R = 1000 * 8760 * AV_R

GOLD_KG = 2706.0            # 197Au at 1 t/GW_th/yr on the 1 GWe tokamak
GOLD_COSTS_MWH = 2.856      # Hg feedstock + extraction loop + O&M + blanket markup
HG_ENRICH_CAPEX_MWH = 6.0   # deferred in the source; charged where unproven

# cogen scaling anchors, lifted from flexible_cogen_tool.html (1costingFE)
PNET_A = [100, 200, 400, 700, 1000, 1500, 2000]
PTOT_A = [4287, 5100, 6286, 7590, 8614, 9995, 11557]     # total capital M$
PT23_A = [72, 100, 146, 205, 258, 339, 425]              # turbine CAS23 M$
TESK, BOPK, TES_H = 30.0, 200.0, 4                       # $/kWh, $/kW_th, hours


def interp(x, xs, ys):
    if x <= xs[0]:
        return ys[0]
    for i in range(len(xs) - 1):
        if x <= xs[i + 1]:
            t = (x - xs[i]) / (xs[i + 1] - xs[i])
            return ys[i] + t * (ys[i + 1] - ys[i])
    i = len(xs) - 2
    t = (x - xs[i]) / (xs[i + 1] - xs[i])
    return ys[i] + t * (ys[i + 1] - ys[i])


def gold_lcoe(price_kg, cooldown_factor, enrich_capex):
    gross = GOLD_KG * price_kg / 1e6                       # M$/yr
    credit = gross * cooldown_factor * 1e6 / MWH_R
    return LCOE_BASE - credit + GOLD_COSTS_MWH + enrich_capex


def heat_lcoe(hfirm, price_th, cap_kw_yr, pnet, tes=True):
    """Cogen net LCOE, following flexible_cogen_tool.html with HFIRM generalized.

    The reactor is sized so that after diverting `hfirm` MW_th to the heat
    offtake it still nets `pnet` MW_e, i.e. at full power it makes
    pnet + eta*hfirm.  Heat and capacity revenue are credited against the
    electricity actually sold.
    """
    nfull = pnet + ETA_R * hfirm
    tot0 = interp(nfull, PNET_A, PTOT_A)
    turb_full = interp(nfull, PNET_A, PT23_A)
    reactor_c = tot0 - turb_full
    turb_c = turb_full if tes else interp(pnet, PNET_A, PT23_A)
    tes_c = TESK * (hfirm * TES_H) * 1e3 / 1e6 if tes else 0.0
    bop_c = BOPK * hfirm * 1e3 / 1e6
    cap = reactor_c + turb_c + tes_c + bop_c
    om = 0.0147 * tot0
    heat_rev = hfirm * price_th * 8760 * AV_R / 1e6
    peak_mwe = nfull if tes else pnet
    cap_rev = peak_mwe * 1e3 * cap_kw_yr / 1e6
    net_mwh = pnet * 8760 * AV_R
    return (CRF_R * cap + om - heat_rev - cap_rev) * 1e6 / net_mwh


def revenue_ladder():
    """Two series -- gold-credited and heat-credited -- on one 1 GWe base plant."""
    gold = [["0: design baseline", LCOE_BASE]]
    heat = [["0: design baseline", LCOE_BASE]]

    # tier 1 -- co-product at OBSERVED, contracted market terms.  Gold's spot
    # price is a record, but no record supports discounting a 14-yr deferred,
    # non-fungible, radioactive asset below the plant's own WACC, and the
    # enrichment plant is unpriced in the source -- so both revert here.
    gold.append(["1: records", gold_lcoe(100e3, 1.07 ** -14, HG_ENRICH_CAPEX_MWH)])
    heat.append(["1: records", heat_lcoe(200, 35.0, 0.0, 1000, tes=False)])

    # tier 2 -- the published ledger basis: the 14-yr wait discounted at 3% on
    # the physically-backed forward-asset argument, enrichment OPEX only; heat
    # at a high decarbonized offtake with TES-enabled capacity payments.
    gold.append(["2: extrapolations", gold_lcoe(100e3, 0.661, 0.0)])
    heat.append(["2: extrapolations", heat_lcoe(200, 50.0, 88.0, 1000, tes=True)])

    # tier 3 -- speculation: gold fungible on day one with free enrichment; the
    # heat-led plant, a GW-thermal offtake with electricity as a byproduct.
    gold.append(["3: speculation", gold_lcoe(100e3, 1.0, 0.0)])
    heat.append(["3: speculation", heat_lcoe(1000, 78.0, 139.0, 100, tes=True)])
    return gold, heat, LCOE_BASE


# ------------------------------------------------------------------ run + emit
OUT = {}

print("=" * 76)
print("MATURE MAGNETIC D-T  --  stellarator (selected archetype) + compact tokamak")
print("=" * 76)
s1, s1f = mature_ladder(STEL, 0, "stellarator")
s2, s2f = mature_ladder(STEL, 1, "stellarator")
c1, c1f = mature_ladder(CT, CT_I1, "tokamak")
c2, c2f = mature_ladder(CT, CT_I2, "tokamak")
print(f"{'rung':<22}{'stel 1GWe':>12}{'stel 3GWe':>12}{'tok 1GWe':>12}{'tok 2GWe':>12}")
for i in range(4):
    print(f"{s1[i][0]:<22}{s1[i][1]:>12.1f}{s2[i][1]:>12.1f}{c1[i][1]:>12.1f}{c2[i][1]:>12.1f}")
print(f"{'free core (at tier 3)':<22}{s1f:>12.1f}{s2f:>12.1f}{c1f:>12.1f}{c2f:>12.1f}")
OUT["mature"] = {"stel_1g": s1, "stel_3g": s2, "tok_1g": c1, "tok_2g": c2,
                 "free": {"stel_1g": s1f, "stel_3g": s2f, "tok_1g": c1f, "tok_2g": c2f}}

print()
print("=" * 76)
print("PULSED POWER  --  fiber/direct at 10 Hz and KrF/hybrid at 1 Hz, 1 GWe")
print("=" * 76)
pb, px = pulsed_ladder("BLF"), pulsed_ladder("Xcimer")
print(f"{'rung':<22}{'fiber/direct':>14}{'KrF/hybrid':>14}")
for i in range(4):
    print(f"{pb[i][0]:<22}{pb[i][1]:>14.1f}{px[i][1]:>14.1f}")
OUT["pulsed"] = {"fiber": pb, "krf": px}

print()
print("=" * 76)
print("ALTERNATE REVENUE  --  gold and heat credited against a 1 GWe D-T tokamak")
print("=" * 76)
gl, hl, l0 = revenue_ladder()
print(f"{'rung':<22}{'+ gold':>14}{'+ heat':>14}")
for i in range(4):
    print(f"{gl[i][0]:<22}{gl[i][1]:>14.1f}{hl[i][1]:>14.1f}")
OUT["revenue"] = {"gold": gl, "heat": hl, "elec_only_baseline": l0}

json.dump(OUT, open("corridor_tiers.json", "w"), indent=1)
print("\nwrote corridor_tiers.json")
