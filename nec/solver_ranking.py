"""Which browser NEC-2 to believe, where: score both against the converged answer.

Reads the decks and browser-solver answers solver_ranking_decks.mjs wrote,
solves every deck with NEC-4.2 at 1x, 2x and 4x its segmentation and with
NEC-5 at 1x, takes the Richardson pair (2x, 4x) as the converged answer,
and scores each solver's SWR at the radio against it, through the page's
9:1 and 49:1.

    uv run python solver_ranking.py solve   # NEC-4.2 and NEC-5, hours of solver time
    uv run python solver_ranking.py report  # the tables, seconds

The error factor is exp|ln(swr / swr_converged)|, so x1.10 is ten percent
either way.  Regimes are what the page can tell apart at run time:
geometry, counterpoise height, band, and the wire's length in half-waves.
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from nec4_table_sweep import parse_impedance
from nec_model import C

HERE = Path(__file__).resolve().parent / "ranking"
DECKS = HERE / "decks.jsonl"
RESULTS = HERE / "results.jsonl"
NEC4 = "/usr/bin/nec4d42"
NEC5 = "/usr/bin/nec5cl"
WORKERS = 12
UNUNS = (9.0, 49.0)
Z_SYSTEM = 50.0
MAX_GAMMA = 0.999999

#: Length bins, in half-waves: where nec2c's second peak lives is past 2.
HALF_WAVE_BINS = ((0, 1), (1, 2), (2, 3), (3, 99))


def densify(deck, k):
    """Every wire's segment count times k, kept odd as the page keeps it."""

    def gw(match):
        fields = match.group(0).split()
        n = int(fields[2]) * k
        fields[2] = str(n if n % 2 else n + 1)
        return " ".join(fields)

    return re.sub(r"^GW .*$", gw, deck, flags=re.M)


def solve(binary, deck):
    with tempfile.TemporaryDirectory(prefix="rank-") as work:
        source = Path(work) / "in.nec"
        result = Path(work) / "out.txt"
        source.write_text(deck)
        try:
            subprocess.run(
                [binary, str(source), str(result)],
                capture_output=True,
                check=True,
                cwd=work,
            )
            z = parse_impedance(result.read_text())
            return {"re": z.real, "im": z.imag}
        except (subprocess.CalledProcessError, ValueError, OSError):
            return None


def solve_row(line):
    row = json.loads(line)
    deck = row.pop("deck")
    row["nec4_d1"] = solve(NEC4, deck)
    row["nec4_d2"] = solve(NEC4, densify(deck, 2))
    row["nec4_d4"] = solve(NEC4, densify(deck, 4))
    row["nec5_d1"] = solve(NEC5, deck)
    return json.dumps(row)


def swr(z, ratio):
    at_radio = complex(z["re"], z["im"]) / ratio
    gamma = min(abs((at_radio - Z_SYSTEM) / (at_radio + Z_SYSTEM)), MAX_GAMMA)
    return (1.0 + gamma) / (1.0 - gamma)


def converged(row):
    if row["nec4_d2"] is None or row["nec4_d4"] is None:
        return None
    z2 = complex(row["nec4_d2"]["re"], row["nec4_d2"]["im"])
    z4 = complex(row["nec4_d4"]["re"], row["nec4_d4"]["im"])
    z = 2.0 * z4 - z2
    return {"re": z.real, "im": z.imag}


SOLVERS = ("nec2c", "necpp", "nec4_d1", "nec5_d1")


def report():
    rows = [json.loads(line) for line in RESULTS.read_text().splitlines()]
    scored = []
    for row in rows:
        truth = converged(row)
        if truth is None:
            continue
        halves = 2.0 * row["lenM"] * row["freqHz"] / C
        for ratio in UNUNS:
            true_swr = swr(truth, ratio)
            errors = {}
            for solver in SOLVERS:
                z = row[solver]
                errors[solver] = (
                    None if z is None else np.exp(abs(np.log(swr(z, ratio) / true_swr)))
                )
            scored.append({**row, "halves": halves, "ratio": ratio, "errors": errors})
    print(f"{len(rows)} decks, {len(scored)} scored points (two ununs each)\n")

    def table(title, key):
        groups = {}
        for point in scored:
            groups.setdefault(key(point), []).append(point)
        print(f"=== {title}: error factor of SWR at the radio, median / 90th ===")
        print(
            f"{'regime':>34} {'n':>5} | "
            + " | ".join(f"{s:>13}" for s in SOLVERS)
            + " | nec2++ closer"
        )
        for name in sorted(groups, key=lambda k: str(k)):
            points = groups[name]
            cells = []
            for solver in SOLVERS:
                e = np.array(
                    [
                        p["errors"][solver]
                        for p in points
                        if p["errors"][solver] is not None
                    ]
                )
                cells.append(
                    f"{np.median(e):5.2f} / {np.percentile(e, 90):5.2f}"
                    if len(e)
                    else f"{'--':>13}"
                )
            both = [
                p
                for p in points
                if p["errors"]["nec2c"] is not None and p["errors"]["necpp"] is not None
            ]
            closer = (
                np.mean([p["errors"]["necpp"] < p["errors"]["nec2c"] for p in both])
                if both
                else float("nan")
            )
            print(
                f"{str(name):>34} {len(points):5d} | "
                + " | ".join(cells)
                + f" | {100 * closer:5.0f}%"
            )
        print()

    def halves_bin(h):
        for lo, hi in HALF_WAVE_BINS:
            if lo <= h < hi:
                return f"{lo}-{hi} half-waves" if hi < 99 else f"{lo}+ half-waves"
        return "?"

    table("all", lambda p: "everything")
    table("by geometry", lambda p: p["geometry"])
    table(
        "by counterpoise height", lambda p: f"{p['geometry']} z={p['counterpoiseZM']} m"
    )
    table("by band", lambda p: f"{p['freqHz'] / 1e6:.3f} MHz")
    table("by length", lambda p: halves_bin(p["halves"]))
    table(
        "by counterpoise height and length",
        lambda p: f"{p['geometry']} z={p['counterpoiseZM']} m, {halves_bin(p['halves'])}",
    )
    table("by soil", lambda p: p["soil"])
    table("by unun", lambda p: f"{p['ratio']:g}:1")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=("solve", "report"))
    args = parser.parse_args()
    if args.mode == "report":
        return report()
    lines = DECKS.read_text().splitlines()
    print(f"{len(lines)} decks, four solves each", flush=True)
    with RESULTS.open("w") as out, Pool(WORKERS) as pool:
        for i, line in enumerate(pool.imap_unordered(solve_row, lines, chunksize=4)):
            out.write(line + "\n")
            if (i + 1) % 250 == 0:
                print(f"  {i + 1}/{len(lines)}", flush=True)
    print(f"wrote {RESULTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
