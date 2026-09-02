"""Coefficients over h/lambda and counterpoise height, refined jointly.

`table2d.py` established that the second axis earns its place -- it takes
the 90th percentile from x1.65 to x1.38 and the worst from x3.11 to
x1.62 -- and settled two things about its shape.  Only `alpha_r`, `vf_r`
and `kr` need it, because they describe the return line and it is the
return line that moves; giving `alpha_a` and `ka` the axis changes
nothing.  And four nodes carry it as well as six.

That matters because the refinement has to move every parameter at once.
`coefficients.py` refines 40 per soil and its docstring notes that 120
struggles; the full 2-D table would be 200.  Return-only at four nodes is
112, which is why the shape was worth measuring before building.

Refinement is the point of this module rather than a flourish.
`alpha_r`, `vf_r` and `kr` trade off against one another, so a table
built from coordinate-wise medians can sit outside the joint feasible
set -- each entry sensible, the vector not a fit of anything.

    uv run python coefficients2d.py                    # the flat top
    uv run python coefficients2d.py --sweep nec4_table_sloper_sweep.npz
"""

import argparse
import itertools
import warnings
import json
import re
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares
from scipy.sparse import csr_matrix

from table_spec import (
    COUNTERPOISE_CEILING_FRACTION,
    LENGTH_POWER_H_LAM_HIGH,
    LENGTH_POWER_H_LAM_LOW,
    LENGTH_POWER_PLATEAU,
    MAX_COUNTERPOISE_Z_M,
    MIN_COUNTERPOISE_Z_M,
    MIN_H_OVER_LAMBDA,
    NODES,
    REFINE_BOUNDS,
    TABLE_PARAMS,
    VF_A,
    Z_NODES,
    length_power,
)
from fit import fit_group, model_zin
from nec_model import BALUN_HEIGHT_M, C
from table2d import RETURN_ONLY, build, look_up

#: What differs between the two geometries, and all that differs: which
#: column holds the height the table is indexed on, and what the return
#: conductor drops from.  A flat top drops from the wire; a sloper from
#: the balun, which is where it is fed.
FLAT_TOP = ("height_m", None)
SLOPER = ("apex_m", BALUN_HEIGHT_M)

#: Written beside this script, so the shipped numbers have a checkable
#: original outside the page.
DATA = Path(__file__).resolve().parent / "coefficients2d.json"

#: The page, and the block this script owns in it.
PAGE = Path(__file__).resolve().parents[1] / "docs" / "random-wire.html"
BEGIN = "// BEGIN GENERATED COEFFICIENTS"
END = "// END GENERATED COEFFICIENTS"


#: Indices into TABLE_PARAMS that carry the second axis.
TWO_D = RETURN_ONLY
ONE_D = tuple(i for i in range(len(TABLE_PARAMS)) if i not in TWO_D)


def pack(block):
    """A soil's table as a flat vector: the 1-D coefficients, then the 2-D."""
    flat = [block[:, 0, pi] for pi in ONE_D]
    flat += [block[:, :, pi].reshape(-1) for pi in TWO_D]
    return np.concatenate(flat)


def unpack(flat):
    """The inverse, rebuilding the (h-node, z-node, parameter) block."""
    block = np.zeros((len(NODES), len(Z_NODES), len(TABLE_PARAMS)))
    at = 0
    for pi in ONE_D:
        block[:, :, pi] = flat[at : at + len(NODES)][:, np.newaxis]
        at += len(NODES)
    for pi in TWO_D:
        block[:, :, pi] = flat[at : at + len(NODES) * len(Z_NODES)].reshape(
            len(NODES), len(Z_NODES)
        )
        at += len(NODES) * len(Z_NODES)
    return block


def bounds():
    """REFINE_BOUNDS, laid out to match `pack`."""
    lo = [np.full(len(NODES), REFINE_BOUNDS[0][pi]) for pi in ONE_D]
    hi = [np.full(len(NODES), REFINE_BOUNDS[1][pi]) for pi in ONE_D]
    lo += [np.full(len(NODES) * len(Z_NODES), REFINE_BOUNDS[0][pi]) for pi in TWO_D]
    hi += [np.full(len(NODES) * len(Z_NODES), REFINE_BOUNDS[1][pi]) for pi in TWO_D]
    return np.concatenate(lo), np.concatenate(hi)


