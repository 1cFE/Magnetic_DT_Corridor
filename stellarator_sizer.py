"""Size a stellarator from its power target, the way 1costingFE sizes a tokamak.

The tokamak solve bisects R0 against IPB98(y,2) confinement, the Greenwald
density limit and the Troyon beta limit, with B0 set by the inboard radial build.
This is the stellarator analogue, with each ingredient swapped for its
stellarator counterpart:

  confinement     ISS04 (Yamada 2005) instead of IPB98(y,2)
  density limit   Sudo instead of Greenwald
  beta limit      a flat beta_max (stellarators are beta- not current-limited)
  field           B0 = B_max / f_coil instead of the inboard 1/R build

f_coil is the peak-on-conductor to on-axis field ratio. A stellarator's modular
coils are non-planar and sit close to the plasma, so this is worse than a
tokamak's: published reactor designs sit at roughly 2.1 (HELIAS-5B, B0 5.9 T)
to 2.65 (ARIES-CS, B0 5.7 T). 2.4 is used as the central value.

Published design points this is calibrated against:
  ARIES-CS    R0 7.5 m,  A 4.5,  B0 5.7 T,  beta 6.5%,  ~2.4 GW fusion,  1 GWe
  HELIAS-5B   R0 22 m,   A 12.2, B0 5.9 T,  3 GW fusion,  1.3 m plasma-coil gap
  HSR4/18     R0 18 m,   A 8.6,  B0 5.0 T
  FFHR-d1     R0 15.6 m, A ~6.2, B0 4.7 T,  V_p 2000 m3, 3 GW fusion
  SPPS        R0 14 m,   A ~8.8, B0 5.0 T
  FFHR-c1     R0 10.9 m,          B0 7.3 T  (compact, high-field variant)
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _os.environ.get("COSTINGFE_SRC", "1costingfe/src"))
import math

EV = 1.602176634e-19
MU0 = 4 * math.pi * 1e-7
E_FUS_DT_J = 17.58e6 * EV


def sigv_dt(T_keV):
    """Bosch-Hale D-T reactivity [m^3/s]; same form the framework uses."""
    from costingfe.layers.reactivity import sigv_dt as _s
    return float(_s(T_keV))


def tau_iss04(a, R, P_MW, n_e19, B, iota, f_ren):
    return (f_ren * 0.134 * a ** 2.28 * R ** 0.64 * P_MW ** -0.61
            * n_e19 ** 0.54 * B ** 0.84 * iota ** 0.41)


def n_sudo(P_MW, B, a, R):
    """Sudo density limit [10^20 m^-3] -- the stellarator's Greenwald."""
    return 0.25 * math.sqrt(P_MW * B / (a ** 2 * R))


def operating_point(R0, A, B0, T_keV, iota, f_ren, beta_max, kappa=1.0,
                    mn=1.115, eta_th=0.40, eta_pin=0.50, f_sub=0.03,
                    fixed_recirc=31.2, q_n_max=None, f_limit=0.85):
    """Self-consistent 0D point at fixed geometry and temperature.

    Density is the lower of the Sudo and beta limits; both depend on the heating
    power, which depends on the density, so the pair is iterated to convergence.
    """
    a = R0 / A
    V = 2 * math.pi ** 2 * R0 * a ** 2 * kappa
    n_beta = beta_max * B0 ** 2 / (4 * MU0 * T_keV * 1e3 * EV) / 1e20  # 1e20 m^-3
    # Neutron wall loading is the third density cap, and at high field it is the
    # binding one: P_fus goes as n^2 V while the first-wall area goes as R0*a, so
    # a small high-field machine hits the wall-load limit long before it runs out
    # of beta. Without this the solver returns geometrically tiny reactors that
    # no first wall could survive.
    n_wall = float("inf")
    if q_n_max:
        fw_area = 4 * math.pi ** 2 * R0 * a * kappa
        p_fus_cap = q_n_max * fw_area / 0.8          # 80% of fusion power is neutrons
        n_wall = math.sqrt(4 * p_fus_cap * 1e6
                           / (sigv_dt(T_keV) * E_FUS_DT_J * V)) / 1e20
    n20, P_heat = min(n_beta, n_wall), 100.0
    for _ in range(200):
        # the tokamak solves run at f_GW = 0.85 of the Greenwald limit, so the
        # stellarator runs at the same fraction of its Sudo limit
        n20 = min(n_beta, n_wall, f_limit * n_sudo(P_heat, B0, a, R0))
        n_e = n20 * 1e20
        W_MJ = 3.0 * n_e * T_keV * 1e3 * EV * V / 1e6
        K = tau_iss04(a, R0, 1.0, n20 * 10, B0, iota, f_ren)   # tau at P = 1 MW
        P_new = (W_MJ / K) ** (1.0 / (1.0 - 0.61))
        if abs(P_new - P_heat) < 1e-6 * max(P_heat, 1.0):
            P_heat = P_new
            break
        P_heat = 0.5 * (P_heat + P_new)
    n_e = n20 * 1e20
    P_fus = 0.25 * n_e * n_e * sigv_dt(T_keV) * E_FUS_DT_J * V / 1e6
    P_alpha = P_fus / 5.0
    P_aux = max(0.0, P_heat - P_alpha)
    P_th = P_fus * mn
    P_et = eta_th * P_th
    recirc = P_aux / eta_pin + fixed_recirc + f_sub * P_et
    beta = 2 * MU0 * (2 * n_e * T_keV * 1e3 * EV) / B0 ** 2
    fw_area = 4 * math.pi ** 2 * R0 * a * kappa
    return dict(R0=R0, a=a, V=V, n20=n20, T=T_keV, B0=B0, beta=beta,
                fw_area=fw_area, q_n=0.8 * P_fus / fw_area,
                binding=("wall" if n20 >= n_wall - 1e-9 else
                         "beta" if n20 >= n_beta - 1e-9 else "Sudo"),
                W_MJ=W_MJ, tau_E=W_MJ / P_heat, P_heat=P_heat, P_fus=P_fus,
                P_alpha=P_alpha, P_aux=P_aux, P_th=P_th, P_et=P_et,
                P_net=P_et - recirc, recirc_frac=recirc / P_et,
                n_sudo=n_sudo(P_heat, B0, a, R0), n_beta=n_beta)


