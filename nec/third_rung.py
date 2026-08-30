"""Re-extrapolate the points the (2x, 4x) pair got wrong, from (4x, 8x).

Richardson extrapolation can cross zero resistance where the rungs still
disagree strongly -- the half-wave peaks -- and a negative resistance is
not a measurement.  This solves just those rows at 8x the fitted density
and replaces their extrapolation with the (4x, 8x) pair, which sits an
octave deeper into the asymptotic regime.

    uv run python third_rung.py NEC_BINARY SWEEP_D4 EXTRAPOLATED

Rewrites EXTRAPOLATED in place, with a `third_rung` mask recording which
rows came from the deeper pair.  The geometry is inferred from the file's
height column, as extrapolate_sweep.py wrote it.
"""

import argparse
import os
import subprocess
import sys
import tempfile
from multiprocessing import Pool
from pathlib import Path

import numpy as np

import nec_model
from nec4_table_sweep import parse_impedance

#: NEC-4.2 and NEC-5 are OpenMP builds that spawn a thread per core for
#: every solve; a pool of a dozen of them is a hundred and fifty runnable
#: threads and a load average to match, for no throughput.  One thread per
#: solve is as fast on these small matrices and leaves the machine usable.
SOLVER_ENV = {**os.environ, "OMP_NUM_THREADS": "1"}


THIRD_DENSITY = 8
WORKERS = 12


def solve_row(job):
    """One row at the third rung, in its own scratch directory."""
    index, binary, sloper, freq_hz, height_m, return_m, soil, ratio, z_m, balun_m = job
    nec_model.SEGMENTS_PER_WAVELENGTH = 20 * THIRD_DENSITY
    length_m = ratio * (nec_model.C / freq_hz)
    if sloper:
        deck = nec_model.sloper_deck(
            length_m,
            freq_hz,
            height_m,
            return_m,
            balun_m=balun_m,
            ground=soil,
            return_height_m=z_m,
        )
    else:
        deck = nec_model.end_fed_deck(
            length_m,
            freq_hz,
            height_m,
            return_m,
            ground=soil,
            return_height_m=z_m,
        )
    with tempfile.TemporaryDirectory(prefix="rung3-") as work:
        source = Path(work) / "in.nec"
        result = Path(work) / "out.txt"
        source.write_text(deck)
        try:
            subprocess.run(
                [binary, str(source), str(result)],
                capture_output=True,
                env=SOLVER_ENV,
                check=True,
                cwd=work,
            )
            z = parse_impedance(result.read_text())
        except (subprocess.CalledProcessError, ValueError, OSError):
            z = complex(np.nan, np.nan)
    return index, z


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("binary")
    parser.add_argument("fine", help="the 4x rung")
    parser.add_argument("extrapolated", help="rewritten in place")
    args = parser.parse_args()

    fine = np.load(args.fine)
    ex = np.load(args.extrapolated)
    if int(fine["density"]) * 2 != THIRD_DENSITY:
        raise SystemExit(f"{args.fine} is not the x{THIRD_DENSITY // 2} rung")
    sloper = "apex_m" in ex.files
    height_key = "apex_m" if sloper else "height_m"
    soils = [str(s) for s in ex["soil_names"]]

    bad = np.flatnonzero(ex["resistance"] < 0)
    print(f"{len(bad)} rows with negative resistance", flush=True)

    jobs = [
        (
            int(i),
            args.binary,
            sloper,
            float(ex["freq_hz"][i]),
            float(ex[height_key][i]),
            float(ex["return_m"][i]),
            soils[int(ex["soil"][i])],
            float(ex["ratio"][i]),
            float(ex["return_height_m"][i]),
            float(ex["balun_m"][i]),
        )
        for i in bad
    ]
    resistance = ex["resistance"].copy()
    reactance = ex["reactance"].copy()
    third_rung = np.zeros(len(resistance), dtype=bool)
    solved = 0
    with Pool(WORKERS) as pool:
        for index, z8 in pool.imap_unordered(solve_row, jobs):
            z4 = complex(fine["resistance"][index], fine["reactance"][index])
            z = 2.0 * z8 - z4
            resistance[index] = z.real
            reactance[index] = z.imag
            third_rung[index] = True
            solved += 1
            if solved % 100 == 0:
                print(f"  {solved}/{len(jobs)}", flush=True)

    fields = {name: ex[name] for name in ex.files}
    fields["resistance"] = resistance
    fields["reactance"] = reactance
    fields["third_rung"] = third_rung
    np.savez_compressed(args.extrapolated, **fields)

    still = int((resistance[bad] < 0).sum())
    nan = int(np.isnan(resistance[bad]).sum())
    print(
        f"replaced {len(bad)} rows from the (4x, 8x) pair; "
        f"{still} still negative, {nan} NaN"
    )
    print(f"rewrote {args.extrapolated}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
