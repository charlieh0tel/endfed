"""Does the table work at a frequency it never saw?

Every figure this repository quotes is in sample: the same sweeps fit the
table and measure it.  That is optimistic by construction and by an unknown
amount, and frequency is the axis where it matters, because the table has no
frequency index at all -- five coefficients against height and counterpoise
height, nothing else -- while the sweeps carry six frequencies and the page
serves ten bands.

So: drop one frequency, fit the whole pipeline on what is left, and measure
at the frequency that was held back.  The comparison that matters is against
the same measurement made in sample, because the question is not whether the
model is good but how much of its reported goodness is memory.

    uv run python holdout_check.py [--hold 14.175e6] [--sweep FILE]

No solver time: it refits from sweeps already on disk.
"""

import argparse
import sys

import numpy as np

from coefficients2d import (
    FLAT_TOP,
    TWO_D,
    fill_unsupported,
    fit_groups,
    load_sweeps,
    slices,
    refine,
    support,
)
from fit import model_zin
from nec_model import C
from table_spec import VF_A, Z_NODES
from table2d import build, look_up

SWEEP = "nec4_table_sweep.npz"

#: Interior frequencies, where dropping one leaves the h/lambda coverage
#: either side of it.  Holding out an end would test extrapolation, which is
#: a different and harder question than the page asks.
DEFAULT_HOLD_HZ = 14.175e6

#: The page's defaults, which is the decision the metric is about.
UNUN_RATIO = 9.0
TUNER_LIMIT = 3.0
Z_SYSTEM_OHMS = 50.0
MAX_GAMMA = 0.999999


def without(data, freq_hz):
    """The sweep with one frequency removed, and only that frequency."""
    keep = data["freq_hz"] != freq_hz
    return {
        field: values if field == "soil_names" else values[keep]
        for field, values in data.items()
    }


def only(data, freq_hz):
    keep = data["freq_hz"] == freq_hz
    return {
        field: values if field == "soil_names" else values[keep]
        for field, values in data.items()
    }


def fitted_table(data, geometry):
    """The shipped pipeline, over whatever data it is given."""
    groups = fit_groups(data, geometry)
    n_soils = len(data["soil_names"])
    table = build(groups, n_soils, "z_lam", Z_NODES, TWO_D)
    table, _runs = refine(table, data, geometry)
    counts = support(data, geometry, n_soils)
    table, _filled = fill_unsupported(table, counts)
    return table


def swr(z, ratio=UNUN_RATIO):
    at_radio = z / ratio
    gamma = np.abs((at_radio - Z_SYSTEM_OHMS) / (at_radio + Z_SYSTEM_OHMS))
    gamma = np.minimum(gamma, MAX_GAMMA)
    return (1.0 + gamma) / (1.0 - gamma)


def score(data, table, geometry, label):
    """Per-length error and miscall rate at one frequency."""
    model, nec = [], []
    for si in range(len(data["soil_names"])):
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
    model, nec = np.concatenate(model), np.concatenate(nec)
    factor = np.exp(np.abs(np.log(np.abs(model) / np.abs(nec))))
    says_ok = swr(model) <= TUNER_LIMIT
    miscall = float((says_ok & (swr(nec) > TUNER_LIMIT)).sum()) / max(
        float(says_ok.sum()), 1.0
    )
    print(
        f"{label:>28}  n={len(model):>7}  median x{np.median(factor):.3f}  "
        f"90th x{np.percentile(factor, 90):.3f}  "
        f"99th x{np.percentile(factor, 99):.3f}  miscall {miscall * 100:.1f}%"
    )
    return miscall


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--hold", type=float, default=DEFAULT_HOLD_HZ)
    parser.add_argument("--sweep", default=SWEEP)
    args = parser.parse_args()

    data = load_sweeps([args.sweep])
    held = args.hold
    if not (data["freq_hz"] == held).any():
        raise SystemExit(
            f"{held / 1e6:g} MHz is not in {args.sweep}: "
            f"{sorted(set(np.round(np.unique(data['freq_hz']) / 1e6, 3)))}"
        )
    print(f"{args.sweep}, holding out {held / 1e6:g} MHz\n")

    print("in sample, the table as it ships:")
    shipped = fitted_table(data, FLAT_TOP)
    at_held_in = score(only(data, held), shipped, FLAT_TOP, f"{held / 1e6:g} MHz")
    score(data, shipped, FLAT_TOP, "every frequency")

    print("\nout of sample, fitted without it:")
    reduced = fitted_table(without(data, held), FLAT_TOP)
    at_held_out = score(only(data, held), reduced, FLAT_TOP, f"{held / 1e6:g} MHz")
    score(without(data, held), reduced, FLAT_TOP, "the frequencies it saw")

    print(
        f"\nmiscall at {held / 1e6:g} MHz: {at_held_in * 100:.1f}% having seen it, "
        f"{at_held_out * 100:.1f}% not.  "
        f"The gap is what being in sample is worth."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
