"""Does conductor gauge matter, and do the #14 coefficients survive it?

The sweeps that produce the shipped tables run entirely at #14 AWG, so
`a/lambda` is the one axis the table never saw and every coefficient has
seen one diameter.  Two questions follow, with different answers:

  dependence  do the fitted coefficients move with gauge?
  agreement   does the shipped table, fitted at #14, still predict other
              gauges within its stated bound?

Agreement is the one the page rests on: it says the fit holds from #12 to
#22.  Coefficients may drift with gauge while the model still predicts
adequately, because Schelkunoff's Z0 already carries a logarithmic
diameter term.

    uv run python nec4_gauge_sweep.py /usr/bin/nec4d42

Grid is reduced against the table sweeps: one soil, fewer heights and
returns, because the question is a single axis rather than the whole
surface.  Writes `nec4_gauge_sweep.npz`.
"""

import argparse
import itertools
import re
import subprocess
import sys
import tempfile
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from nec_model import C, end_fed_deck
from sweep_grid import RATIO_MAX, RATIO_MIN, RATIO_STEP

OUTPUT = "nec4_gauge_sweep.npz"

#: Radii in meters for common antenna wire.  #12 through #22 spans what
#: anyone actually hangs, a factor of 3.2 in diameter.
GAUGES = {
    "12": 2.053e-3 / 2,
    "14": 1.628e-3 / 2,
    "18": 1.024e-3 / 2,
    "22": 0.644e-3 / 2,
}

FREQS_HZ = (1.9e6, 7.15e6, 14.175e6, 28.85e6)
HEIGHTS_M = (3.0, 10.0, 25.0)
RETURNS_M = (4.0, 7.62, 20.0)
SOIL = "average"

#: Runs beside other work.
WORKERS = 4

IMPEDANCE_FIELD = 4
SCIENTIFIC = re.compile(r"[-+]?\d*\.?\d+[Ee][-+]?\d+")


def parse_impedance(text):
    """Pull the source impedance out of an ANTENNA INPUT PARAMETERS table."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if "(WATTS)" not in line:
            continue
        for row in lines[i + 1 :]:
            values = SCIENTIFIC.findall(row)
            if len(values) >= IMPEDANCE_FIELD + 2:
                real, imag = values[IMPEDANCE_FIELD : IMPEDANCE_FIELD + 2]
                return complex(float(real), float(imag))
    raise ValueError("no impedance in solver output")


def ratios():
    return np.arange(RATIO_MIN, RATIO_MAX + RATIO_STEP / 2, RATIO_STEP)


def solve_group(job):
    """One (gauge, frequency): NEC-4 caches its Sommerfeld grid per pair."""
    binary, gauge, freq_hz = job
    wavelength_m = C / freq_hz
    radius_m = GAUGES[gauge]
    rows = []
    with tempfile.TemporaryDirectory(prefix="gauge-") as work:
        source = Path(work) / "in.nec"
        result = Path(work) / "out.txt"
        for height_m, return_m, ratio in itertools.product(
            HEIGHTS_M, RETURNS_M, ratios()
        ):
            source.write_text(
                end_fed_deck(
                    ratio * wavelength_m,
                    freq_hz,
                    height_m,
                    return_m,
                    ground=SOIL,
                    radius_m=radius_m,
                )
            )
            try:
                subprocess.run(
                    [binary, str(source), str(result)],
                    capture_output=True,
                    check=True,
                    cwd=work,
                )
                z = parse_impedance(result.read_text())
            except (subprocess.CalledProcessError, ValueError, OSError):
                z = complex(np.nan, np.nan)
            rows.append(
                (
                    sorted(GAUGES).index(gauge),
                    radius_m,
                    freq_hz,
                    height_m,
                    return_m,
                    ratio,
                    z.real,
                    z.imag,
                )
            )
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("binary")
    args = parser.parse_args()

    jobs = [(args.binary, gauge, freq) for gauge in sorted(GAUGES) for freq in FREQS_HZ]
    per_job = len(HEIGHTS_M) * len(RETURNS_M) * len(ratios())
    print(f"{len(jobs) * per_job} points over {len(GAUGES)} gauges", flush=True)

    start = time.time()
    with Pool(WORKERS) as pool:
        collected = pool.map(solve_group, jobs)
    columns = np.array([row for group in collected for row in group])
    print(f"solved in {time.time() - start:.0f} s", flush=True)

    np.savez_compressed(
        OUTPUT,
        gauge=columns[:, 0].astype(np.int8),
        radius_m=columns[:, 1],
        freq_hz=columns[:, 2],
        height_m=columns[:, 3],
        return_m=columns[:, 4],
        ratio=columns[:, 5],
        resistance=columns[:, 6],
        reactance=columns[:, 7],
        gauge_names=np.array(sorted(GAUGES)),
    )
    bad = int(np.isnan(columns[:, 6]).sum())
    print(f"{bad} failed, wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
