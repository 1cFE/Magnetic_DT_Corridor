# Magnetic D-T Corridor

Techno-economic analysis of the mature magnetic D-T fusion corridor: a stellarator
archetype costed bottom-up on [1costingFE](https://github.com/1cFE/1costingfe), with an
evidence-tier LCOE ladder and single-lever sensitivity.

This is the analysis code behind the 1cFE dispatch *Mature Magnetic D-T Corridor*.

## Result

A mature D-T magnetic plant does not reach 1 ¢/kWh. It reaches **2.5 ¢/kWh**, and only
on assumptions with no mechanism behind them.

| Evidence tier | 1 GWe | 3 GWe |
|---|---|---|
| 0 · design basis | $227.5 | $202.5 |
| 1 · applicable record | $154.9 | $140.8 |
| 2 · extrapolation with a known mechanism | $43.1 | $42.7 |
| 3 · speculation, no mechanism | **$25.2** | **$24.8** |

LCOE in $/MWh. Tiers are cumulative — each carries every entry below it. The 1 ¢/kWh
target is $10/MWh.

## Reproducing

The analysis runs against a specific 1costingFE commit plus a patch. The patch carries
model changes that are not on `master`; see [Why a patch](#why-a-patch) below.

```bash
git clone https://github.com/1cFE/1costingfe
git clone https://github.com/1cFE/Magnetic_DT_Corridor

cd 1costingfe
git checkout 4c7f0df
git apply ../Magnetic_DT_Corridor/costingfe-mature-corridor.patch
cd ../Magnetic_DT_Corridor

export COSTINGFE_SRC=../1costingfe/src      # Windows: set COSTINGFE_SRC=..\1costingfe\src

python build_stel_anchors.py                # solve the stellarator at 1 and 3 GWe
python build_ct_corridor.py                 # compact-tokamak reference sweep
python corridor_tiers.py                    # evidence ladder -> corridor_tiers.json
python tier_ladder_figs.py                  # figures/*_tier_ladder.png
python stel_tornado_plot.py                 # figures/stel_tornado.png
```

`build_stel_anchors.py` should print:

```
  1000 MWe -> R0  9.62 m  net 1000.0  LCOE $ 227.46  q_n 2.37/4.73  recirc  8.3%
  3000 MWe -> R0 16.49 m  net 3000.0  LCOE $ 202.53  q_n 2.38/4.76  recirc  4.8%
```

The committed `*.json` datasets are the ones the published figures were drawn from, so
the figure scripts run standalone without re-solving the machines.

## What each file does

| File | Role |
|---|---|
| `stellarator_sizer.py` | Stellarator 0D solve: ISS04 confinement, Sudo density limit, beta limit, neutron wall-load cap. Bisects major radius against a net-electric target. |
| `build_stel_anchors.py` | Runs the sizer at 1 and 3 GWe and costs each point in 1costingFE. Writes `stel_anchors_data.json`. |
| `build_ct_corridor.py` | Compact-tokamak reference sweep. Writes `ct_corridor_data.json`. |
| `ct_tornado.py` | Reduced cost model over the exported CAS accounts, plus the lever definitions. Reproduces the full 1costingFE LCOE at baseline to the cent. |
| `corridor_tiers.py` | Applies the evidence-tier ladder. Writes `corridor_tiers.json`. |
| `tier_ladder_figs.py` | The cumulative tier-ladder bar charts. |
| `stel_tornado_plot.py` | Single-lever sensitivity: each cost-down lever from the tier-0 basis to its deepest tier. |
| `stel_tornado_symmetric.py` | Two-sided version — each lever moved by the same factor in both directions, showing that LCOE is convex in nearly every input. |

## Why a patch

The published numbers were produced against a 1costingFE working tree that carries
changes not merged to `master`. Rather than push those changes upstream, they are
vendored here so the analysis reproduces exactly. The patch touches eight files and
contains four independent groups:

- **`nwl_peaking_factor`** — a neutron-wall-load peaking factor applied to `q_n`, used
  here at 2.0 because Φ_max is anchored to the ARIES *peak* wall loading while the model
  computes a plant average. Without it the first-wall life model cannot be reproduced;
  `forward()` rejects the parameter on `master`.
- **Spherical-tokamak support** — `path_factor` 0.80 and a coil markup for the ST
  concept. Used only for the appendix note on why the ST coil cost is a lower bound.
- **CAS21 buildings rescale** — reactor building and hot cell keyed to the machine
  envelope rather than fusion power, rebased so the D-T reference plant's CAS21 is
  unchanged.
- **Laser-IFE driver terms** — KrF `$/J` raised to a published NOAK figure, and an
  uncalibrated gas-laser rep-rate BoP penalty. These affect the pulsed corridor only and
  do not enter any number in this repository.

On unpatched `master` the ladder lands about 2% lower at tier 0 (222.9 against 227.5)
and the floor is 2.49 ¢/kWh rather than 2.52 — the difference comes from a slightly
smaller coil bore in the radial build and the buildings rescale, not from the physics.

## Scope and limits

- The cost model prices conductor **quantity** only: no current-density limit, no
  structural term, and ampere-meters evaluated at the on-axis rather than the peak field.
- The stellarator coil account carries two compounding constants — a 2.0 coil-path
  multiplier and a ~1.9× manufacturing markup, together ~3.8 — and **neither has been
  calibrated against a built stellarator**. This is the largest and least secure number
  in the analysis.
- First-wall fluence enters replacement cost only. The model does not couple it to
  availability, so a longer-lived wall buys no additional uptime here.
- No tritium-breeding calculation of any kind; the omission of an inboard breeding
  blanket registers as a cost saving rather than a liability.

## Contact

Questions or challenges to the assumptions and methodology are welcome at
[1cf.energy/contact](https://1cf.energy/contact).