def slices(data, si, geometry, min_points=1):
    """Every group for one soil, as the refinement and the fits want them."""
    height_key, feed_m = geometry
    rows = []
    for freq_hz, height_m, step in itertools.product(
        np.unique(data["freq_hz"]),
        np.unique(data[height_key]),
        np.unique(data["step"]),
    ):
        sel = (
            (data["freq_hz"] == freq_hz)
            & (data[height_key] == height_m)
            & (data["soil"] == si)
            & (data["step"] == step)
            & np.isfinite(data["resistance"])
        )
        if sel.sum() < min_points:
            continue
        wavelength_m = C / freq_hz
        if height_m / wavelength_m < MIN_H_OVER_LAMBDA:
            continue
        z_m = float(np.unique(data["return_height_m"][sel])[0])
        if feed_m is None:
            drops_from_m = height_m
        elif "balun_m" in data:
            # The sweep raises the balun to clear an elevated counterpoise,
            # so the drop is against what it actually solved with.
            drops_from_m = np.unique(data["balun_m"][sel])
            if len(drops_from_m) != 1:
                raise RuntimeError(
                    f"group at {freq_hz / 1e6:g} MHz, height {height_m:g}, "
                    f"step {step} spans {len(drops_from_m)} balun heights"
                )
            drops_from_m = float(drops_from_m[0])
        else:
            # A sloper sweep written before that column, which is only right
            # if it never raised the balun, which the retired domain sweep did.
            warnings.warn(
                "sloper sweep has no balun_m column: assuming the drop is "
                f"from {feed_m} m, which is wrong wherever it was raised",
                RuntimeWarning,
                stacklevel=2,
            )
            drops_from_m = feed_m
        rows.append(
            (
                height_m / wavelength_m,
                z_m / wavelength_m,
                data["ratio"][sel] * wavelength_m,
                (drops_from_m - data["return_height_m"][sel]) + data["return_m"][sel],
                wavelength_m,
                data["resistance"][sel] + 1j * data["reactance"][sel],
            )
        )
    return rows


def fit_groups(data, geometry, tapered=True):
    """Per-group fits, in the shape build() wants."""
    out = []
    for si in range(len(data["soil_names"])):
        for h_lam, z_lam, length_m, total_return_m, wavelength_m, z_nec in slices(
            data, si, geometry, min_points=20
        ):
            params, _, _ = fit_group(
                length_m,
                total_return_m,
                wavelength_m,
                z_nec,
                power=length_power(h_lam),
                tapered=tapered,
            )
            out.append({"soil": si, "h_lam": h_lam, "z_lam": z_lam, "params": params})
    return out


#: Total interpolation weight below which a node counts as unconstrained.
#: Not zero: a group can brush a node with a weight of 1e-12 and still leave
#: it a direction the residual cannot see.
WEIGHT_FLOOR = 1e-6


def _axis_weights(nodes, value):
    """The two nodes np.interp lands between in log space, and their weights."""
    xs = np.log10(nodes)
    x = np.log10(np.clip(value, nodes[0], nodes[-1]))
    i = min(max(int(np.searchsorted(xs, x)) - 1, 0), len(nodes) - 2)
    span = xs[i + 1] - xs[i]
    upper = 0.0 if span == 0 else (x - xs[i]) / span
    return (i, 1.0 - upper), (i + 1, upper)


