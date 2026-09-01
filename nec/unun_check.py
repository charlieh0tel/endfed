"""What the ideal-unun assumption costs, against the page's own loads.

The page divides the modeled feedpoint impedance by the unun ratio and
calls that the radio's load.  A real unun is an autotransformer on a
ferrite core with a magnetizing branch (complex, lossy: #43 material's
mu'' is comparable to mu' across HF), leakage inductance, and winding
capacitance.  This models the two standard builds:

    49:1  2:14 turns on one FT240-43, 100 pF compensation across the
          primary (the common EFHW commercial design)
    9:1   3:9 turns on an FT140-43, uncompensated (the common random
          wire design)

and compares, over the same length x band grid the page scores
(flat top at the page defaults, lengths 20 to 250 ft), the SWR the
radio would actually see against the ideal division, plus the core
loss.  Feedpoint impedances come from the shipped tables via the
shipped code, read-only.

Parameters are typical-curve values, not measurements of one unit:
#43 complex permeability read from Fair-Rite's published curves
(+/-30 percent is realistic between lots), leakage from published
measurements of crossover-wound 2:14 FT240-43 builds (Owen Duffy,
KN5L), winding C an estimate.  A sensitivity pass scales mu'' and
leakage +/-30 percent.

    uv run python unun_check.py
"""

import json
import sys
from pathlib import Path

import numpy as np

from fit import model_zin
from table2d import look_up
from table_spec import VF_A, Z_NODES, length_power
from nec_model import C

FT = 0.3048
Z_SYSTEM = 50.0
MAX_GAMMA = 0.999999

#: Fair-Rite #43 complex permeability, read from the datasheet curves.
#: (f MHz, mu', mu'').  Initial permeability 800.
MU_43 = {
    1.85: (700.0, 150.0),
    3.75: (550.0, 300.0),
    5.35: (450.0, 360.0),
    7.15: (350.0, 380.0),
    10.14: (250.0, 350.0),
    14.18: (180.0, 320.0),
    18.12: (140.0, 290.0),
    21.22: (120.0, 270.0),
    24.94: (100.0, 250.0),
    28.85: (90.0, 230.0),
}
MU_I = 800.0

#: Inductance factor per turn-squared at initial permeability, henries.
A_L = {"FT240-43": 1075e-9, "FT140-43": 885e-9}

#: The two builds.  Leakage is referred to the secondary; the
#: compensation capacitor sits across the primary (feedpoint side of the
#: coax).  Winding capacitance shunts the secondary.
BUILDS = {
    49.0: {
        "core": "FT240-43",
        "n_primary": 2,
        "n_secondary": 14,
        "leak_secondary_h": 4.0e-6,
        "c_comp_f": 100e-12,
        "c_winding_f": 1.5e-12,
    },
    9.0: {
        "core": "FT140-43",
        "n_primary": 3,
        "n_secondary": 9,
        "leak_secondary_h": 1.0e-6,
        "c_comp_f": 0.0,
        "c_winding_f": 1.0e-12,
    },
}


def mu_complex(freq_hz):
    """mu' - j mu'' at the sweep frequencies, interpolated in log f."""
    fs = np.array(sorted(MU_43))
    mp = np.array([MU_43[f][0] for f in fs])
    ms = np.array([MU_43[f][1] for f in fs])
    lf = np.log(freq_hz / 1e6)
    return np.interp(lf, np.log(fs), mp) - 1j * np.interp(lf, np.log(fs), ms)


def through_unun(z_load, freq_hz, build, mu_scale=1.0, leak_scale=1.0):
    """(Zin at the radio, efficiency) through the real transformer.

    Autotransformer treated as an ideal n:1 with the parasitics hung on:
    magnetizing branch across the primary from the primary turns' core
    impedance, leakage in series on the secondary, winding C across the
    load, compensation C across the primary.
    """
    w = 2 * np.pi * freq_hz
    mu = mu_complex(freq_hz)
    mu = np.real(mu) + 1j * np.imag(mu) * mu_scale
    n = build["n_secondary"] / build["n_primary"]
    l0 = A_L[build["core"]] / MU_I  # per turn-squared, at mu = 1
    z_mag = 1j * w * build["n_primary"] ** 2 * l0 * mu
    z_leak = 1j * w * build["leak_secondary_h"] * leak_scale
    y_wind = 1j * w * build["c_winding_f"]
    # Secondary side: load with winding C across it, leakage in series.
    z_sec = 1.0 / (1.0 / z_load + y_wind) + z_leak
    z_reflected = z_sec / n**2
    y_in = 1.0 / z_mag + 1.0 / z_reflected
    if build["c_comp_f"] > 0:
        y_in = y_in + 1j * w * build["c_comp_f"]
    z_in = 1.0 / y_in
    # Powers for unit primary voltage: core loss in Re(1/z_mag), the
    # rest divides between leakage (lossless) and the load branch.
    p_in = np.real(1.0 / np.conj(z_in))
    i_branch = 1.0 / z_reflected  # current into the reflected branch
    v_load_branch = 1.0  # primary volts; scale cancels in the ratio
    p_branch = np.real(v_load_branch * np.conj(i_branch))
    # Within the branch everything real is the load (leakage and C are
    # reactive), so branch power is load power.
    efficiency = np.where(p_in > 0, p_branch / p_in, np.nan)
    return z_in, efficiency


