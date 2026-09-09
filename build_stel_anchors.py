"""Stellarator corridor dataset at TWO power anchors (1 GWe, 3 GWe).

Generalizes build_stel_corridor.py, which solved 1 GWe only, so the evidence-tier
ladder can quote the selected archetype at the same two anchors Tal's dispatches
use. Sizing is stellarator_sizer.py (ISS04 + Sudo + beta + wall-load cap,
bisected on R0 against the power target); costing is 1costingFE at that geometry.
Cycle and coupling levers are evaluated at FIXED geometry by bisecting requested
net until back-solved fusion power matches the baseline, exactly as in the 1 GWe run.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _os.environ.get("COSTINGFE_SRC", "1costingfe/src"))
import json, sys
from costingfe import CostModel
from costingfe.types import ConfinementConcept as C, Fuel, PowerCycle
from costingfe.defaults import MAGNET_TABLE, MagnetProperties
from costingfe.layers.geometry import RadialBuild, compute_geometry
import stellarator_sizer as SS

F, AV, LIFE, WACC = Fuel.DT, 0.85, 30.0, 0.07
BMAX, Q_PEAK, F_PK = 23.0, 4.7, 2.0
ETA_CPL = [0.8333, 0.95]
ANCHORS = [1000.0, 3000.0]
BASE = dict(availability=AV, lifetime_yr=LIFE, interest_rate=WACC,
            nwl_peaking_factor=F_PK)

def mag():
    MAGNET_TABLE["rebco_hts"] = MagnetProperties(b_max=BMAX, recirc_power_factor=0.0, cryo_temp_k=20.0)

def make(P):
    OP = SS.size_from_power(P, A=4.5, B_max=BMAX, f_coil=2.4, iota=1.0,
                            f_ren=1.0, beta_max=0.05, q_n_max=Q_PEAK / F_PK)
    PA = max(10.0, OP["P_aux"])
    GEO = dict(R0=OP["R0"], plasma_t=OP["a"], B=OP["B0"], n_e=OP["n20"] * 1e20,
               T_e=OP["T"], plasma_volume=OP["V"], structure_t=0.20, vessel_t=0.20,
               p_cryo=0.5, p_input=PA, p_ecrh=PA)

    def run(cycle, cpl, pnet):
        mag(); m = CostModel(C.STELLARATOR, F, power_cycle=cycle)
        return m, m.forward(net_electric_mw=pnet, eta_couple=cpl, **GEO, **BASE)

    def extract(m, r, target):
        c, d, p, pt = r.costs, r.cas22_detail, r.params, r.power_table
        g = compute_geometry(RadialBuild(R0=OP["R0"], plasma_t=OP["a"], elon=1.0,
            blanket_t=float(p["blanket_t"]), ht_shield_t=float(p["ht_shield_t"]),
            structure_t=0.20, vessel_t=0.20), C.STELLARATOR)
        q_n = float(pt.p_neutron) / g.firstwall_area
        gg = lambda k: float(d.get(k, 0.0))
        keys = ("C220101","C220102","C220103","C220104","C220105","C220106",
                "C220107","C220108","C220110","C220111","C220200","C220300",
                "C220400","C220500","C220600","C220700")
        return dict(P=float(pt.p_net), P_target=target, n_mod=1, R0=OP["R0"],
            a=OP["a"], B=OP["B0"], kappa=1.0, q_n=q_n, q_n_peak=q_n * F_PK,
            fw_area=g.firstwall_area, p_fus=float(pt.p_fus), p_th=float(pt.p_th),
            rec=float(pt.rec_frac), constr=float(p["construction_time_yr"]),
            drate=0.0, dmg=0.0, ddown=0.0,
            cas10=float(c.cas10), cas21=float(c.cas21), cas22=float(c.cas22),
            cas23=float(c.cas23), cas24=float(c.cas24), cas25=float(c.cas25),
            cas26=float(c.cas26), cas27=float(c.cas27), cas28=float(c.cas28),
            cas80=float(c.cas80),
            fw=gg("C220101"), shield=gg("C220102"), coil=gg("C220103"),
            heat=gg("C220104"), struct=gg("C220105"), vessel=gg("C220106"),
            power=gg("C220107"), divertor=gg("C220108"), rh=gg("C220110"),
            assembly=gg("C220111"), coolant=gg("C220200"), cryo=gg("C220300"),
            radwaste=gg("C220400"), fuelhandling=gg("C220500"),
            other22=gg("C220600"), iandc=gg("C220700"),
            rest22=float(c.cas22) - sum(gg(k) for k in keys),
            repl_event=gg("C220101") + gg("C220108"),
            lcoe_full=float(c.lcoe), capkw=float(c.capital_per_kw))

    m, r = run(PowerCycle.RANKINE, ETA_CPL[0], P)
    base = extract(m, r, P)

    def refix(cycle, cpl):
        lo, hi = 0.5 * P, 2.5 * P
        for _ in range(45):
            mid = 0.5 * (lo + hi)
            if float(run(cycle, cpl, mid)[1].power_table.p_fus) < base["p_fus"]:
                lo = mid
            else:
                hi = mid
        mm, rr = run(cycle, cpl, 0.5 * (lo + hi))
        return extract(mm, rr, P)

    print(f"{P:6.0f} MWe -> R0 {OP['R0']:5.2f} m  net {base['P']:6.1f}  "
          f"LCOE ${base['lcoe_full']:7.2f}  q_n {base['q_n']:.2f}/{base['q_n_peak']:.2f}  "
          f"recirc {base['rec']*100:4.1f}%", flush=True)
    return dict(rankine_base=base,
                sco2_fixed=refix(PowerCycle.BRAYTON_SCO2, ETA_CPL[0]),
                cpl_fixed=refix(PowerCycle.RANKINE, ETA_CPL[1]),
                both_fixed=refix(PowerCycle.BRAYTON_SCO2, ETA_CPL[1]))

rows = [make(P) for P in ANCHORS]
OUT = {"meta": dict(scale=ANCHORS, bmax=BMAX, q_n_peak=Q_PEAK,
                    nwl_peaking_factor=F_PK, av=AV, life=LIFE, wacc=WACC,
                    sizer="stellarator_sizer.py ISS04+Sudo+beta+wall-load",
                    note="cycle/coupling levers at FIXED geometry"),
       "data": {k: [r[k] for r in rows] for k in
                ("rankine_base", "sco2_fixed", "cpl_fixed", "both_fixed")}}
json.dump(OUT, open("stel_anchors_data.json", "w"), indent=1)
print("wrote stel_anchors_data.json")