def weight_matrix(rows, n_params):
    """Each group's five coefficients as a linear map over the flat table.

    h_lam and z_lam are fixed for a group, so the interpolation weights are
    fixed for the whole refinement and only the table values move: the lookup
    is a matrix multiply computed once rather than an np.interp per group per
    evaluation.  Same arithmetic as table2d.look_up, to 1e-14.
    """
    data, rows_at, cols_at = [], [], []
    for gi, (h_lam, z_lam, *_) in enumerate(rows):
        (i0, wh0), (i1, wh1) = _axis_weights(NODES, h_lam)
        (j0, wz0), (j1, wz1) = _axis_weights(Z_NODES, z_lam)
        for k, pi in enumerate(ONE_D):
            for node, weight in ((i0, wh0), (i1, wh1)):
                if weight:
                    rows_at.append(gi * len(TABLE_PARAMS) + pi)
                    cols_at.append(k * len(NODES) + node)
                    data.append(weight)
        base = len(ONE_D) * len(NODES)
        for k, pi in enumerate(TWO_D):
            block = base + k * len(NODES) * len(Z_NODES)
            for hn, wh in ((i0, wh0), (i1, wh1)):
                for zn, wz in ((j0, wz0), (j1, wz1)):
                    if wh * wz:
                        rows_at.append(gi * len(TABLE_PARAMS) + pi)
                        cols_at.append(block + hn * len(Z_NODES) + zn)
                        data.append(wh * wz)
    return csr_matrix(
        (data, (rows_at, cols_at)),
        shape=(len(rows) * len(TABLE_PARAMS), n_params),
    )


def group_points(rows):
    """Every group's points end to end, with the counts to spread them by."""
    counts = np.array([len(row[2]) for row in rows])
    return (
        counts,
        np.concatenate([row[2] for row in rows]),
        np.concatenate([row[3] for row in rows]),
        np.repeat([row[4] for row in rows], counts),
        np.concatenate([row[5] for row in rows]),
    )


def refine(table, data, geometry, max_nfev=600, tapered=True):
    """Fit the tabulated surface itself, one soil at a time.

    Returns the table and what the optimizer did to reach it.  Raises when a
    soil stops on max_nfev rather than on a gradient or step criterion, which
    is not a converged fit.
    """
    refined = table.copy()
    lo, hi = bounds()
    runs = []
    grouped = [slices(data, si, geometry) for si in range(table.shape[0])]
    for si, rows in enumerate(grouped):
        weights = weight_matrix(rows, len(lo))
        counts, length_m, total_return_m, wavelength_m, z_nec = group_points(rows)
        power = np.repeat([length_power(h_lam) for h_lam, *_ in rows], counts)
        log_abs_nec = np.log(np.abs(z_nec))
        angle_nec = np.angle(z_nec)

        # A node no group interpolates from is a direction the residual cannot
        # see: the trust region wanders along it until max_nfev, never
        # converging, and the value it lands on is the optimizer's rather than
        # the antenna's.  Those columns are held at what build() tabulated and
        # filled from a measured neighbour afterwards.
        held = np.asarray(np.abs(weights).sum(axis=0)).ravel() <= WEIGHT_FLOOR
        free = np.flatnonzero(~held)
        fixed_at = np.clip(pack(refined[si]), lo, hi)
        fixed_at[free] = 0.0
        constant = weights @ fixed_at
        weights = weights[:, free]

        def residual(
            flat,
            weights=weights,
            constant=constant,
            counts=counts,
            length_m=length_m,
            total_return_m=total_return_m,
            wavelength_m=wavelength_m,
            log_abs_nec=log_abs_nec,
            angle_nec=angle_nec,
        ):
            per_group = (weights @ flat + constant).reshape(-1, len(TABLE_PARAMS))
            alpha_a, ka, alpha_r, vf_r, kr = (
                np.repeat(per_group[:, pi], counts) for pi in range(len(TABLE_PARAMS))
            )
            model = model_zin(
                (alpha_a, VF_A, ka, alpha_r, vf_r, kr),
                length_m,
                total_return_m,
                wavelength_m,
                power=power,
                tapered=tapered,
            )
            magnitude = np.log(np.abs(model)) - log_abs_nec
            phase = np.angle(model) - angle_nec
            return np.concatenate([magnitude, (phase + np.pi) % (2.0 * np.pi) - np.pi])

        start = np.clip(pack(refined[si]), lo, hi)
        out = least_squares(
            residual,
            start[free],
            bounds=(lo[free], hi[free]),
            max_nfev=max_nfev,
        )
        if out.status <= 0:
            raise RuntimeError(
                f"soil {si} refinement did not converge: status {out.status}, "
                f"{out.nfev} evaluations of a {max_nfev} budget -- {out.message}"
            )
        settled = start.copy()
        settled[free] = out.x
        refined[si] = unpack(settled)
        print(
            f"  soil {si} refined: status {out.status}, {out.nfev} evaluations, "
            f"{len(free)} of {len(lo)} parameters fitted",
            flush=True,
        )
        runs.append(
            {
                "soil": si,
                "status": int(out.status),
                "nfev": int(out.nfev),
                "max_nfev": int(max_nfev),
                "cost": float(out.cost),
                "fitted": int(len(free)),
                "held": int(held.sum()),
            }
        )
    return refined, runs


