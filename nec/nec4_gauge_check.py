"""Does the shipped table, fitted at #14, hold from #12 to #22?

The page says it does.  This measures it: the tabulated model is evaluated
at each gauge's own radius -- Schelkunoff's Z0 carries a logarithmic
diameter term, so the model does respond to gauge without being fitted per
gauge -- and compared against NEC at the same geometry.

    uv run python nec4_gauge_check.py [sweep.npz]

Per-group error factors, by gauge, against the bound coefficients2d.json
records for the flat top.  If a gauge is worse than the table's own
measured error, the claim on the page does not hold at that gauge.
"""

import json
import sys
from pathlib import Path

import numpy as np

from fit import model_zin
from nec_model import C, RETURN_HEIGHT_M
from table_spec import VF_A, Z_NODES
from table2d import look_up

DATA = Path(__file__).resolve().parent / "coefficients2d.json"
DEFAULT_SWEEP = "nec4_gauge_sweep.npz"

#: The gauge the tables were fitted at.  It is the control: it should land
#: on the table's own error, and if it does not, the comparison is wrong
#: rather than the claim.  A NEC-2 sweep read here does exactly that.
FITTED_GAUGE = "14"

#: How far past the table's own 90th a gauge may sit before the claim on
#: the page stops holding.
SLACK = 1.05


def error_factors(data, table, soil_index, radius_m, selection):
    """Per-group RMS error factor, as coefficients2d.measure computes it."""
    factors = []
    for freq_hz in np.unique(data["freq_hz"][selection]):
        for height_m in np.unique(data["height_m"][selection]):
            for return_m in np.unique(data["return_m"][selection]):
                sel = (
                    selection
                    & (data["freq_hz"] == freq_hz)
                    & (data["height_m"] == height_m)
                    & (data["return_m"] == return_m)
                    & np.isfinite(data["resistance"])
                )
                if not sel.any():
                    continue
                wavelength_m = C / freq_hz
                h_lam = height_m / wavelength_m
                z_lam = RETURN_HEIGHT_M / wavelength_m
                alpha_a, ka, alpha_r, vf_r, kr = look_up(
                    table, soil_index, h_lam, Z_NODES, z_lam
                )
                model = model_zin(
                    (alpha_a, VF_A, ka, alpha_r, vf_r, kr),
                    data["ratio"][sel] * wavelength_m,
                    (height_m - RETURN_HEIGHT_M) + return_m,
                    wavelength_m,
                    radius_m,
                )
                nec = data["resistance"][sel] + 1j * data["reactance"][sel]
                err = np.log(np.abs(model)) - np.log(np.abs(nec))
                factors.append(np.exp(np.sqrt(np.mean(err**2))))
    return np.array(factors)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SWEEP
    data = np.load(path, allow_pickle=False)
    stored = json.loads(DATA.read_text())
    table = np.array(stored["flat_top"]["table"])
    bound = stored["flat_top"]["error"]
    soils = [str(s) for s in stored["soils"]]
    soil_index = soils.index("average")
    gauges = [str(g) for g in data["gauge_names"]]

    print(f"{path}, against the flat top fitted at #{FITTED_GAUGE}")
    print(
        f"the table's own error: median x{bound['median']:.3f}, "
        f"90th x{bound['p90']:.3f}, worst x{bound['worst']:.3f}\n"
    )
    print(
        f"{'gauge':>6} {'radius mm':>10} {'groups':>7} "
        f"{'median':>8} {'90th':>8} {'worst':>8}"
    )

    outside = []
    control = None
    for gi, gauge in enumerate(gauges):
        sel = data["gauge"] == gi
        radius_m = float(np.unique(data["radius_m"][sel])[0])
        factors = error_factors(data, table, soil_index, radius_m, sel)
        median = float(np.median(factors))
        p90 = float(np.percentile(factors, 90))
        print(
            f"{'#' + gauge:>6} {radius_m * 2000:10.3f} {len(factors):7d} "
            f"x{median:7.3f} x{p90:7.3f} x{factors.max():7.3f}"
        )
        if gauge == FITTED_GAUGE:
            control = p90
        # The claim is that other gauges are no worse than the table itself.
        if p90 > bound["p90"] * SLACK:
            outside.append(f"#{gauge}: 90th x{p90:.3f} against x{bound['p90']:.3f}")

    if control is not None and control > bound["p90"] * SLACK:
        print(
            f"\n#{FITTED_GAUGE} is the gauge the table was fitted at and it is "
            f"outside its own bound: x{control:.3f} against x{bound['p90']:.3f}.\n"
            "Read the comparison, not the gauges: a sweep from another solver, "
            "or a table refitted since this sweep, lands here.",
            file=sys.stderr,
        )
        return 1
    if outside:
        print("\ngauges outside the table's own bound:", file=sys.stderr)
        for line in outside:
            print(f"  {line}", file=sys.stderr)
        return 1
    print("\nevery gauge is within the bound the table records for itself")
    return 0


if __name__ == "__main__":
    sys.exit(main())
