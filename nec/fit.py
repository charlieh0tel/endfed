"""Fit the two-line model to the sweep.

Structure comes from finding 7: the feedpoint is the antenna line and the
return line in series,

    Zin = Za(l) + Zr(h + ret)
    Za  = the tapered line below, open at the far end
    Zr  = kr * Z0r * coth((alpha_r + j*beta_r) * (h + ret))

with each Z0 from Schelkunoff.  The antenna line is nonuniform: its
local Z0 grows logarithmically from the feed (tapered_zin), which is
what softens the half-wave peaks the averaged-Z0 form drew nearly twice
too high; see docs/MODEL.md.  The return keeps the averaged form and
its own scale `kr` because it runs close to ground, where the image
lowers the characteristic impedance below the free-space thin-wire
figure.

beta is fitted as a velocity factor rather than assumed, because measured
half-wave reactance is nowhere near zero (finding 3).

Residuals are taken on the complex logarithm.  |Zin| spans tens of ohms
to kilohms across a sweep, so an absolute residual would fit the peaks
and ignore everything else; log residual is relative in magnitude and
plain angular error in phase, which is what SWR actually cares about.
"""

import numpy as np
from scipy.optimize import least_squares

from nec_model import WIRE_RADIUS_M

#: Fitted parameters, in the order least_squares sees them.  The alphas
#: are nepers per wavelength, not per meter: fitted per meter they came
#: out proportional to frequency, which is just the statement that a wire
#: loses a fixed fraction per wavelength.  Per wavelength they are
#: comparable across bands, which is what the coefficient surface needs.
PARAM_NAMES = ("alpha_a_lam", "vf_a", "ka", "alpha_r_lam", "vf_r", "kr")

#: Start point and bounds.  alpha_r is capped well below the point where
#: coth saturates: past about 3 nepers per wavelength the return line
#: stops being a line at all and the fit uses it as a lumped constant,
#: which fits the data while meaning nothing.
#:
#: Velocity factors are capped at unity.  Left free they drifted to 1.018,
#: which is not a wave outrunning light but beta absorbing what the line
#: form omits: Z0 varies along a real wire where Schelkunoff's figure is
#: an average, the open end is capacitively loaded, and the structure
#: radiates.  Capping costs 0.5 percent of median accuracy and keeps the
#: parameter readable as what it claims to be.
#:
#: ka and kr scale each line's Schelkunoff Z0.  Schelkunoff's figure is
#: an average over an isolated wire in free space; over ground the image
#: lowers it, and both come out near 0.75, which is that effect.
INITIAL = (0.12, 0.98, 1.0, 0.5, 0.92, 0.7)
#: alpha_r's floor is far below alpha_a's because a counterpoise clear of
#: the soil is a nearly lossless line, and at 1e-3 the fit rails there
#: rather than measuring it.  Not zero: a lossless line has infinite |Z|
#: at every half-wave multiple, and coth has nothing to damp it with.
BOUNDS = ((1e-3, 0.5, 0.2, 1e-6, 0.4, 0.05), (3.0, 1.0, 5.0, 3.0, 1.0, 3.0))


#: eta0 / (2 pi): the impedance of free space, 376.73 ohms, over 2 pi,
#: rounded to the 60 every antenna text writes.  The scale of every
#: thin-wire characteristic-impedance formula here.
ETA0_OVER_2PI_OHMS = 60.0


def schelkunoff_z0(length_m, radius_m=WIRE_RADIUS_M):
    """Average characteristic impedance of a thin wire, ohms."""
    return ETA0_OVER_2PI_OHMS * (np.log(2.0 * length_m / radius_m) - 1.0)


#: Segments in the tapered cascade.  Each segment is solved exactly, so
#: the only discretization is the Z0 staircase; against a 256-segment
#: reference, 64 leaves the worst |Z| within x1.07 at the sweep's
#: lengths, below the fit residual everywhere.
CASCADE_SEGMENTS = 64

#: Local Z0 floor, ohms.  The log profile dives toward -infinity at the
#: feed; the first segment midpoint sits at l/(2N) where the profile is
#: still a few hundred ohms, so this floor is a guard, not a knob.
Z0_FLOOR_OHMS = 10.0


