"""Everything the shipped tables are fitted from, in one sweep.

Three scripts grew separately and their union is what a refit reads:
counterpoise heights as fractions of the wire, counterpoise heights at the
table's own z nodes, and the (h node, z node) grid across the domain the
page's controls reach.  Each answers a different question -- between the
nodes, on the z nodes, on both -- and all three are needed: a table fitted
only on its nodes has nothing checking the interpolation between them.

They are reproduced here point for point, so a sweep from this script and
the three files it replaces can be compared directly, and so a re-sweep
measures a change in the decks rather than a change in the grid.

    uv run python nec4_table_sweep.py /usr/bin/nec4d42
    uv run python nec4_table_sweep.py /usr/bin/nec4d42 --sloper

Writes `nec4_table_sweep.npz` or `nec4_table_sloper_sweep.npz`.
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

import sweep_grid
import nec_model
from nec_model import (
    BALUN_HEIGHT_M,
    C,
    GROUNDS,
    MIN_DROP_M,
    end_fed_deck,
    sloper_deck,
)
from table_spec import (
    MIN_H_OVER_LAMBDA,
    NODES,
    Z_NODES,
    counterpoise_range_m,
)

FLAT_TOP_OUTPUT = "nec4_table_sweep.npz"
SLOPER_OUTPUT = "nec4_table_sloper_sweep.npz"

SOILS = tuple(sorted(GROUNDS))

#: Return length enters the model analytically through the whole conductor
#: rather than as a table axis, so three values carry it.
RETURNS_M = (4.0, 7.62, 20.0)
RATIOS = np.arange(0.05, 4.0 + 1e-9, 0.05)

#: Counterpoise as a fraction of the wire height, plus a floor for lying on
#: the ground.  0.9 is left out: with almost no drop it is a different
#: antenna, and it is the only step that degraded when measured.
FRACTIONS = (0.02, 0.05, 0.1, 0.25, 0.5)
GROUND_M = 0.01

#: A sloper's counterpoise hangs from the balun, so it is placed in metres
#: under it rather than as a fraction of the apex.
SLOPER_RETURN_HEIGHTS_M = (0.01, 0.15, 0.30, 0.45, BALUN_HEIGHT_M)

#: The page's height control, which is what the node grid is bounded by.
MIN_HEIGHT_M = 1.0
MAX_HEIGHT_M = 30.0
MIN_BALUN_M = 0.3
MAX_BALUN_M = 2.0

#: A node lands just outside a control's limit often enough -- 0.006 of a
#: 1.8 MHz wavelength is 0.7 mm under a metre -- that solving at the limit
#: is worth more than losing the corner.  Further out is geometry the page
#: cannot ask for.
EDGE = 0.05

#: Band edges reach the ends of the node grid: 0.006 is a metre of height
#: only at 1.8 MHz, and 3.0 is 30 m only at 30 MHz.
NODE_GRID_FREQS_HZ = (1.8e6, 7.15e6, 14.175e6, 28.85e6, 30e6)

#: Step indices keep the families apart, because `slices` groups on
#: (frequency, height, soil, step) and assumes one counterpoise height in a
#: group.  These are the numbers the three earlier sweeps used, ground
#: included: nec4_return_height_sweep wrote -1 for the counterpoise on the
#: ground and 0 upwards for the fractions, so a file from here and a file
#: from there can be read together without two groups merging.
GROUND_STEP = -1
FRACTION_BASE = 0
Z_NODE_BASE = 10
NODE_GRID_BASE = 30

IMPEDANCE_FIELD = 4
SCIENTIFIC = re.compile(r"[-+]?\d*\.?\d+[Ee][-+]?\d+")

#: Solves are small and separate, so this is a core count rather than a
#: memory budget.  The default leaves the machine usable; --workers takes
#: it up.  More than one per (frequency, soil) group does nothing.
DEFAULT_WORKERS = 4


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


def fraction_cells(freq_hz, sloper):
    """Counterpoise placed under the feedpoint, as the first sweeps placed it."""
    out = []
    for height_m in sweep_grid.HEIGHTS_M:
        if sloper:
            if height_m <= BALUN_HEIGHT_M:
                continue
            for zi, z_m in enumerate(SLOPER_RETURN_HEIGHTS_M):
                out.append((height_m, z_m, BALUN_HEIGHT_M, FRACTION_BASE + zi))
            continue
        out.append((height_m, GROUND_M, BALUN_HEIGHT_M, GROUND_STEP))
        for zi, fraction in enumerate(FRACTIONS):
            out.append(
                (height_m, fraction * height_m, BALUN_HEIGHT_M, FRACTION_BASE + zi)
            )
    return out


def z_node_cells(freq_hz, sloper):
    """Counterpoise at the table's own z nodes, under the same heights."""
    if sloper:
        return []
    wavelength_m = C / freq_hz
    out = []
    for height_m in sweep_grid.HEIGHTS_M:
        if height_m / wavelength_m < MIN_H_OVER_LAMBDA:
            continue
        low_m, high_m = counterpoise_range_m(height_m)
        for zi, z_lam in enumerate(Z_NODES):
            z_m = z_lam * wavelength_m
            if z_m < low_m or z_m > high_m:
                continue
            out.append((height_m, z_m, BALUN_HEIGHT_M, Z_NODE_BASE + zi))
    return out


