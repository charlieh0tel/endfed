"""Does the fitting pipeline still produce the numbers it used to?

The sweeps that produce the shipped tables need NEC-4.2, which is licensed
and cannot run in CI, so nothing automated could see a change in `fit.py`,
`table2d.py` or `coefficients2d.py` until someone spent an hour of local
solver time and noticed the coefficients had moved.

`fixtures/pipeline_fixture.npz` is a small cut of a NEC-4.2 sweep -- solver
output, which carries no license of its own -- and
`fixtures/pipeline_expected.json` is what the pipeline makes of it.  This
runs the one against the other.  A change in the fit, the tabulation, the
refinement, or in a pinned scipy, fails here rather than silently in the
next refit.

    uv run python pipeline_check.py            # check, exit 1 on drift
    uv run python pipeline_check.py --write    # after an intended change

Not a check of whether the model is right: `validate.py` does the physics
and `docs/MODEL.md` argues the rest.  This only says the pipeline is the
one that produced what ships.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from coefficients2d import (
    FLAT_TOP,
    TWO_D,
    error_block,
    fill_unsupported,
    fit_groups,
    load_sweeps,
    measure,
    refine,
    support,
)
from table_spec import NODES, TABLE_PARAMS, Z_NODES
from table2d import build

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "pipeline_fixture.npz"
EXPECTED = Path(__file__).resolve().parent / "fixtures" / "pipeline_expected.json"

#: Tight enough to catch a changed formula, loose enough to survive a
#: different BLAS summing in a different order.  The error statistics are
#: aggregates over ~7000 points and move in the fifth decimal between
#: machines.
TOLERANCE = 1e-4

#: Coefficients get their own, much looser, and the reason is not sloppiness.
#: The refinement has flat directions wherever a node is thinly supported --
#: kr against alpha_r at a node with one group behind it -- and two machines
#: rounding differently land on different points along one.  Measured between
#: this machine and CI: identical inputs, identical scipy, a cost that agrees
#: to nine figures, and one coefficient 11 percent apart.  What is
#: reproducible is the cost and the error, which are checked tightly below; a
#: formula change moves every coefficient far more than this.
COEFFICIENT_TOLERANCE = 0.15

#: The cost is the invariant: two points in a flat valley have the same one.
COST_TOLERANCE = 1e-6


def run():
    """The shipped pipeline, over the fixture."""
    data = load_sweeps([str(FIXTURE)])
    n_soils = len(data["soil_names"])
    groups = fit_groups(data, FLAT_TOP)
    table = build(groups, n_soils, "z_lam", Z_NODES, TWO_D)
    table, runs = refine(table, data, FLAT_TOP)
    counts = support(data, FLAT_TOP, n_soils)
    table, filled = fill_unsupported(table, counts)
    factors, magnitude, phase = measure(data, table, FLAT_TOP)
    return {
        "h_nodes": NODES.tolist(),
        "z_nodes": Z_NODES.tolist(),
        "params": list(TABLE_PARAMS),
        "groups": len(groups),
        "fitted": [run["fitted"] for run in runs],
        "held": [run["held"] for run in runs],
        "cost": [run["cost"] for run in runs],
        "filled": len(filled),
        "table": table.tolist(),
        "error": error_block(factors, magnitude, phase),
    }


def differences(got, want):
    """Every way the two disagree, in words a reader can act on."""
    out = []
    for key in ("h_nodes", "z_nodes", "params", "groups", "fitted", "held", "filled"):
        if got[key] != want[key]:
            out.append(f"{key}: {got[key]}, expected {want[key]}")
    for si, (value, expected) in enumerate(zip(got["cost"], want["cost"])):
        if abs(value - expected) > COST_TOLERANCE * max(abs(expected), 1.0):
            out.append(f"cost, soil {si}: {value:.9f}, expected {expected:.9f}")

    def compare_errors(got_block, want_block, prefix=""):
        for key, value in got_block.items():
            if isinstance(value, dict):
                compare_errors(value, want_block[key], f"{prefix}{key} ")
            elif abs(value - want_block[key]) > TOLERANCE:
                out.append(
                    f"error {prefix}{key}: {value:.9f}, expected {want_block[key]:.9f}"
                )

    compare_errors(got["error"], want["error"])
    a, b = np.array(got["table"]), np.array(want["table"])
    if a.shape != b.shape:
        out.append(f"table shape: {a.shape}, expected {b.shape}")
        return out
    worst = np.abs(a - b).max()
    if worst > COEFFICIENT_TOLERANCE:
        si, hi, zi, pi = np.unravel_index(np.abs(a - b).argmax(), a.shape)
        out.append(
            f"table: largest difference {worst:.3e} at soil {si}, "
            f"h node {NODES[hi]:g}, z node {Z_NODES[zi]:g}, {TABLE_PARAMS[pi]} "
            f"({a[si, hi, zi, pi]:.6f} against {b[si, hi, zi, pi]:.6f})"
        )
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--write", action="store_true", help="record what the pipeline makes now"
    )
    args = parser.parse_args()

    got = run()
    if args.write:
        EXPECTED.write_text(json.dumps(got, indent=1) + "\n")
        print(
            f"wrote {EXPECTED.name}: {got['groups']} groups, "
            f"error median x{got['error']['median']:.4f}"
        )
        return 0

    want = json.loads(EXPECTED.read_text())
    problems = differences(got, want)
    if problems:
        print(f"the pipeline no longer reproduces {EXPECTED.name}:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print(
            "\nIf the change was intended, rerun with --write and say in the "
            "commit what moved and why.",
            file=sys.stderr,
        )
        return 1
    print(
        f"pipeline reproduces {EXPECTED.name}: {got['groups']} groups, "
        f"error median x{got['error']['median']:.4f}, "
        f"90th x{got['error']['p90']:.4f}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