def best_T(R0, A, B0, iota, f_ren, beta_max, T_lo=8.0, T_hi=30.0, n=45,
           q_n_max=None, f_limit=0.85):
    """Temperature that maximises net electric at this geometry."""
    best = None
    for i in range(n):
        T = T_lo + (T_hi - T_lo) * i / (n - 1)
        op = operating_point(R0, A, B0, T, iota, f_ren, beta_max,
                             q_n_max=q_n_max, f_limit=f_limit)
        if best is None or op["P_net"] > best["P_net"]:
            best = op
    return best


def size_from_power(target_MWe, A, B_max, f_coil, iota, f_ren, beta_max,
                    R_lo=4.0, R_hi=30.0, q_n_max=None, f_limit=0.85):
    """Bisect R0 so net electric hits the target, exactly as the tokamak solve
    does. Net power is monotone in R0 over this range."""
    B0 = B_max / f_coil
    hi = best_T(R_hi, A, B0, iota, f_ren, beta_max, q_n_max=q_n_max, f_limit=f_limit)
    if hi["P_net"] < target_MWe:
        return None
    for _ in range(70):
        mid = 0.5 * (R_lo + R_hi)
        if best_T(mid, A, B0, iota, f_ren, beta_max, q_n_max=q_n_max,
                  f_limit=f_limit)["P_net"] < target_MWe:
            R_lo = mid
        else:
            R_hi = mid
    return best_T(0.5 * (R_lo + R_hi), A, B0, iota, f_ren, beta_max,
                  q_n_max=q_n_max, f_limit=f_limit)


if __name__ == "__main__":
    import sys
    print("=" * 84)
    print("VALIDATION — reproduce published design points with their own B0")
    print("=" * 84)
    print(f"  {'design':<12}{'R0 pub':>8}{'B0':>6}{'A':>6}{'P_fus pub':>11}"
          f"{'P_fus model':>13}{'beta':>7}{'n20':>7}{'T':>6}")
    for nm, R0, A, B0, pf in (("ARIES-CS", 7.5, 4.5, 5.7, 2400),
                              ("HELIAS-5B", 22.0, 12.2, 5.9, 3000),
                              ("FFHR-d1", 15.6, 6.2, 4.7, 3000),
                              ("SPPS", 14.0, 8.8, 5.0, 1730)):
        op = best_T(R0, A, B0, iota=1.0, f_ren=1.0, beta_max=0.05)
        print(f"  {nm:<12}{R0:8.1f}{B0:6.1f}{A:6.1f}{pf:11.0f}"
              f"{op['P_fus']:13.0f}{op['beta']*100:6.1f}%{op['n20']:7.2f}{op['T']:6.1f}")

    print()
    print("=" * 84)
    print("SIZED FROM POWER — 1 GWe net, ISS04 + Sudo + beta limit")
    print("=" * 84)
    print(f"  {'B_max':>6}{'f_coil':>7}{'B0':>6}{'A':>5}{'f_ren':>6}{'q_cap':>6}{'R0':>7}{'a':>6}"
          f"{'V':>8}{'n20':>6}{'T':>6}{'beta':>6}{'tau_E':>6}{'P_fus':>8}{'q_n':>6}"
          f"{'P_aux':>7}{'recirc':>7}{'limit':>6}")
    for B_max, f_coil, A, f_ren, qc in ((14.0, 2.4, 4.5, 1.0, None),
                                        (23.0, 2.4, 4.5, 1.0, None),
                                        (23.0, 2.4, 4.5, 1.0, 2.5),
                                        (23.0, 2.4, 4.5, 1.2, 2.5),
                                        (23.0, 2.1, 4.5, 1.0, 2.5),
                                        (23.0, 2.65, 4.5, 1.0, 2.5),
                                        (23.0, 2.4, 8.0, 1.0, 2.5)):
        op = size_from_power(1000.0, A, B_max, f_coil, iota=1.0, f_ren=f_ren,
                             beta_max=0.05, q_n_max=qc)
        if op is None:
            print(f"  {B_max:6.1f}{f_coil:8.2f}{B_max/f_coil:6.2f}{A:5.1f}{f_ren:7.2f}"
                  f"   infeasible at any R0 <= 30 m")
            continue
        print(f"  {B_max:6.1f}{f_coil:7.2f}{op['B0']:6.2f}{A:5.1f}{f_ren:6.2f}"
              f"{('-' if qc is None else f'{qc:.1f}'):>6}"
              f"{op['R0']:7.2f}{op['a']:6.2f}{op['V']:8.0f}{op['n20']:6.2f}{op['T']:6.1f}"
              f"{op['beta']*100:5.1f}%{op['tau_E']:6.2f}{op['P_fus']:8.0f}{op['q_n']:6.2f}"
              f"{op['P_aux']:7.1f}{op['recirc_frac']*100:6.1f}%{op['binding']:>6}")
