"""Richardson-extrapolate a pair of density rungs to the converged sweep.

The density study (docs/MODEL.md, "The density study") measured that a
sweep's impedance approaches its limit like 1/N in segment count, still
moving at 16x, so no uniform density converges.  What does converge is
the extrapolation: with rungs at 2x and 4x the fitted density,

    Z_limit ~= Z_4x + (Z_4x - Z_2x)

lands within x1.02 median and x1.07 at the 90th percentile of the limit,
against x1.20 and x1.60 for the raw fitted density.  Real and imaginary
parts extrapolate separately.

    uv run python extrapolate_sweep.py SWEEP_D2 SWEEP_D4 OUTPUT

The rungs must be the same campaign: every axis column is required to
match row for row, which the deterministic sweep order guarantees, and
anything else is an error rather than a silent misalignment.  A point
that failed on either rung stays NaN.
"""

import argparse
import sys

import numpy as np

#: Columns that identify a point; these must agree across the rungs.
AXIS_FIELDS = (
    "freq_hz",
    "return_m",
    "soil",
    "ratio",
    "return_height_m",
    "balun_m",
    "step",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("coarse", help="the 2x rung")
    parser.add_argument("fine", help="the 4x rung")
    parser.add_argument("output")
    args = parser.parse_args()

    coarse = np.load(args.coarse)
    fine = np.load(args.fine)

    height_key = "apex_m" if "apex_m" in coarse else "height_m"
    for field in AXIS_FIELDS + (height_key,):
        if not np.array_equal(coarse[field], fine[field]):
            raise SystemExit(f"rungs disagree on {field}: not the same campaign")
    if int(coarse["density"]) * 2 != int(fine["density"]):
        raise SystemExit(
            f"rungs are x{int(coarse['density'])} and x{int(fine['density'])}: "
            "the extrapolation wants an octave"
        )
    # The density field records what was asked for, not what was solved: a
    # campaign once solved both rungs at the fitting density because the
    # multiplier never reached forkserver workers.  Identical data cannot
    # be two densities of the same geometry.
    if np.array_equal(
        coarse["resistance"], fine["resistance"], equal_nan=True
    ) and np.array_equal(coarse["reactance"], fine["reactance"], equal_nan=True):
        raise SystemExit(
            "rungs are bit-identical: the density flag never reached the solves"
        )

    fields = {
        field: coarse[field]
        for field in coarse.files
        if field not in ("resistance", "reactance", "density")
    }
    fields["resistance"] = 2.0 * fine["resistance"] - coarse["resistance"]
    fields["reactance"] = 2.0 * fine["reactance"] - coarse["reactance"]
    # Provenance: which rungs, and that this is extrapolated rather than
    # solved.  `density` of 0 marks it as no single rung's output.
    fields["density"] = np.int16(0)
    fields["extrapolated_from"] = np.array([args.coarse, args.fine])
    np.savez_compressed(args.output, **fields)

    z_coarse = coarse["resistance"] + 1j * coarse["reactance"]
    z_fine = fine["resistance"] + 1j * fine["reactance"]
    z_out = fields["resistance"] + 1j * fields["reactance"]
    ok = ~np.isnan(fields["resistance"])
    step = np.abs(z_out[ok] - z_fine[ok]) / np.abs(z_fine[ok])
    gap = np.abs(z_fine[ok] - z_coarse[ok]) / np.abs(z_fine[ok])
    print(
        f"{ok.sum()} points extrapolated, {int((~ok).sum())} NaN; "
        f"rung gap median {np.median(gap) * 100:.1f}%, "
        f"extrapolation step median {np.median(step) * 100:.1f}%"
    )
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
