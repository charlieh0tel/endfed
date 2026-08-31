"""Does the return conductor's radius matter?  Coax is not #14 wire.

Every fitting deck gives the drop and the counterpoise the antenna's own
radius, 0.814 mm of #14.  A coax shield used as the return is 2.5 mm
(RG-58) to 5 mm (RG-8) in radius.  This solves a slice of the fitting
decks with the return conductors fattened to each, at 2x and 4x the
fitted segmentation with the (2x, 4x) Richardson pair as the answer, and
measures what the radius moves in SWR at the radio -- the page's own
statistic -- against the model's error budget.

    uv run python return_radius_check.py solve    # ~12k solves, under an hour
    uv run python return_radius_check.py report
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from multiprocessing import Pool
from pathlib import Path

import numpy as np

import nec_model
from nec4_table_sweep import parse_impedance

SOLVER_ENV = {**os.environ, "OMP_NUM_THREADS": "1"}

OUT = Path(__file__).resolve().parent / "ranking" / "return_radius.jsonl"
NEC4 = "/usr/bin/nec4d42"
WORKERS = 12

#: The slice: enough of the domain to say "everywhere sampled", small
#: enough for an evening.
HEIGHTS_M = (3.0, 10.0, 20.0)
Z_M = (0.02, 0.30)
SOILS = ("average", "poor")
FREQS_HZ = (3.75e6, 7.15e6, 14.175e6, 28.85e6)
RATIOS = np.arange(0.1, 4.0 + 1e-9, 0.1)
RETURN_M = 7.62

#: #14 as fitted, then RG-58 and RG-8 shield radii.
RADII_M = (nec_model.WIRE_RADIUS_M, 0.0025, 0.005)


def with_return_radius(deck, radius_m):
    """The deck with every conductor but the antenna (tag 1) fattened."""

    def gw(match):
        fields = match.group(0).split()
        if fields[1] != "1":
            fields[-1] = f"{radius_m:.6f}"
        return " ".join(fields)

    return re.sub(r"^GW .*$", gw, deck, flags=re.M)


def densify(deck, k):
    def gw(match):
        fields = match.group(0).split()
        n = int(fields[2]) * k
        fields[2] = str(n if n % 2 else n + 1)
        return " ".join(fields)

    return re.sub(r"^GW .*$", gw, deck, flags=re.M)


def solve(deck):
    with tempfile.TemporaryDirectory(prefix="rrad-") as work:
        source = Path(work) / "in.nec"
        result = Path(work) / "out.txt"
        source.write_text(deck)
        try:
            subprocess.run(
                [NEC4, str(source), str(result)],
                capture_output=True,
                env=SOLVER_ENV,
                check=True,
                cwd=work,
            )
            z = parse_impedance(result.read_text())
            return {"re": z.real, "im": z.imag}
        except (subprocess.CalledProcessError, ValueError, OSError):
            return None


def solve_case(case):
    height_m, z_m, soil, freq_hz, ratio = case
    length_m = ratio * nec_model.C / freq_hz
    base = nec_model.end_fed_deck(
        length_m, freq_hz, height_m, RETURN_M, ground=soil, return_height_m=z_m
    )
    row = {
        "height_m": height_m,
        "z_m": z_m,
        "soil": soil,
        "freq_hz": freq_hz,
        "ratio": float(ratio),
    }
    for radius_m in RADII_M:
        deck = with_return_radius(base, radius_m)
        z2 = solve(densify(deck, 2))
        z4 = solve(densify(deck, 4))
        if z2 is None or z4 is None:
            row[f"r{radius_m * 1e3:g}"] = None
            continue
        z = 2.0 * complex(z4["re"], z4["im"]) - complex(z2["re"], z2["im"])
        row[f"r{radius_m * 1e3:g}"] = {"re": z.real, "im": z.imag}
    return json.dumps(row)


def swr(z, ratio):
    at_radio = complex(z["re"], z["im"]) / ratio
    gamma = min(abs((at_radio - 50.0) / (at_radio + 50.0)), 0.999999)
    return (1.0 + gamma) / (1.0 - gamma)


def report():
    rows = [json.loads(line) for line in OUT.read_text().splitlines()]
    base_key = f"r{RADII_M[0] * 1e3:g}"
    print(
        f"{len(rows)} cases; SWR error factor of a fat return against #14, both ununs\n"
    )

    def table(title, key):
        groups = {}
        for row in rows:
            if row[base_key] is None:
                continue
            groups.setdefault(key(row), []).append(row)
        fat = [f"r{r * 1e3:g}" for r in RADII_M[1:]]
        print(f"=== {title} ===")
        print(f"{'regime':>28} {'n':>5} | " + " | ".join(f"{k:>13}" for k in fat))
        for name in sorted(groups, key=str):
            cells = []
            for k in fat:
                errs = []
                for row in groups[name]:
                    if row[k] is None:
                        continue
                    for unun in (9.0, 49.0):
                        errs.append(
                            np.exp(
                                abs(
                                    np.log(swr(row[k], unun) / swr(row[base_key], unun))
                                )
                            )
                        )
                e = np.array(errs)
                cells.append(
                    f"{np.median(e):5.2f} / {np.percentile(e, 90):5.2f}"
                    if len(e)
                    else f"{'--':>13}"
                )
            print(f"{str(name):>28} {len(groups[name]):5d} | " + " | ".join(cells))
        print()

    def halves_of(row):
        h = 2.0 * row["ratio"]
        for lo, hi in ((0, 1), (1, 2), (2, 99)):
            if lo <= h < hi:
                return f"{lo}-{hi} half-waves" if hi < 99 else "2+ half-waves"
        return "?"

    table("all", lambda r: "everything")
    table("by counterpoise height", lambda r: f"z={r['z_m']} m")
    table("by band", lambda r: f"{r['freq_hz'] / 1e6:.3f} MHz")
    table("by length", halves_of)
    table("by height", lambda r: f"h={r['height_m']} m")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=("solve", "report"))
    args = parser.parse_args()
    if args.mode == "report":
        return report()
    cases = [
        (h, z, soil, f, r)
        for h in HEIGHTS_M
        for z in Z_M
        for soil in SOILS
        for f in FREQS_HZ
        for r in RATIOS
    ]
    print(f"{len(cases)} cases, {len(RADII_M)} radii, two rungs each", flush=True)
    OUT.parent.mkdir(exist_ok=True)
    with OUT.open("w") as out, Pool(WORKERS) as pool:
        for i, line in enumerate(pool.imap_unordered(solve_case, cases, chunksize=2)):
            out.write(line + "\n")
            if (i + 1) % 200 == 0:
                print(f"  {i + 1}/{len(cases)}", flush=True)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
