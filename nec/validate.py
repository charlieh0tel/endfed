"""Sanity checks before trusting any sweep output.

Two textbook cases pin the driver itself, then the end-fed geometry is
exercised over the quarter/half wave pattern it exists to capture.

PyNEC solves these, not NEC-4.2: the point is that the decks this repo
builds are well formed and the physics comes out textbook, which is a
question either solver answers.  Nothing fitted comes from here.

Exits non-zero if a case leaves its bounds, so CI can run it.
"""

import sys

from PyNEC import nec_context

from nec_model import C, WIRE_RADIUS_M, end_fed_zin

SEGMENTS = 101


def monopole_zin(length_m, freq_hz, radius_m=WIRE_RADIUS_M, segments=SEGMENTS):
    """Base-fed vertical monopole over perfect ground.  Expect ~36 + j21."""
    ctx = nec_context()
    geo = ctx.get_geometry()
    # The lower end must sit exactly at z = 0 to bond to the ground plane.
    geo.wire(1, segments, 0, 0, 0, 0, 0, length_m, radius_m, 1, 1)
    ctx.geometry_complete(1)
    ctx.gn_card(1, 0, 0, 0, 0, 0, 0, 0)  # perfectly conducting ground
    ctx.ex_card(0, 1, 1, 0, 1.0, 0, 0, 0, 0, 0)
    ctx.fr_card(0, 1, freq_hz / 1e6, 0)
    ctx.xq_card(0)
    return ctx.get_input_parameters(0).get_impedance()[0]


def dipole_zin(length_m, freq_hz, radius_m=WIRE_RADIUS_M, segments=SEGMENTS):
    """Center-fed dipole in free space.  Expect ~73 + j42."""
    ctx = nec_context()
    geo = ctx.get_geometry()
    geo.wire(1, segments, 0, 0, -length_m / 2, 0, 0, length_m / 2, radius_m, 1, 1)
    ctx.geometry_complete(0)
    ctx.ex_card(0, 1, segments // 2 + 1, 0, 1.0, 0, 0, 0, 0, 0)
    ctx.fr_card(0, 1, freq_hz / 1e6, 0)
    ctx.xq_card(0)
    return ctx.get_input_parameters(0).get_impedance()[0]


#: Bounds a textbook case has to stay inside.  Wide enough for a thin wire
#: and a segment count, narrow enough that a broken deck lands outside.
TEXTBOOK = (
    ("quarter-wave monopole, perfect ground", 30.0, 45.0, 15.0, 30.0),
    ("half-wave dipole, free space", 65.0, 90.0, 30.0, 55.0),
)

#: The end-fed pattern: hundreds of ohms at odd quarter waves, kilohms at
#: half-wave multiples.  The gap either side is what the page exists to
#: keep a wire out of.
QUARTER_WAVE_MAX = 800.0
HALF_WAVE_MIN = 1500.0


def check(name, value, low, high, failures):
    """Report a value against its bounds, and record it if it is outside."""
    ok = low <= value <= high
    if not ok:
        failures.append(f"{name}: {value:.1f}, expected {low:g} to {high:g}")
    return "ok " if ok else "OUT"


if __name__ == "__main__":
    freq = 14.2e6
    lam = C / freq
    failures = []
    print(f"f = {freq / 1e6} MHz, lambda = {lam:.3f} m\n")

    print("-- driver against textbook cases --")
    values = (monopole_zin(lam / 4, freq), dipole_zin(lam / 2, freq))
    for (name, r_lo, r_hi, x_lo, x_hi), z in zip(TEXTBOOK, values):
        marks = (
            check(f"{name} R", z.real, r_lo, r_hi, failures),
            check(f"{name} X", z.imag, x_lo, x_hi, failures),
        )
        print(f"  {name}: {z:.1f}  R {marks[0]}  X {marks[1]}")

    print("\n-- end-fed geometry, h = 10 m, 15 m return, average ground --")
    for ratio in (0.25, 0.5, 0.75, 1.0, 1.5, 2.0):
        z = end_fed_zin(ratio * lam, freq, 10.0, 15.0)
        odd_quarter = abs(ratio * 4 % 4 - 1) < 1e-9 or abs(ratio * 4 % 4 - 3) < 1e-9
        if odd_quarter:
            mark = check(f"{ratio} lambda", abs(z), 0.0, QUARTER_WAVE_MAX, failures)
        else:
            mark = check(f"{ratio} lambda", abs(z), HALF_WAVE_MIN, 1e9, failures)
        print(f"  l = {ratio:4.2f} lambda: {z:>18.1f}   |Z| = {abs(z):8.1f}  {mark}")

    if failures:
        print("\nout of bounds:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        sys.exit(1)
    print("\nevery case inside its bounds")