def support(data, geometry, n_soils):
    """How many groups sit nearest each node, which is what constrains it."""
    counts = np.zeros((n_soils, len(NODES), len(Z_NODES)), dtype=int)
    for si in range(n_soils):
        for h_lam, z_lam, *_ in slices(data, si, geometry):
            hi = int(np.argmin(np.abs(np.log10(NODES) - np.log10(h_lam))))
            zi = int(np.argmin(np.abs(np.log10(Z_NODES) - np.log10(max(z_lam, 1e-12)))))
            counts[si, hi, zi] += 1
    return counts


def fill_unsupported(table, counts):
    """Give unconstrained nodes their nearest measured neighbour's values.

    A node with no group nearest it is not fitted: nothing in the residual
    pulls it, so the refinement leaves it wherever the bounds allow.  Such a
    node is unreachable geometry -- z/lambda of 1e-4 at a high h/lambda is a
    counterpoise under two millimetres, and on a sloper it can mean one above
    the apex it hangs from -- so it is held at the nearest measured node, the
    same extrapolation the table makes outside its range.

    Two grains of support.  The return coefficients (TWO_D) live per
    (h, z) cell and fill cell-wise.  The antenna coefficients (ONE_D)
    depend on height alone -- pack/unpack keep them equal along z -- so
    any group at any z constrains them at that h-node, and a cell-wise
    fill must not touch them: copying a neighbouring h-node's antenna
    line into the one column render() ships froze alpha_a and ka above
    h/lambda 0.9 in every table shipped before 2026-09-02.
    """
    filled = table.copy()
    filled_cells = []
    for si in range(table.shape[0]):
        measured = [
            (hi, zi)
            for hi in range(len(NODES))
            for zi in range(len(Z_NODES))
            if counts[si, hi, zi] > 0
        ]
        if not measured:
            raise RuntimeError(f"soil {si} has no measured node at all")
        measured_h = sorted({hi for hi, _ in measured})
        for hi in range(len(NODES)):
            if counts[si, hi].sum() > 0:
                continue
            near_h = min(
                measured_h,
                key=lambda h: abs(np.log10(NODES[h]) - np.log10(NODES[hi])),
            )
            for pi in ONE_D:
                filled[si, hi, :, pi] = table[si, near_h, 0, pi]
            filled_cells.append({"soil": si, "h_node": hi, "from": {"h_node": near_h}})
        for hi in range(len(NODES)):
            for zi in range(len(Z_NODES)):
                if counts[si, hi, zi] > 0:
                    continue
                near = min(
                    measured,
                    key=lambda c: (np.log10(NODES[c[0]]) - np.log10(NODES[hi])) ** 2
                    + (np.log10(Z_NODES[c[1]]) - np.log10(Z_NODES[zi])) ** 2,
                )
                for pi in TWO_D:
                    filled[si, hi, zi, pi] = table[si, near[0], near[1], pi]
                filled_cells.append(
                    {
                        "soil": si,
                        "h_node": hi,
                        "z_node": zi,
                        "from": {"h_node": near[0], "z_node": near[1]},
                    }
                )
    for pi in ONE_D:
        if not np.allclose(filled[:, :, :, pi], filled[:, :, :1, pi]):
            raise RuntimeError(
                f"{TABLE_PARAMS[pi]} varies along the counterpoise axis after "
                "filling, and render() ships only the first column"
            )
    return filled, filled_cells


