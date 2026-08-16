"""Does the antenna line's loss fall with electrical length?

The model gives each line one `alpha` in nepers per wavelength, the same
whatever the wire's electrical length.  At a half-wave peak the magnitude is
about `ka * Z0(l) / (alpha_lam * l/lambda)`, so a constant `alpha_lam` fixes
how the peak envelope decays -- and the measured envelope decays more slowly
than that, which is the x1.86 peak overshoot in docs/MODEL.md.

Inverting NEC's peaks for the `alpha_lam` each would need gives a monotone
fall of about a factor of three from a half wave to three and a half.  So
this fits each group twice, with

    constant   alpha_lam
    falling    alpha_lam * (l / lambda) ** -p,  p fitted

and compares them on what the page is judged by: the error of one length,
and how often a length the model calls a match is not one.  A parameter
added always fits better in sample, so the residual alone proves nothing.

docs/MODEL.md tried this with the sign the other way -- letting alpha grow
with electrical length -- and rejected it.

    uv run python alpha_length_check.py [--groups N]
"""

import argparse
import sys

import numpy as np
from scipy.optimize import least_squares

from coefficients2d import FLAT_TOP, load_sweeps, slices
from fit import BOUNDS, INITIAL, PARAM_NAMES, schelkunoff_z0
from nec_model import WIRE_RADIUS_M

SWEEP = "nec4_table_sweep.npz"

#: The exponent on l/lambda.  Zero is the model as it ships, so the fit can
#: always fall back to it and a fitted p is evidence rather than an artefact
#: of the bound.  One is faster than anything the peaks suggest.
POWER_INITIAL = 0.4
POWER_BOUNDS = (0.0, 1.0)

#: SWR at the radio through the page's default transformer, against its
#: default tuner.  The decision the whole page turns on.
UNUN_RATIO = 9.0
TUNER_LIMIT = 3.0
Z_SYSTEM_OHMS = 50.0
MAX_GAMMA = 0.999999


def model_zin(params, length_m, total_return_m, wavelength_m, power=0.0):
    """The two-line model, with the antenna's loss free to fall with length.

    `power` of zero is the shipped model exactly.
    """
    alpha_a_lam, vf_a, ka, alpha_r_lam, vf_r, kr = params
    in_wavelengths = length_m / wavelength_m
    alpha_a = alpha_a_lam * in_wavelengths**-power / wavelength_m
    alpha_r = alpha_r_lam / wavelength_m
    beta_a = 2.0 * np.pi / (wavelength_m * vf_a)
    beta_r = 2.0 * np.pi / (wavelength_m * vf_r)
    za = (ka * schelkunoff_z0(length_m, WIRE_RADIUS_M)) / np.tanh(
        (alpha_a + 1j * beta_a) * length_m
    )
    zr = (kr * schelkunoff_z0(total_return_m, WIRE_RADIUS_M)) / np.tanh(
        (alpha_r + 1j * beta_r) * total_return_m
    )
    return za + zr


def residual(values, length_m, total_return_m, wavelength_m, z_nec, falling):
    """Complex log residual, as fit.py takes it."""
    params = values[:6]
    power = values[6] if falling else 0.0
    z = model_zin(params, length_m, total_return_m, wavelength_m, power)
    magnitude = np.log(np.abs(z)) - np.log(np.abs(z_nec))
    phase = np.angle(z) - np.angle(z_nec)
    phase = (phase + np.pi) % (2.0 * np.pi) - np.pi
    return np.concatenate([magnitude, phase])


