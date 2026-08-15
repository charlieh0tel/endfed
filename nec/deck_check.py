"""Are the decks this repo writes the geometry it means?

Everything measured here comes from cards handed to a solver, so a wrong
card is a wrong measurement that looks like a finding.  This reads the
decks rather than solving them: no NEC of either version, milliseconds,
and it runs in CI where the licensed solver cannot.

    uv run python deck_check.py

`validate.py` is the other half, and needs a solver: it asks whether the
physics comes out textbook.  This asks whether the deck says what the
geometry says.
"""

import sys

from nec_model import (
    BALUN_HEIGHT_M,
    C,
    GROUNDS,
    MIN_DROP_M,
    RETURN_HEIGHT_M,
    SEGMENTS_PER_WAVELENGTH,
    WIRE_RADIUS_M,
    end_fed_deck,
    sloper_deck,
)
from table_spec import MIN_COUNTERPOISE_Z_M

FREQ_HZ = 14.175e6
WAVELENGTH_M = C / FREQ_HZ


def cards(deck, kind):
    """Every card of one kind, split into fields."""
    return [
        line.split()
        for line in deck.splitlines()
        if line.startswith(f"{kind} ") or line == kind
    ]


def wires(deck):
    """Each GW as (tag, segments, x1, y1, z1, x2, y2, z2, radius)."""
    return [
        (int(c[1]), int(c[2]), *[float(v) for v in c[3:10]]) for c in cards(deck, "GW")
    ]


def check(name, ok, failures, detail=""):
    if not ok:
        failures.append(f"{name}{': ' + detail if detail else ''}")
    return "ok " if ok else "OUT"


def flat_top(failures):
    """A flat top: wire at height, drop to the counterpoise, run along it."""
    length_m, height_m, return_m = 21.336, 9.144, 7.62
    deck = end_fed_deck(length_m, FREQ_HZ, height_m, return_m)
    got = wires(deck)

    check("three wires", len(got) == 3, failures, f"{len(got)}")
    antenna, drop, run = got
    check(
        "antenna runs from the feedpoint at height",
        antenna[4] == height_m and antenna[7] == height_m and antenna[2] == 0.0,
        failures,
        f"{antenna}",
    )
    check(
        "antenna is as long as asked",
        abs(antenna[5] - length_m) < 1e-9,
        failures,
        f"{antenna[5]} against {length_m}",
    )
    check(
        "drop falls from the feedpoint to the counterpoise",
        drop[4] == height_m and abs(drop[7] - RETURN_HEIGHT_M) < 1e-9,
        failures,
        f"{drop}",
    )
    check(
        "run lies at the counterpoise height",
        abs(run[4] - RETURN_HEIGHT_M) < 1e-9 and abs(run[7] - RETURN_HEIGHT_M) < 1e-9,
        failures,
        f"{run}",
    )
    check(
        "run is the length asked for, along the antenna",
        abs(run[5] - return_m) < 1e-9,
        failures,
        f"{run[5]} against {return_m}",
    )
    check("radius is the wire's", all(w[8] == WIRE_RADIUS_M for w in got), failures)

    # Source on the first segment of the antenna wire, where the unun goes.
    ex = cards(deck, "EX")
    check("one source", len(ex) == 1, failures, f"{len(ex)}")
    check(
        "source is on segment 1 of wire 1",
        ex[0][1:4] == ["0", "1", "1"],
        failures,
        " ".join(ex[0]),
    )

    # Sommerfeld ground, with the soil constants asked for.
    eps, sigma = GROUNDS["average"]
    gn = cards(deck, "GN")
    check("one ground card", len(gn) == 1, failures, f"{len(gn)}")
    check("ground is Sommerfeld", gn[0][1] == "2", failures, " ".join(gn[0]))
    check(
        "soil constants are the ones asked for",
        abs(float(gn[0][5]) - eps) < 1e-9 and abs(float(gn[0][6]) - sigma) < 1e-12,
        failures,
        " ".join(gn[0]),
    )

    fr = cards(deck, "FR")
    check(
        "frequency is in MHz",
        abs(float(fr[0][5]) - FREQ_HZ / 1e6) < 1e-9,
        failures,
        " ".join(fr[0]),
    )
    check("deck ends", deck.strip().endswith("EN"), failures)
    return deck