def measure(data, table, geometry, tapered=True):
    """Tabulated error, per group and per length.

    Per group is an RMS over the ~240 lengths in one (soil, frequency,
    height, counterpoise) cell, which is what the fit is scored on.  Per
    length is the error of one answer, which is what a user gets: they pick
    a length, not a group, so it is the figure the page has to quote.  The
    two differ by more than rounding -- an RMS over a group hides its own
    tail -- so both are recorded and the page is bound to the second.

    Phase is carried because SWR is computed from R and X together: a
    magnitude that is right and an angle that is twenty degrees out is a
    match the user does not get.
    """
    factors, magnitude, phase = [], [], []
    for si in range(len(data["soil_names"])):
        for h_lam, z_lam, length_m, total_return_m, wavelength_m, z_nec in slices(
            data, si, geometry
        ):
            alpha_a, ka, alpha_r, vf_r, kr = look_up(table, si, h_lam, Z_NODES, z_lam)
            model = model_zin(
                (alpha_a, VF_A, ka, alpha_r, vf_r, kr),
                length_m,
                total_return_m,
                wavelength_m,
                power=length_power(h_lam),
                tapered=tapered,
            )
            err = np.log(np.abs(model)) - np.log(np.abs(z_nec))
            factors.append(np.exp(np.sqrt(np.mean(err**2))))
            magnitude.append(np.abs(err))
            angle = np.angle(model) - np.angle(z_nec)
            phase.append(np.abs((angle + np.pi) % (2.0 * np.pi) - np.pi))
    return np.array(factors), np.concatenate(magnitude), np.concatenate(phase)


def error_block(factors, magnitude, phase):
    """What the json records about how wrong the table is."""
    per_length = np.exp(magnitude)
    return {
        # Per group, the statistic the fit is scored on.  Kept because every
        # earlier figure in docs/MODEL.md is one of these.
        "median": float(np.median(factors)),
        "p90": float(np.percentile(factors, 90)),
        "worst": float(factors.max()),
        # Per length, the statistic a user meets.
        "per_length": {
            "median": float(np.median(per_length)),
            "p90": float(np.percentile(per_length, 90)),
            "p99": float(np.percentile(per_length, 99)),
            "worst": float(per_length.max()),
        },
        # Degrees, because SWR needs the angle as much as the magnitude.
        "phase_deg": {
            "median": float(np.degrees(np.median(phase))),
            "p90": float(np.degrees(np.percentile(phase, 90))),
            "worst": float(np.degrees(phase.max())),
        },
    }


def render(tables, soils):
    """The generated block, in the page's own style.

    Stored sparsely: `alpha_a` and `ka` are one row per h/lambda node,
    because they do not vary with counterpoise height, while the three
    return coefficients carry a row per node pair.  Dense storage would
    repeat the first two at every counterpoise node for nothing.
    """
    names = {"flat_top": "flatTop", "sloper": "sloper"}
    js = {
        "alpha_a_lam": "alphaA",
        "ka": "kA",
        "alpha_r_lam": "alphaR",
        "vf_r": "vfR",
        "kr": "kR",
    }
    out = [
        f"    const MODEL_H_NODES = Object.freeze("
        f"{[round(float(v), 4) for v in NODES]});",
        f"    const MODEL_Z_NODES = Object.freeze("
        f"{[round(float(v), 5) for v in Z_NODES]});",
        "    /**",
        "     * Where the fit applies.  Outside it the table is held flat and",
        "     * the answer is an extrapolation, which the page says rather",
        "     * than hides; see nec/table_spec.py.",
        "     */",
        "    const MODEL_DOMAIN = Object.freeze({",
        f"      minHOverLambda: {MIN_H_OVER_LAMBDA},",
        f"      maxHOverLambda: {round(float(NODES[-1]), 4)},",
        f"      minCounterpoiseZM: {MIN_COUNTERPOISE_Z_M},",
        f"      maxCounterpoiseZM: {MAX_COUNTERPOISE_Z_M},",
        f"      counterpoiseCeilingFraction: {COUNTERPOISE_CEILING_FRACTION},",
        "    });",
        "    /**",
        "     * The antenna line's loss falls with electrical length above a",
        "     * tenth of a wavelength up; see nec/table_spec.py and docs/MODEL.md.",
        "     */",
        "    const MODEL_LENGTH_POWER = Object.freeze({",
        f"      plateau: {LENGTH_POWER_PLATEAU},",
        f"      hOverLambdaLow: {LENGTH_POWER_H_LAM_LOW},",
        f"      hOverLambdaHigh: {LENGTH_POWER_H_LAM_HIGH},",
        "    });",
        "    const MODEL_COEFFS = Object.freeze({",
    ]
    for key, table in tables.items():
        out.append(f"      {names[key]}: Object.freeze({{")
        for si, soil in enumerate(soils):
            out.append(f"        {soil}: Object.freeze({{")
            for pi, name in enumerate(TABLE_PARAMS):
                if pi in ONE_D:
                    row = [round(float(v), 4) for v in table[si, :, 0, pi]]
                    out.append(f"          {js[name]}: {row},")
                    continue
                out.append(f"          {js[name]}: [")
                for ni in range(len(NODES)):
                    row = [round(float(v), 4) for v in table[si, ni, :, pi]]
                    out.append(f"            {row},")
                out.append("          ],")
            out.append("        }),")
        out.append("      }),")
    out.append("    });")
    return "\n".join(out)