def fit_group(length_m, total_return_m, wavelength_m, z_nec, falling, fixed=None):
    """One group, with or without the extra freedom.

    `fixed` holds the exponent at a value shared by every group, which is
    the cheap version: one number for the whole model rather than another
    surface to tabulate and interpolate.
    """
    if fixed is not None:
        out = least_squares(
            residual,
            list(INITIAL) + [fixed],
            bounds=(list(BOUNDS[0]) + [fixed - 1e-9], list(BOUNDS[1]) + [fixed + 1e-9]),
            args=(length_m, total_return_m, wavelength_m, z_nec, True),
            max_nfev=4000,
        )
        return out.x, model_zin(
            out.x[:6], length_m, total_return_m, wavelength_m, fixed
        )
    start = list(INITIAL) + ([POWER_INITIAL] if falling else [])
    lo = list(BOUNDS[0]) + ([POWER_BOUNDS[0]] if falling else [])
    hi = list(BOUNDS[1]) + ([POWER_BOUNDS[1]] if falling else [])
    out = least_squares(
        residual,
        start,
        bounds=(lo, hi),
        args=(length_m, total_return_m, wavelength_m, z_nec, falling),
        max_nfev=4000,
    )
    return out.x, model_zin(
        out.x[:6],
        length_m,
        total_return_m,
        wavelength_m,
        out.x[6] if falling else 0.0,
    )


def swr(z, ratio=UNUN_RATIO):
    at_radio = z / ratio
    gamma = np.abs((at_radio - Z_SYSTEM_OHMS) / (at_radio + Z_SYSTEM_OHMS))
    return (1.0 + np.minimum(gamma, MAX_GAMMA)) / (1.0 - np.minimum(gamma, MAX_GAMMA))


def report(name, model, nec, powers=None):
    factor = np.exp(np.abs(np.log(np.abs(model) / np.abs(nec))))
    model_swr, nec_swr = swr(model), swr(nec)
    says_ok = model_swr <= TUNER_LIMIT
    miscall = float((says_ok & (nec_swr > TUNER_LIMIT)).sum()) / max(
        float(says_ok.sum()), 1.0
    )
    print(
        f"{name:>10}  per length median x{np.median(factor):.3f}  "
        f"90th x{np.percentile(factor, 90):.3f}  "
        f"99th x{np.percentile(factor, 99):.3f}  "
        f"miscall {miscall * 100:.1f}%"
    )
    if powers is not None:
        powers = np.array(powers)
        print(
            f"{'':>10}  fitted exponent median {np.median(powers):.3f}  "
            f"10th {np.percentile(powers, 10):.3f}  "
            f"90th {np.percentile(powers, 90):.3f}  "
            f"at zero {100 * np.mean(powers < 1e-6):.0f}%"
        )
    return miscall


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--groups", type=int, default=120)
    parser.add_argument("--sweep", default=SWEEP)
    args = parser.parse_args()

    data = load_sweeps([args.sweep])
    rows = []
    for si in range(len(data["soil_names"])):
        rows += [(si, row) for row in slices(data, si, FLAT_TOP)]
    step = max(1, len(rows) // args.groups)
    sample = rows[::step][: args.groups]
    print(f"{len(sample)} groups of {len(rows)}, {args.sweep}\n")

    constant_model, falling_model, shared_model, nec_all, powers = [], [], [], [], []
    for _si, (_h, _z, length_m, total_return_m, wavelength_m, z_nec) in sample:
        _, z_constant = fit_group(
            length_m, total_return_m, wavelength_m, z_nec, falling=False
        )
        values, z_falling = fit_group(
            length_m, total_return_m, wavelength_m, z_nec, falling=True
        )
        constant_model.append(z_constant)
        falling_model.append(z_falling)
        nec_all.append(z_nec)
        powers.append(values[6])

    shared = float(np.median(powers))
    for _si, (_h, _z, length_m, total_return_m, wavelength_m, z_nec) in sample:
        _, z_shared = fit_group(
            length_m, total_return_m, wavelength_m, z_nec, falling=True, fixed=shared
        )
        shared_model.append(z_shared)

    constant_model = np.concatenate(constant_model)
    falling_model = np.concatenate(falling_model)
    shared_model = np.concatenate(shared_model)
    nec_all = np.concatenate(nec_all)

    print("per group, its own best coefficients, so this is the form alone:")
    before = report("constant", constant_model, nec_all)
    after = report("falling", falling_model, nec_all, powers)
    report(f"shared p={shared:.3f}", shared_model, nec_all)
    print(
        f"\nmiscall {before * 100:.1f}% to {after * 100:.1f}%"
        f"  ({'better' if after < before else 'no better'})"
    )
    print(f"parameters: {len(PARAM_NAMES)} against {len(PARAM_NAMES) + 1}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
