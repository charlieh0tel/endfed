"""How often does the page call a length usable when NEC says it is not?

The page ranks lengths and keeps users off bad ones.  The error figures it
carries are about |Z|, which is not the question a user asks: they ask
whether a length will match through their tuner.  This measures that
directly.

For every swept point the shipped table is evaluated at the same geometry,
both impedances are taken through the unun to SWR at the radio, and the two
are compared against each tuner's limit.  A miscall is a length the model
calls acceptable and NEC does not; the reverse -- calling a good length bad
-- costs the user a length rather than a match, and is reported separately.

    uv run python miscall_check.py [sweep.npz ...]

Per tuner limit, per unun ratio, per band, both geometries.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from coefficients2d import FLAT_TOP, SLOPER, load_sweeps, slices
from fit import model_zin
from nec_model import C
from table_spec import VF_A, Z_NODES
from table2d import look_up

DATA = Path(__file__).resolve().parent / "coefficients2d.json"

FLAT_TOP_SWEEPS = (
    "nec4_return_height_sweep.npz",
    "nec4_node_fill_sweep.npz",
    "nec4_domain_sweep.npz",
)
SLOPER_SWEEPS = ("nec4_sloper_sweep.npz", "nec4_domain_sloper_sweep.npz")

#: The page's own controls.
TUNER_LIMITS = {
    "rig 3:1": 3.0,
    "compact 5:1": 5.0,
    "wide 9:1": 9.0,
    "roller 12:1": 12.0,
}
UNUN_RATIOS = (1, 4, 9, 49, 64)
Z_SYSTEM_OHMS = 50.0

#: A perfectly reflecting load would divide by zero, as the page's own
#: MAX_GAMMA guards against.
MAX_GAMMA = 0.999999

#: Bands, to say where the misses fall.  Edges as the page has them.
BANDS_M = {
    160: (1.8e6, 2.0e6),
    80: (3.5e6, 4.0e6),
    60: (5.3515e6, 5.3665e6),
    40: (7.0e6, 7.3e6),
    30: (10.1e6, 10.15e6),
    20: (14.0e6, 14.35e6),
    17: (18.068e6, 18.168e6),
    15: (21.0e6, 21.45e6),
    12: (24.89e6, 24.99e6),
    10: (28.0e6, 29.7e6),
}


def swr(z, ratio):
    """SWR at the radio, through an ideal unun, as the page computes it.

    z is complex: an end-fed feedpoint is reactive nearly everywhere, and
    taking |Z| as if it were a resistance is a different, kinder question
    than the one the page answers.
    """
    at_radio = z / ratio
    gamma = np.abs((at_radio - Z_SYSTEM_OHMS) / (at_radio + Z_SYSTEM_OHMS))
    gamma = np.minimum(gamma, MAX_GAMMA)
    return (1.0 + gamma) / (1.0 - gamma)


def band_of(freq_hz):
    for metres, (lo, hi) in BANDS_M.items():
        if lo <= freq_hz <= hi:
            return metres
    return None


def paired(sweeps, geometry, table, soil_names):
    """Model and NEC impedance for every swept point, with its frequency."""
    data = load_sweeps(list(sweeps))
    model, nec, freqs = [], [], []
    for si in range(len(soil_names)):
        for h_lam, z_lam, length_m, total_return_m, wavelength_m, z_nec in slices(
            data, si, geometry
        ):
            alpha_a, ka, alpha_r, vf_r, kr = look_up(table, si, h_lam, Z_NODES, z_lam)
            model.append(
                model_zin(
                    (alpha_a, VF_A, ka, alpha_r, vf_r, kr),
                    length_m,
                    total_return_m,
                    wavelength_m,
                )
            )
            nec.append(z_nec)
            freqs.append(np.full(len(length_m), C / wavelength_m))
    return (
        np.concatenate(model),
        np.concatenate(nec),
        np.concatenate(freqs),
    )


def report(name, model, nec):
    """Miscall rates for one geometry."""
    print(f"\n=== {name}: {len(model)} points ===")
    print(
        f"{'unun':>6} {'tuner':>12} {'model says ok':>14} {'of those wrong':>16} "
        f"{'good called bad':>16}"
    )
    worst = 0.0
    for ratio in UNUN_RATIOS:
        model_swr, nec_swr = swr(model, ratio), swr(nec, ratio)
        for label, limit in TUNER_LIMITS.items():
            says_ok = model_swr <= limit
            really_ok = nec_swr <= limit
            if not says_ok.any():
                continue
            miscall = float((says_ok & ~really_ok).sum()) / float(says_ok.sum())
            missed = (
                float((~says_ok & really_ok).sum()) / float(really_ok.sum())
                if really_ok.any()
                else 0.0
            )
            worst = max(worst, miscall)
            print(
                f"{ratio:>5}:1 {label:>12} {says_ok.mean() * 100:13.1f}% "
                f"{miscall * 100:15.1f}% {missed * 100:15.1f}%"
            )
    return worst


def by_band(name, model, nec, freqs, ratio, limit):
    """Where the misses fall, for one representative setting."""
    model_swr, nec_swr = swr(model, ratio), swr(nec, ratio)
    says_ok, really_ok = model_swr <= limit, nec_swr <= limit
    print(f"\n{name}, {ratio}:1 into a {limit:g}:1 tuner, by band:")
    print(f"{'band':>6} {'points':>8} {'model says ok':>14} {'of those wrong':>16}")
    for metres, (lo, hi) in BANDS_M.items():
        sel = (freqs >= lo) & (freqs <= hi)
        if not sel.any():
            continue
        ok = says_ok[sel]
        if not ok.any():
            print(f"{metres:>5}m {int(sel.sum()):>8} {0.0:13.1f}% {'-':>16}")
            continue
        wrong = float((ok & ~really_ok[sel]).sum()) / float(ok.sum())
        print(
            f"{metres:>5}m {int(sel.sum()):>8} {ok.mean() * 100:13.1f}% "
            f"{wrong * 100:15.1f}%"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("sweeps", nargs="*", help="override the flat-top sweeps")
    args = parser.parse_args()

    stored = json.loads(DATA.read_text())
    soils = [str(s) for s in stored["soils"]]

    print("the shipped table against the sweeps it was fitted from")
    print("a miscall is a length the model calls usable and NEC does not")

    flat = paired(
        args.sweeps or FLAT_TOP_SWEEPS,
        FLAT_TOP,
        np.array(stored["flat_top"]["table"]),
        soils,
    )
    worst = report("flat top", flat[0], flat[1])
    by_band("flat top", *flat, 9, 3.0)

    if not args.sweeps:
        sloper = paired(
            SLOPER_SWEEPS, SLOPER, np.array(stored["sloper"]["table"]), soils
        )
        worst = max(worst, report("sloper", sloper[0], sloper[1]))
        by_band("sloper", *sloper, 9, 3.0)

    print(f"\nworst miscall rate over every setting: {worst * 100:.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