def tapered_zin(length_m, radius_m, ka, alpha_np_m, beta_rad_m):
    """Input impedance of an open-ended line with Schelkunoff's local Z0.

    Schelkunoff's average Z0 stands in for a nonuniform line whose local
    characteristic impedance grows logarithmically with distance from
    the feed [Schelkunoff, "Theory of Antennas of Arbitrary Size and
    Shape", Proc. IRE 1941].  This cascades CASCADE_SEGMENTS exact
    uniform-segment solutions from the open far end back to the feed,
    each with the local `Z0 = ka * 60 (ln(2 x / a) - 1)` at its
    midpoint, `x` measured from the feed the equivalent cone grows from.
    All arguments may be arrays over points; the loop is over segments.
    """
    length_m = np.asarray(length_m, dtype=float)
    delta_m = length_m / CASCADE_SEGMENTS
    tanh_seg = np.tanh((alpha_np_m + 1j * beta_rad_m) * delta_m)
    # Open end: the far segment alone is Z0 * coth(gamma delta).
    x_mid = (CASCADE_SEGMENTS - 0.5) * delta_m
    z0 = ka * np.maximum(
        ETA0_OVER_2PI_OHMS * (np.log(2.0 * x_mid / radius_m) - 1.0), Z0_FLOOR_OHMS
    )
    zin = z0 / tanh_seg
    for segment in range(CASCADE_SEGMENTS - 2, -1, -1):
        x_mid = (segment + 0.5) * delta_m
        z0 = ka * np.maximum(
            ETA0_OVER_2PI_OHMS * (np.log(2.0 * x_mid / radius_m) - 1.0),
            Z0_FLOOR_OHMS,
        )
        zin = z0 * (zin + z0 * tanh_seg) / (z0 + zin * tanh_seg)
    return zin


def model_zin(
    params,
    length_m,
    total_return_m,
    wavelength_m,
    radius_m=WIRE_RADIUS_M,
    power=0.0,
    tapered=True,
):
    """Zin for the two-line model at the given lengths.

    `power` lets the antenna line's loss fall with electrical length,
    `alpha_a_lam * (l / lambda) ** -power`; zero is the shipped model.
    `tapered` is the shipped model; False is the averaged-Z0 form it
    replaced, kept for comparison instruments.
    """
    alpha_a_lam, vf_a, ka, alpha_r_lam, vf_r, kr = params
    alpha_a = alpha_a_lam * (length_m / wavelength_m) ** -power / wavelength_m
    alpha_r = alpha_r_lam / wavelength_m
    beta_a = 2.0 * np.pi / (wavelength_m * vf_a)
    beta_r = 2.0 * np.pi / (wavelength_m * vf_r)
    if tapered:
        za = tapered_zin(length_m, radius_m, ka, alpha_a, beta_a)
    else:
        za = (ka * schelkunoff_z0(length_m, radius_m)) / np.tanh(
            (alpha_a + 1j * beta_a) * length_m
        )
    zr = (kr * schelkunoff_z0(total_return_m, radius_m)) / np.tanh(
        (alpha_r + 1j * beta_r) * total_return_m
    )
    return za + zr


def _residual(
    params,
    length_m,
    total_return_m,
    wavelength_m,
    z_nec,
    radius_m=WIRE_RADIUS_M,
    power=0.0,
    tapered=True,
):
    """Complex log residual, flattened to the real vector least_squares wants.

    The imaginary part is wrapped to (-pi, pi].  np.log returns the principal
    argument, so a model 190 degrees out reads as -170 and the objective is
    discontinuous where |Zin| swings through resonance -- which it does, at
    every half wave.  Wrapping the difference rather than differencing the
    wrapped values makes the phase error the angle it actually is.
    """
    z = model_zin(
        params, length_m, total_return_m, wavelength_m, radius_m, power, tapered
    )
    magnitude = np.log(np.abs(z)) - np.log(np.abs(z_nec))
    phase = np.angle(z) - np.angle(z_nec)
    phase = (phase + np.pi) % (2.0 * np.pi) - np.pi
    return np.concatenate([magnitude, phase])


def fit_group(
    length_m,
    total_return_m,
    wavelength_m,
    z_nec,
    radius_m=WIRE_RADIUS_M,
    power=0.0,
    tapered=True,
):
    """Fit one (frequency, height, soil) group.

    Every point is used.  An earlier version dropped those with a
    non-positive resistance, which a passive antenna cannot have -- but
    selecting on the sign of the answer is selecting on the outcome.  It kept
    the neighbouring points from the same failing solve that happened to land
    at small positive R, and so flattered the fit exactly where NEC was
    struggling.  The regime is excluded instead, upstream in
    MIN_H_OVER_LAMBDA; see coefficients.py.
    """
    out = least_squares(
        _residual,
        INITIAL,
        bounds=BOUNDS,
        args=(length_m, total_return_m, wavelength_m, z_nec, radius_m, power, tapered),
        max_nfev=4000,
    )
    if out.status <= 0:
        raise RuntimeError(f"fit did not converge: status {out.status}, {out.message}")
    # RMS of the log-magnitude residual, reported as a factor: exp(rms) is
    # the typical multiplicative error in |Z|.
    half = len(out.fun) // 2
    rms_log_mag = float(np.sqrt(np.mean(out.fun[:half] ** 2)))
    rms_phase = float(np.sqrt(np.mean(out.fun[half:] ** 2)))
    return out.x, np.exp(rms_log_mag), np.degrees(rms_phase)
