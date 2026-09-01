"""Does a length-resolved line fix the half-wave peaks?

The shipped model drives one averaged characteristic impedance,
`Z0 = 60 (ln(2l/a) - 1)`, through `coth(gamma l)`.  Schelkunoff's picture
behind that average is a nonuniform line whose local `Z0(x)` grows
logarithmically with distance from the feed [Schelkunoff, "Theory of
Antennas of Arbitrary Size and Shape", Proc. IRE 1941]; averaging it
away is the suspect behind the x1.86 first half-wave peak in
docs/MODEL.md ("The peaks are too sharp"): a uniform open line's peak
height is set entirely by `Z0 / (alpha l)`, so one averaged `Z0` has no
way to soften the first peak without wrecking the rest.

This fits each group twice with the same six parameters:

    uniform    the shipped form, `ka * Z0(l) * coth(gamma l)`
    tapered    a cascade of short uniform segments with local
               `Z0(x) = ka * 60 (ln(2x/a) - 1)`, open at the far end

and compares them on what the page is judged by -- per-length error and
the miscall rate -- plus the same statistics on each group's top-decile
`|Z|` rows, which is where the peaks live.  Equal parameter counts, so
in-sample improvement is evidence about the form.

    uv run python peak_form_check.py [--groups N]
"""

import argparse
import sys

import numpy as np
from scipy.optimize import least_squares

from alpha_length_check import POWER_BOUNDS, POWER_INITIAL, report
from coefficients2d import FLAT_TOP, SLOPER, load_sweeps, slices
from fit import (
    BOUNDS,
    CASCADE_SEGMENTS,
    INITIAL,
    PARAM_NAMES,
    schelkunoff_z0,
    tapered_zin,
)
from nec_model import WIRE_RADIUS_M

SWEEP = "nec4_table_sweep_extrapolated.npz"


def model_zin(params, length_m, total_return_m, wavelength_m, tapered):
    """The two-line model; `tapered` swaps only the antenna line's form.

    A seventh parameter, if given, is the falling-loss exponent the page
    ships as `length_power`, here free per group: if the taper leaves it
    fitting at zero, the taper subsumes the ramp.
    """
    alpha_a_lam, vf_a, ka, alpha_r_lam, vf_r, kr = params[:6]
    power = params[6] if len(params) > 6 else 0.0
    alpha_a = alpha_a_lam * (length_m / wavelength_m) ** -power / wavelength_m
    beta_a = 2.0 * np.pi / (wavelength_m * vf_a)
    if tapered:
        za = tapered_zin(length_m, WIRE_RADIUS_M, ka, alpha_a, beta_a)
    else:
        za = (ka * schelkunoff_z0(length_m, WIRE_RADIUS_M)) / np.tanh(
            (alpha_a + 1j * beta_a) * length_m
        )
    alpha_r = alpha_r_lam / wavelength_m
    beta_r = 2.0 * np.pi / (wavelength_m * vf_r)
    zr = (kr * schelkunoff_z0(total_return_m, WIRE_RADIUS_M)) / np.tanh(
        (alpha_r + 1j * beta_r) * total_return_m
    )
    return za + zr


def residual(params, length_m, total_return_m, wavelength_m, z_nec, tapered):
    """Complex log residual, as fit.py takes it."""
    z = model_zin(params, length_m, total_return_m, wavelength_m, tapered)
    magnitude = np.log(np.abs(z)) - np.log(np.abs(z_nec))
    phase = np.angle(z) - np.angle(z_nec)
    phase = (phase + np.pi) % (2.0 * np.pi) - np.pi
    return np.concatenate([magnitude, phase])


def fit_group(length_m, total_return_m, wavelength_m, z_nec, tapered, falling=False):
    """One group with one form; the model impedances and the parameters."""
    start = list(INITIAL) + ([POWER_INITIAL] if falling else [])
    lo = list(BOUNDS[0]) + ([POWER_BOUNDS[0]] if falling else [])
    hi = list(BOUNDS[1]) + ([POWER_BOUNDS[1]] if falling else [])
    out = least_squares(
        residual,
        start,
        bounds=(lo, hi),
        args=(length_m, total_return_m, wavelength_m, z_nec, tapered),
        max_nfev=4000,
    )
    return model_zin(out.x, length_m, total_return_m, wavelength_m, tapered), out.x