def patch_page(block, path=PAGE):
    """Replace the marked block in the page.  True if it changed."""
    text = path.read_text()
    pattern = re.compile(
        rf"(^[ \t]*{re.escape(BEGIN)}[^\n]*\n)(.*?)(^[ \t]*{re.escape(END)})",
        re.S | re.M,
    )
    match = pattern.search(text)
    if match is None:
        raise SystemExit(f"{path} has no {BEGIN} / {END} markers")
    updated = (
        text[: match.start()]
        + f"{match.group(1)}{block}\n{match.group(3)}"
        + text[match.end() :]
    )
    if updated == text:
        return False
    path.write_text(updated)
    return True


def load_sweeps(paths):
    """Several sweeps of one geometry as a single grid.

    No one grid covers the whole table: a counterpoise placed in metres
    cannot reach a small z/lambda at a short wavelength, which is what
    nec4_node_fill_sweep.py covers.  Groups are keyed on frequency, height,
    soil and step, and that sweep offsets its step indices past this one's,
    so concatenating cannot merge two groups into one.
    """
    loaded = [np.load(path, allow_pickle=False) for path in paths]
    names = loaded[0]["soil_names"]
    # Rows only: a sweep also carries provenance (`density`, the rungs an
    # extrapolation came from) that is not one value per solve.  And only
    # the per-row columns every file carries: a repaired extrapolation adds
    # its rung masks, a plain one does not, and the fit reads neither.
    fields = None
    for path, one in zip(paths, loaded):
        rows = len(one["freq_hz"])
        here = {field for field in one.files if one[field].shape[:1] == (rows,)}
        fields = here if fields is None else fields & here
        if list(one["soil_names"]) != list(names):
            raise SystemExit(f"{path} orders its soils differently")
    assert fields is not None
    for field in ("freq_hz", "ratio", "soil", "step", "resistance", "reactance"):
        if field not in fields:
            raise SystemExit(f"every sweep must carry {field}")
    return {
        "soil_names": names,
        **{field: np.concatenate([one[field] for one in loaded]) for field in fields},
    }


