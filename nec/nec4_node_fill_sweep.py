"""Solve the table's counterpoise-height nodes directly.

`nec4_return_height_sweep.py` places the counterpoise at fractions of the
wire height, so its coverage in (h/lambda, z/lambda) is a family of curves
rather than the rectangle the table is indexed on, and nodes off those
curves have no group to constrain them.

This sweep targets the nodes themselves.  For each frequency it places the
counterpoise at `z_node * wavelength`, which is the only way to reach a small
z/lambda at a large h/lambda: both axes are divided by the same wavelength,
so a counterpoise fixed in metres cannot span the table at a short one.
Combinations outside what can be built are dropped, and what can be built is
`table_spec.counterpoise_range_m` rather than a rule restated here: the model
carries the definition of its own range.  Heights below the fit's h/lambda
floor go too, since nothing downstream would use them.

    uv run python nec4_node_fill_sweep.py /usr/bin/nec4d42

Writes `nec4_node_fill_sweep.npz` in the schema of the main sweep, to be
read alongside it rather than instead of it.
"""

import re
import subprocess
import sys
import tempfile
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

import sweep_grid
from nec_model import C, GROUNDS, end_fed_deck
from table_spec import MIN_H_OVER_LAMBDA, Z_NODES, counterpoise_range_m

OUTPUT = "nec4_node_fill_sweep.npz"

FREQS_HZ = sweep_grid.FREQS_HZ
HEIGHTS_M = sweep_grid.HEIGHTS_M
SOILS = tuple(sorted(GROUNDS))

#: As the main sweep trims them, and for the same reasons: return length
#: enters the model analytically rather than as a table axis.
RETURNS_M = (4.0, 7.62, 20.0)
RATIOS = np.arange(0.05, 4.0 + 1e-9, 0.05)

#: Step indices are offset past the main sweep's so that the two files can be
#: concatenated without a group from one merging into a group from the other:
#: `slices` keys groups on (frequency, height, soil, step) and assumes one
#: counterpoise height within a group.
STEP_BASE = 10

#: Deliberately fewer than the twelve groups: this runs beside other work.
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


def cells(freq_hz):
    """(height, counterpoise height, step index) worth solving at one frequency.

    A node is worth solving where the geometry exists: the wire high enough
    in wavelengths for the fit to use it, and the counterpoise between the
    lowest the page offers and half the wire height.
    """
    wavelength_m = C / freq_hz
    out = []
    for height_m in HEIGHTS_M:
        if height_m / wavelength_m < MIN_H_OVER_LAMBDA:
            continue
        low_m, high_m = counterpoise_range_m(height_m)
        for zi, z_lam in enumerate(Z_NODES):
            z_m = z_lam * wavelength_m
            if z_m < low_m or z_m > high_m:
                continue
            out.append((height_m, z_m, STEP_BASE + zi))
    return out


def solve_group(job):
    """One (frequency, soil), as the main sweep groups them.

    NEC-4 caches its Sommerfeld grid per working directory and that grid is a
    function of frequency and ground alone, so this is the grouping that pays.
    """
    binary, freq_hz, soil = job
    wavelength_m = C / freq_hz
    rows = []
    with tempfile.TemporaryDirectory(prefix="nfs-") as work:
        source = Path(work) / "in.nec"
        result = Path(work) / "out.txt"
        for height_m, z_m, step in cells(freq_hz):
            for return_m in RETURNS_M:
                for ratio in RATIOS:
                    source.write_text(
                        end_fed_deck(
                            ratio * wavelength_m,
                            freq_hz,
                            height_m,
                            return_m,
                            ground=soil,
                            return_height_m=z_m,
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
    if len(sys.argv) < 2:
        print(f"usage: {sys.argv[0]} <nec4-binary>", file=sys.stderr)
        return 2
    binary = sys.argv[1]

    jobs = [(binary, freq, soil) for freq in FREQS_HZ for soil in SOILS]
    points = sum(
        len(cells(freq)) * len(RETURNS_M) * len(RATIOS) for freq in FREQS_HZ
    ) * len(SOILS)
    print(f"{points} points in {len(jobs)} groups", flush=True)
    for freq_hz in FREQS_HZ:
        wavelength_m = C / freq_hz
        listed = ", ".join(
            f"h={h:g} z={z:.4g} (h/lam {h / wavelength_m:.2f}, z/lam {z / wavelength_m:.4f})"
            for h, z, _ in cells(freq_hz)
        )
        print(f"  {freq_hz / 1e6:g} MHz: {listed}", flush=True)

    start = time.time()
    with Pool(WORKERS) as pool:
        collected = pool.map(solve_group, jobs)
    columns = np.array([row for group in collected for row in group])
    print(f"solved in {time.time() - start:.0f} s", flush=True)

    np.savez_compressed(
        OUTPUT,
        freq_hz=columns[:, 0],
        height_m=columns[:, 1],
        return_m=columns[:, 2],
        soil=columns[:, 3].astype(np.int8),
        ratio=columns[:, 4],
        return_height_m=columns[:, 5],
        step=columns[:, 6].astype(np.int8),
        resistance=columns[:, 7],
        reactance=columns[:, 8],
        soil_names=np.array(SOILS),
    )
    bad = int(np.isnan(columns[:, 7]).sum())
    print(f"{bad} failed, wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
