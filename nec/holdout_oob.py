"""The shipped tables out of sample: geometries the sweeps never carried.

Every accuracy figure the page quotes is in sample in every axis but
frequency.  This solves fresh decks at heights, counterpoise heights,
return runs and frequencies between and beyond the sweeps' grid, at 2x
and 4x the fitting density with the (2x, 4x) Richardson pair as the
converged answer, and scores the shipped tables against them the way
the in-sample figures were scored: per-length |Z| factor and phase, and
the miscall rate through the page's ununs and tuners.

    uv run python holdout_oob.py count    # decks and a price, no solving
    uv run python holdout_oob.py solve    # NEC-4.2, an hour or two
    uv run python holdout_oob.py report   # against the shipped tables
"""

import argparse
import os
import itertools
import json
import subprocess
import sys
import tempfile
from multiprocessing import Pool
from pathlib import Path

import numpy as np

import nec_model
from nec4_table_sweep import parse_impedance
from nec_model import C, GROUNDS, MIN_DROP_M
from table2d import look_up
from table_spec import VF_A, Z_NODES, length_power
from fit import model_zin

#: NEC-4.2 and NEC-5 are OpenMP builds that spawn a thread per core for
#: every solve; a pool of a dozen of them is a hundred and fifty runnable
#: threads and a load average to match, for no throughput.  One thread per
#: solve is as fast on these small matrices and leaves the machine usable.
SOLVER_ENV = {**os.environ, "OMP_NUM_THREADS": "1"}


HERE = Path(__file__).resolve().parent / "holdout"
RESULTS = HERE / "oob.jsonl"
DATA = Path(__file__).resolve().parent / "coefficients2d.json"
NEC4 = "/usr/bin/nec4d42"
WORKERS = 12
#: Seconds per deck for the 2x and 4x solves together, measured on this
#: machine during the solver ranking.
SECONDS_PER_DECK = 5.0

#: Between and beyond what nec4_table_sweep.py carried: its heights are
#: 2, 3, 5, 7, 10, 15, 20 and 25 m, its counterpoise heights fractions of
#: the wire height and the table's own nodes, its returns 4, 7.62 and 20 m,
#: its frequencies 1.8, 1.9, 7.15, 14.175, 28.85 and 30 MHz.
FLAT_HEIGHTS_M = (4.0, 6.0, 8.5, 12.0, 17.0)
FLAT_Z_M = (0.03, 0.15, 0.6)
SLOPER_APEX_M = (8.0, 14.0)
SLOPER_Z_M = (0.1, 0.25)
SLOPER_BALUN_M = (0.61, 1.0)
RETURNS_M = (5.5, 15.0)
FREQS_HZ = (3.75e6, 10.125e6, 21.2e6)
SOILS = tuple(sorted(GROUNDS))
LENGTHS_M = tuple(np.linspace(3.0, 66.0, 24))

UNUNS = (1.0, 4.0, 9.0, 49.0, 64.0)
TUNERS = (3.0, 5.0, 9.0, 12.0)
Z_SYSTEM = 50.0
MAX_GAMMA = 0.999999


def cases():
    """Every deck, as the row it will be scored as."""
    out = []
    for h, z, ret, f, soil, length in itertools.product(
        FLAT_HEIGHTS_M, FLAT_Z_M, RETURNS_M, FREQS_HZ, SOILS, LENGTHS_M
    ):
        out.append(
            dict(
                geometry="flatTop",
                height_m=h,
                z_m=z,
                balun_m=None,
                return_m=ret,
                freq_hz=f,
                soil=soil,
                length_m=float(length),
            )
        )
    for apex, z, balun, ret, f, soil, length in itertools.product(
        SLOPER_APEX_M, SLOPER_Z_M, SLOPER_BALUN_M, RETURNS_M, FREQS_HZ, SOILS, LENGTHS_M
    ):
        if length <= apex - balun or z > balun - MIN_DROP_M:
            continue
        out.append(
            dict(
                geometry="sloper",
                height_m=apex,
                z_m=z,
                balun_m=balun,
                return_m=ret,
                freq_hz=f,
                soil=soil,
                length_m=float(length),
            )
        )
    return out


def deck_of(case, density):
    nec_model.SEGMENTS_PER_WAVELENGTH = 20 * density
    if case["geometry"] == "sloper":
        return nec_model.sloper_deck(
            case["length_m"],
            case["freq_hz"],
            case["height_m"],
            case["return_m"],
            balun_m=case["balun_m"],
            ground=case["soil"],
            return_height_m=case["z_m"],
        )
    return nec_model.end_fed_deck(
        case["length_m"],
        case["freq_hz"],
        case["height_m"],
        case["return_m"],
        ground=case["soil"],
        return_height_m=case["z_m"],
    )