def swr(z):
    gamma = np.abs((z - Z_SYSTEM) / (z + Z_SYSTEM))
    gamma = np.minimum(gamma, MAX_GAMMA)
    return (1 + gamma) / (1 - gamma)


def feedpoint_grid():
    """The page's default flat top over its length map, per band."""
    stored = json.loads(
        (Path(__file__).resolve().parent / "coefficients2d.json").read_text()
    )
    table = np.array(stored["flat_top"]["table"])
    si = [str(s) for s in stored["soils"]].index("average")
    height_m = 9.144
    z_m = 0.02
    return_m = 7.62
    lengths_m = np.linspace(20 * FT, 250 * FT, 200)
    bands = {}
    for f_mhz in (1.85, 3.75, 7.15, 10.14, 14.18, 21.22, 28.85):
        freq_hz = f_mhz * 1e6
        lam = C / freq_hz
        h_lam = height_m / lam
        alpha_a, ka, alpha_r, vf_r, kr = look_up(table, si, h_lam, Z_NODES, z_m / lam)
        z = model_zin(
            (alpha_a, VF_A, ka, alpha_r, vf_r, kr),
            lengths_m,
            np.full_like(lengths_m, (height_m - z_m) + return_m),
            lam,
            power=length_power(h_lam),
        )
        bands[f_mhz] = (lengths_m, z)
    return bands


def main():
    bands = feedpoint_grid()
    for ratio, build in BUILDS.items():
        print(
            f"\n{ratio:g}:1 as {build['n_primary']}:{build['n_secondary']} "
            f"on {build['core']}"
            + (
                f", {build['c_comp_f'] * 1e12:.0f} pF compensation"
                if build["c_comp_f"]
                else ", uncompensated"
            )
        )
        print(
            f"{'MHz':>6} {'ideal SWR med':>14} {'real SWR med':>13} "
            f"{'flip %':>7} {'loss dB med':>12} {'worst dB':>9}"
        )
        for f_mhz, (lengths_m, z_load) in bands.items():
            freq_hz = f_mhz * 1e6
            ideal = swr(z_load / ratio)
            z_real, eff = through_unun(z_load, freq_hz, build)
            real = swr(z_real)
            ok_i, ok_r = ideal <= 3.0, real <= 3.0
            flip = 100.0 * np.mean(ok_i != ok_r)
            loss_db = -10 * np.log10(np.clip(eff, 1e-6, 1))
            print(
                f"{f_mhz:6.2f} {np.median(ideal):14.2f} "
                f"{np.median(real):13.2f} {flip:7.1f} "
                f"{np.median(loss_db):12.2f} {np.max(loss_db):9.2f}"
            )
        # Aggregate verdict damage and sensitivity.
        all_ideal, all_real, all_hi, all_lo = [], [], [], []
        for f_mhz, (lengths_m, z_load) in bands.items():
            freq_hz = f_mhz * 1e6
            all_ideal.append(swr(z_load / ratio))
            all_real.append(swr(through_unun(z_load, freq_hz, build)[0]))
            all_hi.append(
                swr(
                    through_unun(z_load, freq_hz, build, mu_scale=1.3, leak_scale=1.3)[
                        0
                    ]
                )
            )
            all_lo.append(
                swr(
                    through_unun(z_load, freq_hz, build, mu_scale=0.7, leak_scale=0.7)[
                        0
                    ]
                )
            )
        ideal = np.concatenate(all_ideal)
        real = np.concatenate(all_real)
        hi = np.concatenate(all_hi)
        lo = np.concatenate(all_lo)
        for name, r in (("typical", real), ("+30%", hi), ("-30%", lo)):
            flip = 100.0 * np.mean((ideal <= 3.0) != (r <= 3.0))
            said_ok = ideal <= 3.0
            wrong = 100.0 * np.mean(r[said_ok] > 3.0) if said_ok.any() else 0
            print(
                f"  {name:>8}: verdict flips {flip:4.1f}% of the map; "
                f"of lengths called ok, {wrong:4.1f}% read over 3:1 through "
                f"the real transformer"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
