"""The tapered line at the table level, in and out of sample.

peak_form_check.py showed the length-resolved antenna line -- fit.py's
`tapered_zin` -- removes the half-wave peak overshoot at the per-group
ceiling.  This asks what survives tabulation: it runs the real pipeline
(fit_groups, build, refine, fill_unsupported, measure) over the shipped
tables' own sweeps with each form, prints the per-length statistics the
page quotes, and then scores both fitted tables against the committed
out-of-sample holdout (holdout/oob.jsonl), the way holdout_oob.py
scores the shipped ones.  Nothing is written; this is a measurement.

    uv run python peak_table_check.py [--max-nfev N] [--geometry g]
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

from coefficients2d import (
    FLAT_TOP,
    SLOPER,
    TWO_D,
    build,
    fill_unsupported,
    fit_groups,
    load_sweeps,
    measure,
    refine,
    support,
)
from fit import model_zin
from holdout_oob import RESULTS, TUNERS, UNUNS, converged, swr
from table2d import look_up
from table_spec import VF_A, Z_NODES, length_power
from nec_model import C

SWEEPS = {
    "flatTop": (
        FLAT_TOP,
        [
            "nec4_table_sweep_3.75MHz_extrapolated.npz",
            "nec4_table_sweep_extrapolated.npz",
        ],
    ),
    "sloper": (
        SLOPER,
        [
            "nec4_table_sloper_sweep_3.75MHz_extrapolated.npz",
            "nec4_table_sloper_sweep_extrapolated.npz",
        ],
    ),
}


def fitted_table(data, geometry, tapered, max_nfev):
    """The pipeline as coefficients2d.__main__ runs it, one form."""
    groups = fit_groups(data, geometry, tapered=tapered)
    n_soils = len(data["soil_names"])
    table = build(groups, n_soils, "z_lam", Z_NODES, TWO_D)
    table, _ = refine(table, data, geometry, max_nfev, tapered=tapered)
    table, _ = fill_unsupported(table, support(data, geometry, n_soils))
    return table


def modeled(row, table, soils, tapered):
    """holdout_oob.modeled, with the form a parameter."""
    si = soils.index(row["soil"])
    lam = C / row["freq_hz"]
    h_lam = row["height_m"] / lam
    z_lam = row["z_m"] / lam
    alpha_a, ka, alpha_r, vf_r, kr = look_up(table, si, h_lam, Z_NODES, z_lam)
    drops_from = row["height_m"] if row["geometry"] == "flatTop" else row["balun_m"]
    total_return = (drops_from - row["z_m"]) + row["return_m"]
    z = model_zin(
        (alpha_a, VF_A, ka, alpha_r, vf_r, kr),
        np.array([row["length_m"]]),
        np.array([total_return]),
        lam,
        power=length_power(h_lam),
        tapered=tapered,
    )
    return complex(z[0])


def in_sample(name, data, table, geometry, tapered):
    _, magnitude, phase = measure(data, table, geometry, tapered=tapered)
    per_length = np.exp(magnitude)
    print(
        f"  {name:>8}  per length median x{np.median(per_length):.3f}  "
        f"90th x{np.percentile(per_length, 90):.3f}  "
        f"99th x{np.percentile(per_length, 99):.3f}  "
        f"worst x{per_length.max():.2f}  "
        f"phase 90th {np.degrees(np.percentile(phase, 90)):.1f} deg"
    )


def out_of_sample(name, rows, table, soils, tapered):
    factors, models, truths = [], [], []
    for row in rows:
        truth = converged(row)
        if truth is None:
            continue
        model = modeled(row, table, soils, tapered)
        factors.append(float(np.exp(abs(np.log(abs(model) / abs(truth))))))
        models.append(model)
        truths.append(truth)
    factors = np.array(factors)
    ok_m = np.array(
        [swr(m, ratio) <= limit for m in models for ratio in UNUNS for limit in TUNERS]
    )
    ok_t = np.array(
        [swr(t, ratio) <= limit for t in truths for ratio in UNUNS for limit in TUNERS]
    )
    wrong = (ok_m & ~ok_t).sum() / max(ok_m.sum(), 1)
    print(
        f"  {name:>8}  n={len(factors)}  per length median x{np.median(factors):.3f}  "
        f"90th x{np.percentile(factors, 90):.3f}  "
        f"99th x{np.percentile(factors, 99):.3f}  "
        f"miscall {100 * wrong:.1f}%"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--max-nfev", type=int, default=600)
    parser.add_argument(
        "--geometry", choices=("flatTop", "sloper"), help="one geometry only"
    )
    args = parser.parse_args()

    holdout = [json.loads(line) for line in Path(RESULTS).read_text().splitlines()]
    geometries = [args.geometry] if args.geometry else list(SWEEPS)
    for name in geometries:
        geometry, sweeps = SWEEPS[name]
        data = load_sweeps(sweeps)
        soils = [str(s) for s in data["soil_names"]]
        rows = [r for r in holdout if r["geometry"] == name]
        print(f"{name}: {', '.join(sweeps)}")
        for tapered in (False, True):
            label = "tapered" if tapered else "uniform"
            begin = time.perf_counter()
            table = fitted_table(data, geometry, tapered, args.max_nfev)
            print(f"  {label} pipeline: {time.perf_counter() - begin:.0f} s")
            in_sample(label, data, table, geometry, tapered)
            out_of_sample(label, rows, table, soils, tapered)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