def check_cascade_reduces_to_coth():
    """A constant-Z0 cascade must be the shipped coth formula exactly."""
    length_m = np.array([5.0, 20.0, 41.0])
    alpha, beta = 0.02, 2.0 * np.pi / 10.5
    z0 = 300.0
    cascade = z0 / np.tanh((alpha + 1j * beta) * length_m / CASCADE_SEGMENTS)
    tanh_seg = np.tanh((alpha + 1j * beta) * length_m / CASCADE_SEGMENTS)
    for _ in range(CASCADE_SEGMENTS - 1):
        cascade = z0 * (cascade + z0 * tanh_seg) / (z0 + cascade * tanh_seg)
    coth = z0 / np.tanh((alpha + 1j * beta) * length_m)
    assert np.allclose(cascade, coth, rtol=1e-9), (cascade, coth)


def peak_mask(groups_nec):
    """Rows in each group's top decile of |Z|, where the peaks live."""
    masks = []
    for z_nec in groups_nec:
        threshold = np.percentile(np.abs(z_nec), 90)
        masks.append(np.abs(z_nec) >= threshold)
    return np.concatenate(masks)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--groups", type=int, default=120)
    parser.add_argument("--sweep", default=SWEEP)
    args = parser.parse_args()

    check_cascade_reduces_to_coth()

    data = load_sweeps([args.sweep])
    geometry = SLOPER if "apex_m" in data else FLAT_TOP
    rows = []
    for si in range(len(data["soil_names"])):
        rows += [(si, row) for row in slices(data, si, geometry)]
    step = max(1, len(rows) // args.groups)
    sample = rows[::step][: args.groups]
    print(f"{len(sample)} groups of {len(rows)}, {args.sweep}\n")

    uniform_model, tapered_model, groups_nec, powers = [], [], [], []
    for _si, (_h, _z, length_m, total_return_m, wavelength_m, z_nec) in sample:
        z_uniform, _ = fit_group(
            length_m, total_return_m, wavelength_m, z_nec, tapered=False
        )
        z_tapered, _ = fit_group(
            length_m, total_return_m, wavelength_m, z_nec, tapered=True
        )
        _, values = fit_group(
            length_m, total_return_m, wavelength_m, z_nec, tapered=True, falling=True
        )
        uniform_model.append(z_uniform)
        tapered_model.append(z_tapered)
        groups_nec.append(z_nec)
        powers.append(values[6])

    at_peaks = peak_mask(groups_nec)
    uniform_model = np.concatenate(uniform_model)
    tapered_model = np.concatenate(tapered_model)
    nec_all = np.concatenate(groups_nec)

    print("per group, its own best coefficients, so this is the form alone:")
    report("uniform", uniform_model, nec_all)
    report("tapered", tapered_model, nec_all)
    print(f"\nat the peaks (each group's top-decile |Z|, {at_peaks.sum()} rows):")
    report("uniform", uniform_model[at_peaks], nec_all[at_peaks])
    report("tapered", tapered_model[at_peaks], nec_all[at_peaks])
    print(f"\nparameters: {len(PARAM_NAMES)} against {len(PARAM_NAMES)}")

    # Does the taper subsume the shipped falling-loss ramp?  Free the
    # exponent on top of the tapered form: near zero means yes.
    powers = np.array(powers)
    print(
        f"\nfalling-loss exponent freed on the tapered form:  "
        f"median {np.median(powers):.3f}  "
        f"90th {np.percentile(powers, 90):.3f}  "
        f"at zero {100 * np.mean(powers < 1e-6):.0f}%"
    )

    # How far the model overshoots the peak itself: the largest |Z| the
    # model draws in a group against the largest NEC measures there.
    overshoot = {"uniform": [], "tapered": []}
    start = 0
    for z_nec in groups_nec:
        stop = start + len(z_nec)
        for name, model in (("uniform", uniform_model), ("tapered", tapered_model)):
            overshoot[name].append(
                np.max(np.abs(model[start:stop])) / np.max(np.abs(z_nec))
            )
        start = stop
    print("\npeak height, model against NEC, per group:")
    for name in ("uniform", "tapered"):
        ratios = np.array(overshoot[name])
        print(
            f"{name:>10}  median x{np.median(ratios):.2f}  "
            f"90th x{np.percentile(ratios, 90):.2f}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
