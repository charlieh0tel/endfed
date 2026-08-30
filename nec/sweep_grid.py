"""The grid the sweeps share: what is solved, and over what.

Separate from `table_spec.py`, which says what the model is fitted to and
over what domain.  This says where NEC is asked, and every sweep imports it
so that two grids cannot drift apart and be read as one.
"""

#: Four frequencies spanning HF.  More would only resolve the soil's
#: frequency dependence, which is smooth; the rest of the problem scales.
FREQS_HZ = (1.9e6, 3.75e6, 7.15e6, 14.175e6, 28.85e6)

#: Heights someone might actually hang a wire at, meters.
HEIGHTS_M = (2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 20.0, 25.0)

#: Return-path runs, meters.  7.62 m is the 25 ft default.
RETURNS_M = (2.0, 4.0, 7.62, 12.0, 20.0, 30.0, 45.0)

#: Antenna length in wavelengths.  Step resolves the half-wave peaks, which
#: are the whole point; 4 wavelengths covers 160 m band lengths up on 10 m.
RATIO_MIN, RATIO_MAX, RATIO_STEP = 0.05, 4.0, 0.025
