"""Solve the whole table, at the nodes, across everything the page can ask.

The page's controls reach h/lambda from 0.006 to 3.0 and z/lambda from
0.00006 to 1.5.  Earlier sweeps cover the middle of that: they place the
counterpoise at fractions of the wire height, or at fixed metres, and both
trace curves across the two axes rather than covering them.  A node off
those curves has nothing constraining it, and the page reaches it anyway.

This solves at the nodes themselves, in wavelengths, which is the only way
to place a geometry at a chosen (h/lambda, z/lambda): both axes divide by
the same wavelength, so a height or a counterpoise fixed in metres sweeps a
diagonal rather than a point.  Combinations the page cannot ask for are
skipped -- a height outside HEIGHT_RANGE_M, a counterpoise outside
`table_spec.counterpoise_range_m` -- so no NEC time is spent on geometry
nobody can dial in.

    uv run python nec4_domain_sweep.py /usr/bin/nec4d42
    uv run python nec4_domain_sweep.py /usr/bin/nec4d42 --sloper

Writes `nec4_domain_sweep.npz` or `nec4_domain_sloper_sweep.npz`, in the
schema of the main sweeps, to be read alongside them.
"""

import argparse
import re
import subprocess
import sys
import tempfile
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from nec_model import (
    BALUN_HEIGHT_M,
    C,
    GROUNDS,
    MIN_DROP_M,
    end_fed_deck,
    sloper_deck,
)
from table_spec import NODES, Z_NODES, counterpoise_range_m

FLAT_TOP_OUTPUT = "nec4_domain_sweep.npz"
SLOPER_OUTPUT = "nec4_domain_sloper_sweep.npz"

#: The band edges matter here rather than the middles: h/lambda of 0.006 is
#: 1 m of height only at 1.8 MHz, and 3.0 is 30 m only at 30 MHz.  The three
#: interior frequencies are the main sweep's, so the two grids line up.
FREQS_HZ = (1.8e6, 7.15e6, 14.175e6, 28.85e6, 30e6)
SOILS = tuple(sorted(GROUNDS))

#: The page's own height control, which is what "every combination" means.
MIN_HEIGHT_M = 1.0
MAX_HEIGHT_M = 30.0

#: The page's balun control.  A sloper's counterpoise hangs from the balun,
#: so this and MIN_DROP_M are what its z/lambda can reach at all.
MIN_BALUN_M = 0.3
MAX_BALUN_M = 2.0

#: A node often lands just outside a control's limit -- 0.006 of a 1.8 MHz
#: wavelength is 0.7 mm under a metre -- and solving at the limit instead is
#: worth more than losing the corner.  Further out than this it is a
#: geometry the page cannot ask for, and is skipped.
EDGE = 0.02

#: As the other sweeps trim them: return length enters the model
#: analytically through the whole conductor rather than as a table axis.
RETURNS_M = (4.0, 7.62, 20.0)
RATIOS = np.arange(0.05, 4.0 + 1e-9, 0.05)

#: Past every other sweep's, so all of them can be read as one grid without
#: two groups merging: `slices` keys on (frequency, height, soil, step).
STEP_BASE = 30

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


def cells(freq_hz, sloper):
    """(height, counterpoise height, step) at every node the page can reach.

    The height is the wire on a flat top and the apex on a sloper, which is
    what each geometry's table is indexed on.  A sloper also needs its wire
    to clear the rise, which the length axis handles, and a counterpoise no
    higher than the balun it hangs from.
    """
    wavelength_m = C / freq_hz
    out = []
    for hi, h_lam in enumerate(NODES):
        height_m = h_lam * wavelength_m
        if height_m < MIN_HEIGHT_M * (1 - EDGE) or height_m > MAX_HEIGHT_M * (1 + EDGE):
            continue
        height_m = min(max(height_m, MIN_HEIGHT_M), MAX_HEIGHT_M)
        low_m, high_m = counterpoise_range_m(height_m)
        if sloper:
            # It hangs from the balun and has to leave a drop, so the highest
            # counterpoise a sloper can carry is the tallest balun less that.
            high_m = min(high_m, MAX_BALUN_M - MIN_DROP_M)
        for zi, z_lam in enumerate(Z_NODES):
            z_m = z_lam * wavelength_m
            if z_m < low_m * (1 - EDGE) or z_m > high_m * (1 + EDGE):
                continue
            z_m = min(max(z_m, low_m), high_m)
            balun_m = (
                min(max(BALUN_HEIGHT_M, z_m + MIN_DROP_M), MAX_BALUN_M)
                if sloper
                else BALUN_HEIGHT_M
            )
            out.append((height_m, z_m, balun_m, STEP_BASE + hi * len(Z_NODES) + zi))
    return out


def solve_group(job):
    """One (frequency, soil): NEC-4 caches its Sommerfeld grid per pair."""
    binary, freq_hz, soil, sloper = job
    wavelength_m = C / freq_hz
    rows = []
    with tempfile.TemporaryDirectory(prefix="dom-") as work:
        source = Path(work) / "in.nec"
        result = Path(work) / "out.txt"
        for height_m, z_m, balun_m, step in cells(freq_hz, sloper):
            for return_m in RETURNS_M:
                for ratio in RATIOS:
                    length_m = ratio * wavelength_m
                    if sloper:
                        deck = sloper_deck(
                            length_m,
                            freq_hz,
                            height_m,
                            return_m,
                            balun_m=balun_m,
                            ground=soil,
                            return_height_m=z_m,
                        )
                        if deck is None:
                            continue
                    else:
                        deck = end_fed_deck(
                            length_m,
                            freq_hz,
                            height_m,
                            return_m,
                            ground=soil,
                            return_height_m=z_m,
                        )
                    source.write_text(deck)
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
                            freq_hz,
                            height_m,
                            return_m,
                            SOILS.index(soil),
                            ratio,
                            z_m,
                            step,
                            z.real,
                            z.imag,
                        )
                    )
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("binary")
    parser.add_argument(
        "--sloper", action="store_true", help="sweep the sloper geometry instead"
    )
    args = parser.parse_args()

    jobs = [
        (args.binary, freq, soil, args.sloper) for freq in FREQS_HZ for soil in SOILS
    ]
    points = (
        sum(len(cells(freq, args.sloper)) for freq in FREQS_HZ)
        * len(RETURNS_M)
        * len(RATIOS)
        * len(SOILS)
    )
    print(f"at most {points} points in {len(jobs)} groups", flush=True)
    for freq_hz in FREQS_HZ:
        print(
            f"  {freq_hz / 1e6:g} MHz: {len(cells(freq_hz, args.sloper))} nodes",
            flush=True,
        )

    start = time.time()
    with Pool(WORKERS) as pool:
        collected = pool.map(solve_group, jobs)
    columns = np.array([row for group in collected for row in group])
    print(f"solved {len(columns)} in {time.time() - start:.0f} s", flush=True)

    output = SLOPER_OUTPUT if args.sloper else FLAT_TOP_OUTPUT
    height_key = "apex_m" if args.sloper else "height_m"
    np.savez_compressed(
        output,
        freq_hz=columns[:, 0],
        **{height_key: columns[:, 1]},
        return_m=columns[:, 2],
        soil=columns[:, 3].astype(np.int8),
        ratio=columns[:, 4],
        return_height_m=columns[:, 5],
        step=columns[:, 6].astype(np.int16),
        resistance=columns[:, 7],
        reactance=columns[:, 8],
        soil_names=np.array(SOILS),
    )
    bad = int(np.isnan(columns[:, 7]).sum())
    print(f"{bad} failed, wrote {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
