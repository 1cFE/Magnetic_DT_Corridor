"""Compact-tokamak corridor dataset, corrected model, FIXED-GEOMETRY levers.

Two changes from build_mature_corridor_data.py:

1. Scope. The downselect picked the conventional compact tokamak, so only that
   architecture is swept. 8 solves instead of 96.

2. The cycle and coupling levers no longer re-size the machine. Previously an
   eta_th or eta_couple improvement was spent shrinking the reactor to hold
   1 GWe net; now the geometry is pinned at the Rankine solution and the extra
   output is banked. Every other lever in the map was already fixed-geometry
   (they are cost multipliers and financial parameters), so this is the whole
   of the methodology change -- see the note in the artifact.

Model corrections carried in since the published dataset: cryo_temp_k now
drives cryoplant power, CAS21 buildings scale on bioshield envelope rather than
p_fus, the neutron wall-load cap is actually enforced (converged f_GW bisection
+ propagation into the forward pass), and first-wall life is charged on PEAK
wall load via nwl_peaking_factor.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _os.environ.get("COSTINGFE_SRC", "1costingfe/src"))
import json, math, sys
from costingfe import CostModel
from costingfe.types import ConfinementConcept as C, Fuel, PowerCycle
from costingfe.defaults import MAGNET_TABLE, MagnetProperties

F = Fuel.DT
AV, LIFE, WACC = 0.85, 30.0, 0.07
SCALE = [400, 600, 800, 1000, 1400, 2000, 2800, 4000]
BMAX, ASPECT = 23.0, 3.0
Q_N_MAX, F_PEAK = 3.36, 1.4          # NOAK: peak NWL 4.7 MW/m2 at 1.4 peaking
ETA_CPL = [0.8333, 0.95]
PER_MOD = {"C220101", "C220102", "C220103", "C220104", "C220105", "C220106",
           "C220107", "C220108", "C220109", "C220110", "C220112"}


def mag():
    MAGNET_TABLE["rebco_hts"] = MagnetProperties(
        b_max=BMAX, recirc_power_factor=0.0, cryo_temp_k=20.0)


def extract(m, r, n_mod, target):
    c, d, p, pt = r.costs, r.cas22_detail, r.params, r.power_table
    R0, a, kap = float(p["R0"]), float(p["plasma_t"]), float(p["elon"])
    fw_area = kap * 4 * math.pi ** 2 * R0 * (a + float(p.get("vacuum_t", 0.10)))
    q_n = float(pt.p_neutron) / fw_area
    drate = float(m._plasma_state.disruption_rate) if getattr(m, "_plasma_state", None) else 0.0

    def g(k):
        v = float(d.get(k, 0.0))
        return v * n_mod if k in PER_MOD else v
    return dict(
        P=float(pt.p_net) * n_mod, P_target=float(target), n_mod=int(n_mod),
        R0=R0, a=a, B=float(p["B"]), kappa=kap, T_e=float(p["T_e"]),
        n_e=float(p["n_e"]), f_GW=float(p["f_GW"]),
        plasma_volume=float(p["plasma_volume"]),
        constr=float(p["construction_time_yr"]),
        p_fus=float(pt.p_fus), p_th=float(pt.p_th), rec=float(pt.rec_frac),
        p_input=float(p["p_input"]), q_n=q_n, q_n_peak=q_n * F_PEAK,
        fw_area=fw_area, drate=drate,
        dmg=float(p.get("disruption_damage", 0.0)),
        ddown=float(p.get("disruption_downtime", 0.0)),
        cas10=float(c.cas10), cas21=float(c.cas21), cas22=float(c.cas22),
        cas23=float(c.cas23), cas24=float(c.cas24), cas25=float(c.cas25),
        cas26=float(c.cas26), cas27=float(c.cas27), cas28=float(c.cas28),
        cas80=float(c.cas80),
        fw=g("C220101"), shield=g("C220102"), coil=g("C220103"),
        heat=g("C220104"), struct=g("C220105"), vessel=g("C220106"),
        power=g("C220107"), divertor=g("C220108"), rh=g("C220110"),
        assembly=g("C220111"), coolant=g("C220200"), cryo=g("C220300"),
        radwaste=g("C220400"), fuelhandling=g("C220500"), other22=g("C220600"),
        iandc=g("C220700"),
        rest22=float(c.cas22) - sum(g(k) for k in (
            "C220101", "C220102", "C220103", "C220104", "C220105", "C220106",
            "C220107", "C220108", "C220110", "C220111", "C220200", "C220300",
            "C220400", "C220500", "C220600", "C220700")),
        repl_event=g("C220101") + g("C220108"),
        lcoe_full=float(c.lcoe), capkw=float(c.capital_per_kw))


BASE = dict(availability=AV, lifetime_yr=LIFE, interest_rate=WACC,
            q_n_max=Q_N_MAX, nwl_peaking_factor=F_PEAK)


def solve(P, cycle, eta_cpl):
    """Size the machine from its power target (Rankine baseline)."""
    mag()
    m = CostModel(C.TOKAMAK, F, power_cycle=cycle)
    r = m.forward(net_electric_mw=P, size_from_power=True, aspect_ratio=ASPECT,
                  eta_couple=eta_cpl, **BASE)
    n_mod = int(getattr(m, "_last_n_mod", 1) or 1)
    return m, r, n_mod


def _at(b, cycle, eta_cpl, pnet):
    mag()
    m = CostModel(C.TOKAMAK, F, power_cycle=cycle)
    r = m.forward(net_electric_mw=pnet, size_from_power=False,
                  aspect_ratio=ASPECT, eta_couple=eta_cpl,
                  R0=b["R0"], plasma_t=b["a"], elon=b["kappa"], B=b["B"],
                  T_e=b["T_e"], n_e=b["n_e"], f_GW=b["f_GW"],
                  plasma_volume=b["plasma_volume"], p_input=b["p_input"],
                  **BASE)
    return m, r


def refix(b, cycle, eta_cpl, P):
    """Re-evaluate at FIXED geometry: output floats, machine does not shrink.

    The bundled 0D physics model is not available in this release, so with
    size_from_power off the model takes net electric as GIVEN and back-solves
    P_fus. Requesting the same net under a better cycle therefore returns a
    smaller plasma -- the shrink this whole change exists to avoid. Instead,
    bisect the requested net until the back-solved P_fus matches the baseline's:
    same plasma, same geometry, and the net electric it now supports falls out.
    P_fus is monotone increasing in the requested net, so the bisection is well
    posed.
    """
    target = b["p_fus"]
    lo, hi = 0.5 * b["P"], 2.5 * b["P"]
    for _ in range(45):
        mid = 0.5 * (lo + hi)
        if float(_at(b, cycle, eta_cpl, mid)[1].power_table.p_fus) < target:
            lo = mid
        else:
            hi = mid
    m, r = _at(b, cycle, eta_cpl, 0.5 * (lo + hi))
    return extract(m, r, b["n_mod"], P)


DATA = {"rankine_base": [], "sco2_fixed": [], "cpl_fixed": [], "both_fixed": []}
for P in SCALE:
    m, r, n_mod = solve(P, PowerCycle.RANKINE, ETA_CPL[0])
    b = extract(m, r, n_mod, P)
    DATA["rankine_base"].append(b)
    DATA["sco2_fixed"].append(refix(b, PowerCycle.BRAYTON_SCO2, ETA_CPL[0], P))
    DATA["cpl_fixed"].append(refix(b, PowerCycle.RANKINE, ETA_CPL[1], P))
    DATA["both_fixed"].append(refix(b, PowerCycle.BRAYTON_SCO2, ETA_CPL[1], P))
    s = DATA["sco2_fixed"][-1]
    print(f"  {P:5d} MWe target -> R0 {b['R0']:5.2f} m  q_n {b['q_n']:4.2f} "
          f"(peak {b['q_n_peak']:4.2f})  net {b['P']:6.1f}  LCOE {b['lcoe_full']:7.2f}"
          f"   | sCO2 fixed-geom: net {s['P']:6.1f} (+{s['P']/b['P']*100-100:4.1f}%) "
          f"LCOE {s['lcoe_full']:7.2f}", flush=True)

OUT = {"meta": dict(scale=SCALE, bmax=BMAX, aspect=ASPECT, q_n_max=Q_N_MAX,
                    nwl_peaking_factor=F_PEAK, eta_couple=ETA_CPL,
                    av=AV, life=LIFE, wacc=WACC,
                    note="cycle/coupling levers evaluated at FIXED geometry"),
       "data": DATA}
json.dump(OUT, open("ct_corridor_data.json", "w"), indent=1)
print("\nwrote ct_corridor_data.json")