def node_grid_cells(freq_hz, sloper):
    """Both axes at their nodes, over what the page's controls can reach."""
    wavelength_m = C / freq_hz
    out = []
    for hi, h_lam in enumerate(NODES):
        height_m = h_lam * wavelength_m
        if height_m < MIN_HEIGHT_M * (1 - EDGE) or height_m > MAX_HEIGHT_M * (1 + EDGE):
            continue
        height_m = min(max(height_m, MIN_HEIGHT_M), MAX_HEIGHT_M)
        low_m, high_m = counterpoise_range_m(height_m)
        if sloper:
            high_m = min(high_m, MAX_BALUN_M - MIN_DROP_M)
        for zi, z_lam in enumerate(Z_NODES):
            z_m = z_lam * wavelength_m
            # Clamp onto the limit rather than reject: z/lambda 0.2 at 30 MHz
            # is 1.999 m against a ceiling of 1.95, and dropping it left the
            # node with no measurement at all while a 2 m balun on 10 m puts
            # most of its interpolation weight there.
            if z_m < low_m * (1 - EDGE) or z_m > high_m * (1 + EDGE):
                continue
            z_m = min(max(z_m, low_m), high_m)
            balun_m = (
                min(max(BALUN_HEIGHT_M, z_m + MIN_DROP_M), MAX_BALUN_M)
                if sloper
                else BALUN_HEIGHT_M
            )
            out.append(
                (height_m, z_m, balun_m, NODE_GRID_BASE + hi * len(Z_NODES) + zi)
            )
    return out


def cells(freq_hz, sloper):
    """Every placement at one frequency, without solving the same one twice."""
    families = (
        (sweep_grid.FREQS_HZ, fraction_cells),
        (sweep_grid.FREQS_HZ, z_node_cells),
        (NODE_GRID_FREQS_HZ, node_grid_cells),
    )
    seen, out = set(), []
    for freqs, family in families:
        if freq_hz not in freqs:
            continue
        for height_m, z_m, balun_m, step in family(freq_hz, sloper):
            key = (round(height_m, 9), round(z_m, 9), round(balun_m, 9))
            if key in seen:
                continue
            seen.add(key)
            out.append((height_m, z_m, balun_m, step))
    return out


def frequencies():
    """Every frequency any family asks for."""
    return tuple(sorted(set(sweep_grid.FREQS_HZ) | set(NODE_GRID_FREQS_HZ)))