def segmentation(failures):
    """Segments per wavelength, odd, so a center segment exists."""
    for ratio in (0.1, 0.5, 1.0, 2.5):
        length_m = ratio * WAVELENGTH_M
        deck = end_fed_deck(length_m, FREQ_HZ, 9.144, 7.62)
        segments = wires(deck)[0][1]
        want = SEGMENTS_PER_WAVELENGTH * ratio
        check(
            f"{ratio} lambda is segmented at least {SEGMENTS_PER_WAVELENGTH}/lambda",
            segments >= want,
            failures,
            f"{segments} against {want:.0f}",
        )
        check(
            f"{ratio} lambda has a center segment",
            segments % 2 == 1,
            failures,
            f"{segments}",
        )


def sloper(failures):
    """A sloper: fed at the balun, rising to the apex, return heading away."""
    apex_m, return_m = 20.0, 7.62
    slant_m = 25.0
    deck = sloper_deck(slant_m, FREQ_HZ, apex_m, return_m)
    got = wires(deck)
    antenna, drop, run = got[0], got[1], got[-1]

    check("three wires", len(got) == 3, failures, f"{len(got)}")
    check(
        "antenna climbs from the balun to the apex",
        abs(antenna[4] - BALUN_HEIGHT_M) < 1e-9 and abs(antenna[7] - apex_m) < 1e-9,
        failures,
        f"{antenna}",
    )
    rise_m = apex_m - BALUN_HEIGHT_M
    reach_m = (slant_m**2 - rise_m**2) ** 0.5
    check(
        "reach is the slant less the rise",
        abs(antenna[5] - reach_m) < 1e-6,
        failures,
        f"{antenna[5]:.6f} against {reach_m:.6f}",
    )
    check(
        "return heads away from the wire",
        run[5] < 0,
        failures,
        f"x2 = {run[5]}",
    )
    check(
        "return is the length asked for",
        abs(abs(run[5]) - return_m) < 1e-9,
        failures,
        f"{run[5]} against {-return_m}",
    )
    check(
        "drop falls from the balun",
        abs(drop[4] - BALUN_HEIGHT_M) < 1e-9,
        failures,
        f"{drop}",
    )
    check(
        "a wire shorter than its rise is refused",
        sloper_deck(rise_m, FREQ_HZ, apex_m, return_m) is None,
        failures,
    )
    check(
        "a counterpoise level with the balun leaves no drop wire",
        len(
            wires(
                sloper_deck(
                    slant_m, FREQ_HZ, apex_m, return_m, return_height_m=BALUN_HEIGHT_M
                )
            )
        )
        == 2,
        failures,
    )


def counterpoise_height(failures):
    """The counterpoise sits where it is put, down to the page's floor."""
    for z_m in (MIN_COUNTERPOISE_Z_M, 0.05, 1.0, 4.5):
        deck = end_fed_deck(21.336, FREQ_HZ, 9.144, 7.62, return_height_m=z_m)
        drop, run = wires(deck)[1], wires(deck)[2]
        check(
            f"counterpoise at {z_m} m",
            abs(run[4] - z_m) < 1e-9 and abs(drop[7] - z_m) < 1e-9,
            failures,
            f"run at {run[4]}, drop ends at {drop[7]}",
        )
    check(
        "a drop shorter than the minimum is left out",
        len(
            wires(
                end_fed_deck(
                    21.336, FREQ_HZ, 9.144, 7.62, return_height_m=9.144 - MIN_DROP_M / 2
                )
            )
        )
        == 2,
        failures,
    )


def main():
    failures = []
    deck = flat_top(failures)
    segmentation(failures)
    sloper(failures)
    counterpoise_height(failures)

    print("a flat top at 14.175 MHz, 21.336 m of wire, 9.144 m up:\n")
    print("\n".join(f"  {line}" for line in deck.splitlines()))

    if failures:
        print(f"\n{len(failures)} deck checks failed:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1
    print("\nevery deck check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