def solve(deck):
    with tempfile.TemporaryDirectory(prefix="oob-") as work:
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
            return [z.real, z.imag]
        except (subprocess.CalledProcessError, ValueError, OSError):
            return None


def solve_case(case):
    row = dict(case)
    for density in (2, 4):
        deck = deck_of(case, density)
        row[f"d{density}"] = None if deck is None else solve(deck)
    return json.dumps(row)


def converged(row):
    if row["d2"] is None or row["d4"] is None:
        return None
    z2 = complex(*row["d2"])
    z4 = complex(*row["d4"])
    return 2.0 * z4 - z2


def modeled(row, tables):
    """The shipped table at this geometry, as the page evaluates it."""
    table, soils = tables[row["geometry"]]
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
    )
    return complex(z[0])


def swr(z, ratio):
    at_radio = z / ratio
    gamma = min(abs((at_radio - Z_SYSTEM) / (at_radio + Z_SYSTEM)), MAX_GAMMA)
    return (1.0 + gamma) / (1.0 - gamma)


def report():
    stored = json.loads(DATA.read_text())
    soils = [str(s) for s in stored["soils"]]
    tables = {
        "flatTop": (np.array(stored["flat_top"]["table"]), soils),
        "sloper": (np.array(stored["sloper"]["table"]), soils),
    }
    rows = [json.loads(line) for line in RESULTS.read_text().splitlines()]
    scored = []
    for row in rows:
        truth = converged(row)
        if truth is None:
            continue
        model = modeled(row, tables)
        factor = float(np.exp(abs(np.log(abs(model) / abs(truth)))))
        phase = float(np.degrees(abs(np.angle(model / truth))))
        scored.append(
            {**row, "truth": truth, "model": model, "factor": factor, "phase": phase}
        )
    print(f"{len(rows)} decks, {len(scored)} converged\n")

    def per_length(points, label):
        f = np.array([p["factor"] for p in points])
        ph = np.array([p["phase"] for p in points])
        print(
            f"{label:>28} n={len(points):5d}  |Z| x{np.median(f):.3f} / "
            f"x{np.percentile(f, 90):.3f} / x{np.percentile(f, 99):.3f}   "
            f"phase {np.median(ph):.1f} / {np.percentile(ph, 90):.1f} deg"
        )

    print(
        "per length, median / 90th / 99th (in sample: flat x1.162 / x1.488 / "
        "x2.060, sloper x1.153 / x1.430 / x1.972)"
    )
    per_length(scored, "everything")
    for key, label in (
        ("geometry", "geometry"),
        ("height_m", "height m"),
        ("z_m", "counterpoise m"),
        ("return_m", "return m"),
        ("freq_hz", "MHz"),
        ("soil", "soil"),
    ):
        for value in sorted({p[key] for p in scored}):
            shown = f"{value / 1e6:.3f}" if key == "freq_hz" else value
            per_length([p for p in scored if p[key] == value], f"{label} {shown}")
        print()

    print(
        "miscall, unun into tuner: offers / of those wrong / good called bad "
        "(in sample at 9:1 into 3:1: flat 23.6%, sloper 18.7%)"
    )
    for geometry in ("flatTop", "sloper"):
        points = [p for p in scored if p["geometry"] == geometry]
        print(f"  {geometry}, {len(points)} points")
        for ratio in UNUNS:
            for limit in TUNERS:
                ok_m = np.array([swr(p["model"], ratio) <= limit for p in points])
                ok_t = np.array([swr(p["truth"], ratio) <= limit for p in points])
                if not ok_m.any():
                    continue
                wrong = (ok_m & ~ok_t).sum() / ok_m.sum()
                missed = (~ok_m & ok_t).sum() / max(ok_t.sum(), 1)
                print(
                    f"    {ratio:4g}:1 into {limit:g}:1  {100 * ok_m.mean():5.1f}%  "
                    f"{100 * wrong:5.1f}%  {100 * missed:5.1f}%"
                )
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=("count", "solve", "report"))
    args = parser.parse_args()
    if args.mode == "report":
        return report()
    all_cases = cases()
    flat = sum(c["geometry"] == "flatTop" for c in all_cases)
    print(
        f"{len(all_cases)} decks ({flat} flat top, {len(all_cases) - flat} sloper), "
        f"two solves each; about {len(all_cases) * SECONDS_PER_DECK / WORKERS / 3600:.1f} "
        f"hours at {WORKERS} workers",
        flush=True,
    )
    if args.mode == "count":
        return 0
    HERE.mkdir(exist_ok=True)
    with RESULTS.open("w") as out, Pool(WORKERS) as pool:
        for i, line in enumerate(
            pool.imap_unordered(solve_case, all_cases, chunksize=4)
        ):
            out.write(line + "\n")
            if (i + 1) % 500 == 0:
                print(f"  {i + 1}/{len(all_cases)}", flush=True)
    print(f"wrote {RESULTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