def report(name, factors):
    print(
        f"  {name:<12} n={len(factors):4d}  median x{np.median(factors):.2f}  "
        f"90th x{np.percentile(factors, 90):.2f}  worst x{factors.max():.2f}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--sweep",
        nargs="+",
        default=["nec4_table_sweep.npz"],
        help="one or more sweeps of the same geometry, read as one grid",
    )
    parser.add_argument("--max-nfev", type=int, default=600)
    parser.add_argument(
        "--write",
        action="store_true",
        help="write the fitted table into coefficients2d.json",
    )
    parser.add_argument(
        "--write-page",
        action="store_true",
        help="patch both geometries into docs/random-wire.html from the json",
    )
    args = parser.parse_args()

    if args.write_page:
        stored = json.loads(DATA.read_text())
        missing = [k for k in ("flat_top", "sloper") if k not in stored]
        if missing:
            raise SystemExit(f"{DATA.name} has no {', '.join(missing)} yet")
        tables = {k: np.array(stored[k]["table"]) for k in ("flat_top", "sloper")}
        changed = patch_page(render(tables, stored["soils"]))
        print(f"{'patched' if changed else 'unchanged'} {PAGE.name}")
        raise SystemExit(0)

    data = load_sweeps(args.sweep)
    geometry = SLOPER if "apex_m" in data else FLAT_TOP
    print(
        f"{', '.join(args.sweep)}: {'sloper' if geometry is SLOPER else 'flat top'}\n"
    )

    groups = fit_groups(data, geometry)
    print(f"{len(groups)} groups fitted\n")
    n_soils = len(data["soil_names"])
    table = build(groups, n_soils, "z_lam", Z_NODES, TWO_D)
    report("unrefined", measure(data, table, geometry)[0])
    table, runs = refine(table, data, geometry, args.max_nfev)
    report("refined", measure(data, table, geometry)[0])

    counts = support(data, geometry, n_soils)
    table, filled = fill_unsupported(table, counts)
    factors, magnitude, phase = measure(data, table, geometry)
    report("filled", factors)
    per_length = np.exp(magnitude)
    print(
        f"  per length   median x{np.median(per_length):.3f}  "
        f"90th x{np.percentile(per_length, 90):.3f}  "
        f"99th x{np.percentile(per_length, 99):.3f}"
    )
    print(
        f"  phase        median {np.degrees(np.median(phase)):.1f} deg  "
        f"90th {np.degrees(np.percentile(phase, 90)):.1f} deg"
    )
    print(
        f"\n{int((counts == 0).sum())} of {counts.size} nodes have no group "
        f"nearest them and take a measured neighbour's values"
    )
    for run in runs:
        print(
            f"  soil {run['soil']}: status {run['status']}, "
            f"{run['nfev']}/{run['max_nfev']} evaluations"
        )

    if args.write:
        name = "sloper" if geometry is SLOPER else "flat_top"
        DATA.parent.mkdir(exist_ok=True)
        existing = json.loads(DATA.read_text()) if DATA.exists() else {}
        existing.update(
            {
                "h_nodes": NODES.tolist(),
                "z_nodes": Z_NODES.tolist(),
                "params": list(TABLE_PARAMS),
                "two_d_params": [TABLE_PARAMS[i] for i in TWO_D],
                "vf_a": VF_A,
                # The loss exponent's rule, so the page can be held to it.
                "length_power": {
                    "plateau": LENGTH_POWER_PLATEAU,
                    "h_lam_low": LENGTH_POWER_H_LAM_LOW,
                    "h_lam_high": LENGTH_POWER_H_LAM_HIGH,
                },
                "soils": [str(s) for s in data["soil_names"]],
                # The range the model is fitted over, carried beside the
                # numbers so a consumer need not restate it to know it.
                "domain": {
                    "min_h_over_lambda": MIN_H_OVER_LAMBDA,
                    "min_counterpoise_z_m": MIN_COUNTERPOISE_Z_M,
                    "max_counterpoise_z_m": MAX_COUNTERPOISE_Z_M,
                    "counterpoise_ceiling_fraction": COUNTERPOISE_CEILING_FRACTION,
                },
                name: {
                    "table": table.tolist(),
                    "error": error_block(factors, magnitude, phase),
                    # What produced these numbers, so a shipped table can be
                    # told from a converged, fully measured one by reading.
                    "provenance": {
                        "sweeps": sorted(Path(s).name for s in args.sweep),
                        "groups": len(groups),
                        "refinement": runs,
                        "support": counts.tolist(),
                        "filled": filled,
                    },
                },
            }
        )
        DATA.write_text(json.dumps(existing, indent=1) + "\n")
        print(f"\nwrote {name} into {DATA.name}")