def solve_group(job):
    """One (frequency, soil): NEC-4 caches its Sommerfeld grid per pair."""
    index, binary, freq_hz, soil, sloper, density = job
    # Set in the worker, not the parent: under the forkserver start method
    # (the default from Python 3.14) workers re-import nec_model and a
    # parent-side assignment never reaches them.  That silently solved a
    # whole Richardson campaign at the fitting density.
    nec_model.SEGMENTS_PER_WAVELENGTH = 20 * density
    wavelength_m = C / freq_hz
    rows = []
    with tempfile.TemporaryDirectory(prefix="table-") as work:
        source = Path(work) / "in.nec"
        result = Path(work) / "out.txt"
        for height_m, z_m, balun_m, step in cells(freq_hz, sloper):
            for return_m, ratio in itertools.product(RETURNS_M, RATIOS):
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
                        balun_m,
                        step,
                        z.real,
                        z.imag,
                    )
                )
    return index, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("binary")
    parser.add_argument(
        "--workers", type=int, default=DEFAULT_WORKERS, help="parallel solvers"
    )
    parser.add_argument("--sloper", action="store_true", help="the other geometry")
    parser.add_argument(
        "--count", action="store_true", help="report the size and solve nothing"
    )
    parser.add_argument(
        "--density",
        type=int,
        default=1,
        help="segmentation multiplier: N solves at N * 20 segments per "
        "wavelength, for the Richardson pair the density study calls for "
        "(docs/MODEL.md).  Output lands in a _dN file so rungs cannot be "
        "mistaken for one another",
    )
    args = parser.parse_args()

    freqs = frequencies()
    points = 0
    for freq_hz in freqs:
        here = len(cells(freq_hz, args.sloper)) * len(RETURNS_M) * len(RATIOS)
        points += here * len(SOILS)
        print(
            f"  {freq_hz / 1e6:>7.3f} MHz: {len(cells(freq_hz, args.sloper)):>3} "
            f"placements, {here * len(SOILS):>7} points",
            flush=True,
        )
    print(f"at most {points} points in {len(freqs) * len(SOILS)} groups", flush=True)
    if args.count:
        return 0

    jobs = [
        (i, args.binary, freq, soil, args.sloper, args.density)
        for i, (freq, soil) in enumerate(
            (freq, soil) for freq in freqs for soil in SOILS
        )
    ]
    start = time.time()
    # Groups report as they finish, but land at their job index: the rungs
    # of a Richardson pair must match row for row (extrapolate_sweep.py), so
    # the output order cannot depend on which group finished first.
    collected = [None] * len(jobs)
    finished = solved = 0
    with Pool(args.workers) as pool:
        for index, rows in pool.imap_unordered(solve_group, jobs):
            collected[index] = rows
            finished += 1
            solved += len(rows)
            freq_hz, soil = jobs[index][2], jobs[index][3]
            print(
                f"  {freq_hz / 1e6:>7.3f} MHz {soil}: {len(rows)} points, "
                f"group {finished}/{len(jobs)}, {100 * solved / points:.0f}% "
                f"in {time.time() - start:.0f} s",
                flush=True,
            )
    columns = np.array([row for group in collected for row in group])
    print(f"solved {len(columns)} in {time.time() - start:.0f} s", flush=True)

    output = SLOPER_OUTPUT if args.sloper else FLAT_TOP_OUTPUT
    if args.density != 1:
        output = output.replace(".npz", f"_d{args.density}.npz")
    height_key = "apex_m" if args.sloper else "height_m"
    np.savez_compressed(
        output,
        freq_hz=columns[:, 0],
        **{height_key: columns[:, 1]},
        return_m=columns[:, 2],
        soil=columns[:, 3].astype(np.int8),
        ratio=columns[:, 4],
        return_height_m=columns[:, 5],
        # The height the return conductor drops from.  Written because the
        # sweep raises it to clear an elevated counterpoise, and a fit that
        # assumed the default would compute a negative drop.
        balun_m=columns[:, 6],
        step=columns[:, 7].astype(np.int16),
        resistance=columns[:, 8],
        reactance=columns[:, 9],
        soil_names=np.array(SOILS),
        density=np.int16(args.density),
    )
    bad = int(np.isnan(columns[:, 8]).sum())
    print(f"{bad} failed, wrote {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
