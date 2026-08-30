# random-wire.html: the impedance model

How the page decides whether a wire length is any good, what the model
does and does not claim, and how its constants are obtained.

Task status and measured results live in `TODO.md`; this
file is the approach.

## What the model is for

The page answers one question: given the bands you want, how long
should the wire be?  Both methods it offers are answers to that, and
neither is a prediction of what an antenna analyzer will read at your
feedpoint.

- **Classic mode** keeps a percentage margin away from `n * lambda/2`.
  The half-wave points are bad because the feedpoint impedance spikes
  there, so this is a proxy for impedance with the impedance removed.
  Its virtue is that it is checkable arithmetic.
- **Impedance mode** models `|Zin|` directly and scores lengths by the
  SWR they present at the radio through the transformer.  Its virtue is
  that it is the actual criterion.  Its cost is that it is true only
  under assumptions the user cannot see, which is what the rest of this
  document is about.

The output is an **envelope, not a prediction**.  A real end-fed's
feedpoint impedance is dominated by height, ground, the return path,
common-mode current on the feedline, and sag.  Measured resonant peaks
vary severalfold from modeled ones.  Quoting `|Z|` to three figures
would be false precision, and the page's caveat text exists to say so.

## Conventions

Where the physics is scale invariant, parameterise by the dimensionless
ratios `l/lambda`, `a/lambda` and `h/lambda` rather than by absolute
size.  A wire is electrically the same antenna at 40 ft on 40 m as at
20 ft on 20 m, and the fitted coefficients should say so once instead of
twice.

Not everything here is scale invariant, which is why the sweep keeps
frequency as a real axis: soil enters through its complex permittivity,
`eps - j*sigma/(omega*eps0)`, which depends on frequency.

## The runtime model

The page used to ship a single line, open at the far end:

    Zin  = Z0 * coth(gamma * l)
    gamma = alpha + j*beta
    Z0   = 60 * (ln(2l/a) - 1)      # Schelkunoff, thin wire
    beta = 2*pi / (lambda * velocityFactor)

What it ships now is two such lines in series at the feedpoint, the
antenna and the return path, which is the form Finding 7 licenses:

    Zin = Za(l) + Zr(ret)
    Za  = ka * Z0(l)   * coth((alpha_a + j*beta_a) * l)
    Zr  = kr * Z0(ret) * coth((alpha_r + j*beta_r) * ret)
    ret = max(feed - cpz, 0) + cp

`ret` is the whole return conductor: the drop from the feedpoint to the
counterpoise, plus the counterpoise itself.  `feed` is the wire height on
a flat top and the balun height on a sloper, which is what makes the two
geometries one formula.

`ka` and `kr` scale each line's Schelkunoff `Z0`, which is an average
over an isolated wire in free space and reads high once ground is
present.  `alpha` is carried in nepers per wavelength so one number
serves every band.

Choosing this form over anything learned is deliberate.  `Zin` has
near-poles at the half-wave resonances, and that pole structure *is* the
physics of the problem.  `coth` carries it exactly and for free.  What
remains -- `alpha`, and the corrections to `beta` -- is smooth and
low-dimensional, which is an interpolation problem.  A fitted analytic
form also extrapolates sanely, states its own assumptions, and can carry
a written error bound; none of which a black box does.  See
`TODO.md` for the reasoning against a neural network.

### The anchor problem

The two ends of the model are not independent.  Pinning `Zin` at one
length forces the other end to about `Z0^2 / (2 R)`, so a single anchor
cannot make the model right at a quarter wave and a half wave at once.

The shipped anchor is the end-fed half wave at 2450 ohms, the figure a
49:1 transformer is wound for.  NEC has since confirmed that end and
demolished the other: there is no characteristic quarter-wave impedance
to anchor to, because the resonator is not the antenna wire alone.
Which leads to the geometry below.

## Geometry: the return path is part of the antenna

The single most consequential correction to the original model.  The
feedpoint impedance is set by the whole conductor geometry:

    feedpoint ---------------------------- far end (open)   height h
        |
        | vertical drop, length h
        |
        +========== return run =========== station          ground

The return path stands for either real installation: the coax shield
carrying common-mode current back to the station, or a counterpoise wire
thrown out along the ground.  It is not a passive reference.  It
radiates, it resonates on its own with a half-wavelength period in
(drop + run), and when that approaches a half wave it dominates the
feedpoint outright -- antenna length stops mattering.  A half wave on
20 m is about 35 ft of drop plus run, and the resonance repeats every
half wave above that, so most installations sit near one of them on some
band.  (An earlier draft said 25 ft was a half wave on 20 m.  It is not:
34.7 ft is, and 25 ft is a half wave at 19.7 MHz.  No fitted number
depended on the claim, which is measured against (drop+run)/lambda
directly.)

## Parameters

Split by what the user can actually measure.

| quantity | role | note |
|---|---|---|
| wire length | user control | the answer being sought |
| height `h` | user control | the number people know |
| return length | user control | default 25 ft |
| soil type | user control | three standard soils |
| conductor diameter | user control | fixed at #14 AWG today |
| transformer ratio | user control | 1, 4, 9, 49, 64 |
| `Z0` | derived | Schelkunoff, from `a` and `l` |
| `ka`, `kr` | fitted | `Z0` scales; ground lowers it, both near 0.75 |
| `alpha_a`, `alpha_r` | fitted | nepers per wavelength, loss and radiation |
| `beta_a`, `beta_r` | fitted | not assumed from a velocity factor |
| velocity factor | derived | see below |

**Velocity factor is an output, not an input.**  It is not an
independent physical quantity: it is the emergent consequence of
conductor diameter, height, return path, insulation and sag.  It was a
user control only because none of those were modeled, making it the one
fudge factor absorbing all of them.  Once height and diameter are
explicit, leaving it settable would let the user set the same physical
effect twice.  `?vf=` is still read as an override so existing links
resolve, following the `len`/`len_m` precedent.

Soil is exposed but must not be labeled as if it were a quality axis.
"Better" ground does not mean a better match: it means a sharper
resonance, deeper minima and higher peaks.  Permittivity shifts the
effective electrical length while conductivity damps, and the two do not
co-vary monotonically across the three standard soils.

## Where the constants come from

NEC, offline, once.  It does not belong in the *scoring loop*: it models
the environmental unknowns only if told what they are, and assumed
values yield a precise answer to a question nobody asked -- the error
bar does not shrink, it hides behind more decimals.  The cost is real
too, sweeping every candidate length by band by frequency step in a
single-file Pages document.

That objection does not reach a different idea: one NEC run on demand,
after the user has chosen a length, against the height, return path and
soil they have already entered.  That is bounded work on a geometry the
user has described, and it checks the installation rather than the
envelope, which is exactly where this model is weakest.  Worth doing.

Licensing does not obstruct that, because it was settled first: the repo
and the page are GPL-3.0-or-later, so a wasm nec2c inside `docs/` is GPL
object code distributed from a GPL repo, and the page combining with it
is a combined work that is already GPL.  What remains is the ordinary
obligation rather than a question of principle -- a corresponding source
offer for the wasm build, and a check that the exact GPL version nec2c
carries is one GPLv3 can combine with.

So NEC is a calibration and validation instrument.  **What reaches the
page is constants and caveat text, never code.**

The modeler itself lives in `nec/`.  An earlier draft of
this note had it staying outside the repo on license grounds, which
confused two separate things.  PyNEC is GPL-3.0-only and is a declared
PyPI dependency, not vendored; the repo is GPL-3.0-or-later, which
combines with it, and nothing here copies PyNEC or nec2c source.
Separately, and still true, a program's numeric output is not covered by
the producing program's license, so the fitted constants carry no
obligation of their own into the page.

Keeping it in the repo is the point rather than a concession.  The
page's claim to be defensible rests on constants with stated assumptions
and a bounded error; constants whose producing code has been discarded
cannot be checked by anyone.

### Method

1. Validate the driver against textbook cases before trusting it --
   quarter-wave monopole over perfect ground, free-space half-wave
   dipole.  Both should land within the overshoot thin-wire
   segmentation predicts.
2. Sweep the grid.  Antenna length is swept in wavelengths; height and
   return length are held in meters so every grid point is an
   installation someone could build.  Frequency is a real axis, for the
   reason under Conventions above.
3. Decide the fit form against the data before fitting to it.
4. Fit `alpha`, `beta` and a series loss term together, so both ends of
   the model land at once rather than one being forced by the other.
5. Bound the error across the parameter space.  That bound becomes the
   caveat on the plot, e.g. "within ~2x over 20-60 ft, 1-30 MHz,
   15-30 ft high".

### The decomposition hypothesis

Whether the return path earns a separate additive term is a structural
question, tested rather than assumed:

    H1:  Zin(l, ret) = Za(l) + Zr(ret)

the antenna and the return as two lines in series at the feedpoint.  If
H1 holds, the two fit independently and the return gets a clean additive
term -- the cheap, interpretable outcome.

It is falsifiable.  Under H1, `Zin(l, ret_b) - Zin(l, ret_a)` depends
only on the return lengths, so holding frequency, height and soil fixed
and sweeping antenna length should leave that difference constant.
Scatter comparable to the difference itself falsifies it and means the
two are coupled, in which case the return resonance must enter
multiplicatively or through the antenna's own `alpha`.

Measured, H1 holds: see finding 7.  Note that the swamping in finding 4
is *evidence for* additivity rather than against it.  When `Zr`
dominates `Za`, their sum is `Zr`, which is exactly the flat
antenna-length dependence observed.  An earlier draft of this note had
that backwards.

## What NEC measured

First results, 2026-08-09.  Instrument as above, in `nec/`.
Driver validated against textbook cases before anything else -- a
quarter-wave monopole over perfect ground reads 39.5+j22.7 against
~36+j21, a free-space half-wave dipole 79.1+j45.2 against ~73+j42, both
overshooting in the direction thin-wire segmentation predicts.

All figures at 14.2 MHz, #14 AWG.

1. **The half-wave anchor holds.**  The page reads 2480+j0 at its own
   half wave against the 2450 anchor; NEC gives 2600-3100 for
   `h >= 10 m`, rising to 4800-6200 at `h = 5 m` with a short return.
   The anchor is 10-20 percent low and otherwise sound.

2. **The quarter-wave anchor is not a real quantity.**  NEC spans
   133-3500 ohms at a quarter-wave antenna wire depending on height,
   return length and ground.  The page's 52 ohms sits below almost
   every configuration measured.  Cause is definitional: the page's `l`
   is the antenna wire, but the resonator is `l` plus the drop plus the
   return.  Bonded to ground over average earth, a quarter-wave *top
   wire* reads 183 ohms at `h = 2 m`, 2193 ohms at `h = 5 m` (where the
   total reaches a half wave), and 69 ohms at `h = 10 m`.  Ground loss
   adds to it: a `lambda/4` inverted L reads 13.8 ohms over perfect
   ground and 142.8 ohms over average ground at `h = 2 m`.
   Consequence: the impedance mode's penalty on odd-quarter-wave
   lengths is substantially an artifact.

3. **Measured half-wave reactance is strongly inductive**, +j1200 to
   +j1500 at `h >= 10 m`, where the coth model gives j0 at its own
   resonance.  Systematic, and the reason `beta` has to be fitted
   rather than assumed from a velocity factor.

4. **The return path is a resonator in its own right.**  Sweeping
   return length alone at a fixed antenna wire, `|Z|` oscillates with a
   clean half-wavelength period in (drop + run), a factor of 2-3.5:

   | (drop+run)/lambda | 0.71 | 0.92 | 1.21 | 1.42 | 1.71 | 1.92 |
   |---|---|---|---|---|---|---|
   | `\|Z\|` at `lambda/4` | 173 | 546 | 265 | 462 | 296 | 422 |

   When (drop + run) approaches a half wave the return resonance
   dominates the feedpoint entirely and antenna length stops mattering:
   at `h = 5 m` with a 5 m return, `|Z|` is flat at 1800-3500 ohms
   across `l/lambda` from 0.05 to 0.40.  That is the failure mode where
   a user lengthens the wire and nothing improves.  A 15 m coax run is
   a half wave near 8.9 MHz, so this is common, not exotic.

5. **Height matters most below 10 m.**  Half-wave `|Z|` barely moves
   between 10 and 20 m (2674-3047) but reaches 3500-6200 at 5 m with a
   short return.

6. **Ground is not a single quality axis at low height.**  Sweeping
   `l/lambda` per ground type, the curves keep their shape and change
   level, so this is loss rather than a resonance shift -- but the
   ordering is not monotonic in "poor/average/good".  At `h = 3 m`
   better ground sharpens the resonance, giving the lowest minima (148
   against 305 for poor) and the highest peak (5480 against 4577).  At
   `h = 5 m`, average reads lowest across the whole range and good
   highest.  Permittivity shifts the effective electrical length while
   conductivity damps, and the two do not co-vary monotonically across
   the three standard soils.  Low heights are worth getting right:
   improvised wires of this sort get hung low.

7. **The return path is additive, to about 20 percent.**  From the full
   sweep, 106848 points over 4 frequencies, 8 heights, 7 return lengths,
   3 soils and 159 lengths from 0.05 to 4 wavelengths, with no failed
   solves.  Testing H1 across 72 combinations of frequency, height, soil
   and return-length pair, the scatter of `Zin(ret_b) - Zin(ret_a)`
   across antenna length, relative to the size of that difference:

   | | residual |
   |---|---|
   | median | 0.20 |
   | under 0.35 | 89 percent of cases |
   | over 0.5 | 6 percent of cases |

   So the return path earns a separate additive term, and the antenna
   and the return can be fitted independently.  The residual is
   uniform with height in the typical case -- median 0.17 at 10 m, 0.18
   at 20 m, 0.22 at 3 m -- but its tail is entirely at low height, where
   it reaches 0.89 against 0.25 for `h >= 10 m`.  Mutual coupling
   between the wire and its return is what H1 neglects, and that is
   strongest when the two are close together.  A coupling correction
   growing as `h/lambda` falls is the shape to fit.

The structural lesson under the first six is the geometry section above:
feedpoint impedance is set by the whole conductor geometry, not the
antenna wire alone.  Finding 7 says that geometry decomposes, which is
what makes it tractable.

## Fit results

First fit, `nec/fit.py`, over 96 groups of frequency by
height by soil, each holding 159 lengths by 7 return lengths.  Residuals
are taken on the complex logarithm: `|Zin|` spans tens of ohms to
kilohms across a sweep, so an absolute residual would fit the peaks and
ignore everything else, while a log residual is relative in magnitude
and plain angular error in phase, which is what SWR responds to.

| | magnitude error | phase |
|---|---|---|
| median | x1.22 | 10-16 deg |
| 90th percentile | x1.32 | |
| worst | x2.29 | 64 deg |

Each line carries a scale `ka` or `kr` on its Schelkunoff `Z0`.
Schelkunoff's figure is an average over an isolated wire in free space,
and over ground the image lowers it; both scales come out near 0.75,
which is that effect.  Adding `ka` alone took the median from x1.28 to
x1.22 and the 90th percentile from x1.39 to x1.32.

Tried and rejected: a susceptance terminating the open end, standing for
end effect.  It fitted to zero in every group (median 0.000, largest
0.004) and changed no error figure in the fourth decimal.  The five
parameter model is nested inside that seven parameter one, so the
comparison was fair, and end effect is simply not what the model was
missing.  Dropped rather than kept at zero.

Fitted values, with `alpha` in nepers per wavelength.  Per meter it came
out proportional to frequency, which is only the statement that a wire
loses a fixed fraction of its power per wavelength; per wavelength the
numbers are comparable across bands, which is what an interpolable
coefficient surface needs.

| parameter | median | range |
|---|---|---|
| `alpha_a` | 0.100 | 0.038 - 0.568 |
| `vf_a` | 1.000 | capped, see below |
| `ka` | 0.791 | 0.612 - 1.473 |
| `alpha_r` | 0.477 | 0.015 - 3.000 |
| `vf_r` | 0.934 | 0.589 - 1.150 |
| `kr` | 0.733 | 0.425 - 1.189 |

Three things worth drawing out.

**The antenna's velocity factor wants to be 1.0, not 0.95.**  Left free,
`vf_a` fitted to 1.003 and drifted as high as 1.018.  That is not a wave
outrunning light.  `vf_a` is a parameter of an equivalent line standing
in for a radiating structure, and `beta` absorbs what the line form
omits: `Z0` varies along a real wire where Schelkunoff's figure is an
average, the open end is capacitively loaded, and the thing radiates.
Capped at unity it costs 0.5 percent of median accuracy, and 75 percent
of groups then sit against the bound -- so read the result as "1.0 or a
little above", not as a measured phase velocity.

What survives is the direction, which is the part that matters for the
page: the wire is not propagating at 0.95.  The apparent shortening that
0.95 was standing for is the return path in series plus `Z0` varying
with length, both of which this model now carries explicitly.  That is
the quantitative form of the argument that velocity factor is emergent
rather than physical -- model the geometry and it goes away.

That 75 percent of groups press against the cap is itself a signal: a
rail-pinned parameter usually means the model form is missing something,
here most likely the end effect and the length dependence of `Z0`.

**The return path is about three times lossier than the antenna**,
`alpha_r` 0.405 against `alpha_a` 0.126, and its characteristic
impedance is about three quarters of the free-space thin-wire figure
(`kr` 0.741).  Both are what a wire lying along lossy ground should do.

**The error is flat with height, but its tail is not.**  Median error
sits between x1.23 and x1.31 at every height.  The worst cases are all
at low height -- x2.33, x2.25 and x2.19 at 2, 3 and 5 m, against x1.40
or better everywhere at 7 m and above -- and specifically at low
`h/lambda`, the worst being 1.9 MHz over poor ground where a 2 m height
is 0.013 wavelengths.  This is exactly the mutual coupling finding 7
predicted the additive model would neglect, and it is the term still to
add.

Parameters at a bound, over the 90 groups now fitted:

| parameter | at bound |
|---|---|
| `alpha_a`, `ka`, `alpha_r`, `kr` | 0 percent |
| `vf_r` | 8 percent |
| `vf_a` | 81 percent, by construction |

`vf_a` is the one to read carefully.  Its upper bound *is* 1.0, so the
median being 1.0 is not a measurement -- it is the cap.  What the fit
says is that the antenna line wants to be at least that fast, not that
it is exactly that fast, and the direct measurement in NEC (the
resonance peak at 69.5 ft, implying 1.010) is the evidence that matters
for anything resting on it.

## Error bound

The bound the caveat text should carry.  Taken over 96 groups, each
fitted across 159 lengths and 7 return lengths.

This section measures the retired 1-D fit.  What ships is the 2-D NEC-4.2
table, and it is measured two ways, because the two answer different
questions.

Per group, an RMS over the couple of hundred lengths in one (soil,
frequency, height, counterpoise) cell, which is what the fit is scored on:

| | median | 90th | worst |
|---|---|---|---|
| flat top | x1.247 | x1.335 | x1.591 |
| sloper | x1.163 | x1.265 | x1.394 |

Per length, which is what a user meets, because they pick a length and not
a group:

| | median | 90th | 99th | worst | phase, 90th |
|---|---|---|---|---|---|
| flat top | x1.14 | x1.43 | x2.23 | x5.32 | 20 deg |
| sloper | x1.10 | x1.31 | x1.72 | x3.80 | 14 deg |

The per-group median flatters and the per-group 90th understates: an RMS
over a group hides that group's own tail.  The page quotes the flat top's
per-length figures, and a test holds it to `coefficients2d.json` so a
refit cannot leave the claim behind.

Both are in sample -- fitted and measured on the same sweeps -- but how
much that flatters them has now been measured rather than assumed.

`nec/holdout_check.py` drops one frequency, refits the whole pipeline on
what is left, and measures at the frequency held back.  14.175 MHz, which
is interior, so this tests interpolation in frequency rather than
extrapolation past the ends:

| at 14.175 MHz | median | 90th | 99th | miscall at 9:1 into 3:1 |
|---|---|---|---|---|
| the table that saw it | x1.154 | x1.497 | x2.363 | 25.3% |
| a table fitted without it | x1.170 | x1.547 | x2.491 | 27.2% |

Removing a fifth of the data costs 1.9 points of miscall and 3 percent on
the per-length 90th.  So the figures above are optimistic, and not by
much.

That is a stronger result than it looks, because the table has no
frequency index at all: five coefficients against `h/lambda` and
`z/lambda`, nothing else.  Indexing that way asserts that the problem
scales with wavelength, and holding out a frequency removes exactly the
geometries only that frequency reaches.  The assertion is the one this
whole design rests on and it had never been tested.  It holds.

Three sets of figures, and only the last says anything about what a user
will see.

**In-sample, per-group.**  Fitting coefficients independently for every
frequency, height and soil gives x1.35 worst for `h/lambda >= 0.05`.

**In-sample, tabulated.**  The page cannot fit per installation; it
carries a small table and interpolates.  Over the whole sweep that costs
little: x1.25 median, x1.32 at the 90th, x1.38 worst.

Both are *in-sample* -- fitted on `sweep.npz`, measured on `sweep.npz` --
so both are optimistic by construction.

**Out of band.**  `out_of_band.py`, since retired with the 1-D fit,
solved fresh NEC cases at five
frequencies the sweep never used, across three sites.  That is the
holdout, and it is in the axis that matters: the sweep has four
frequencies and the page evaluates nine bands.

| | median | 90th | worst |
|---|---|---|---|
| per-group, in-sample | x1.22 | x1.28 | x1.35 |
| tabulated, in-sample | x1.25 | x1.32 | x1.38 |
| tabulated, out of band | x1.30 | x1.38 | x1.44 |

**Every figure in that table is a per-group RMS, not a cap on any one
length, and the page must not quote it as one.**  Point by point across
the same out-of-band cases:

| | error on \|Z\| |
|---|---|
| median point | x1.18 |
| 90th percentile | x1.48 |
| 99th percentile | x2.42 |
| worst point | x3.45 |

So 14 percent of individual lengths are worse than x1.5 and 4 percent
worse than x2.  The page says "typically within 1.2x, and within 1.5x
nine times in ten", and says explicitly that this is not a cap.  An
earlier version printed x1.5 alone, which reads as a guarantee that one
length in seven breaks.

A leave-one-group-out split was considered and rejected: it would refit
on less data and degrade the coefficients that ship, to answer worse a
question the out-of-band check already answers.

What `h/lambda >= 0.05` means in practice, since the user sets height in
feet and not wavelengths:

| band | height above which the bound holds |
|---|---|
| 160 m | 26 ft |
| 80 m | 13 ft |
| 40 m | 7 ft |
| 20 m and up | 4 ft or less |

**Below `h/lambda = 0.05` nothing is fitted at all.**  The table holds
flat below its first node, so figures there are extrapolation: x1.50
median and x3.12 worst, measured but not claimed.  In practice that is
160 m and 80 m with a low wire.  It is not a region to refuse to answer
in, but it is one where the number on screen should be visibly hedged.

The floor is where it is for two reasons that turn out to be one.  The
page already stops claiming accuracy at 0.05, so fitting hard below it
was claiming a precision the page simultaneously disclaimed.  And it is
exactly where the unusable data ends: with a 0.02 floor some 327
non-physical points survive into the fit, 23 percent of one group at
1.9 MHz over poor ground, while at 0.05 there are none.

**The bound survives conductor gauge.**  The sweeps run entirely at #14,
so `a/lambda` is the one planned axis never executed and the coefficients
have seen a single diameter.  `nec4_gauge_sweep.py` and
`nec4_gauge_check.py` close that: 22896 further NEC-4.2 solves over #12,
#14, #18 and #22, a factor of 3.2 in diameter, evaluated against the
shipped table at each gauge's own radius -- which the model responds to
through Schelkunoff's `Z0` without being fitted per gauge.

| gauge | radius mm | median | 90th | worst |
|---|---|---|---|---|
| #12 | 2.053 | x1.230 | x1.386 | x1.440 |
| #14 | 1.628 | x1.235 | x1.382 | x1.451 |
| #18 | 1.024 | x1.242 | x1.377 | x1.487 |
| #22 | 0.644 | x1.247 | x1.377 | x1.523 |

#14 is the control: the table is fitted there, so it should land on the
table's own x1.247 / x1.335, and it does.  The other three are
indistinguishable from it, so the page's #12 to #22 holds.  The earlier
answer to this question came from a NEC-2 grid and a checking script that
retired with the 1-D fit; both are now the solver the tables use.

Agreement, which is the question the page cares about -- the shipped
#14 table used unchanged against each gauge:

| gauge | radius mm | median | 90th | worst |
|---|---|---|---|---|
| 12 | 1.026 | x1.27 | x1.34 | x1.41 |
| 14 | 0.814 | x1.26 | x1.33 | x1.39 |
| 18 | 0.512 | x1.26 | x1.34 | x1.40 |
| 22 | 0.322 | x1.27 | x1.36 | x1.44 |

Off-gauge is indistinguishable from #14's own x1.39.  Dependence
explains why: refitting per gauge moves the coefficients only slightly
and monotonically -- `alpha_a` 0.105 to 0.096 across the whole range,
`ka` 0.764 to 0.787, `alpha_r` 0.604 to 0.505, `kr` 0.726 to 0.748 --
because Schelkunoff's `Z0` already carries the dominant `log(radius)`
term, leaving the fitted scales little to absorb.

`vf_a` fits to 1.0000 at every gauge, which also disposes of the idea
that wire thickness was behind it.

Tested at medium soil on a reduced grid, three heights by three return
lengths, since one axis was the question rather than the whole surface.

Two hypotheses were tried against that low region and both failed, which
is worth recording so they are not tried again:

- **End effect**, a susceptance terminating the open end.  Fitted to
  zero in all 96 groups, largest 0.004.
- **A height-dependent `Z0`**, blending Schelkunoff's isolated-wire
  figure with the wire-over-image value `60 ln(2h/a)` by an effective
  length, on the theory that whichever return conductor is nearer sets
  `Z0`.  Median x1.220 against x1.225, low region x1.272 against x1.295,
  and the worst case got *worse*.  A wash.

The residual that remains is structured in antenna length rather than
return length -- flat against return length, but running from +1.09 in
log magnitude at short lengths to -0.57 at three wavelengths, with an
oscillation peaking near the odd quarter waves.  So it is not the mutual
coupling finding 7 predicted; that attribution was wrong.  Something in
how loss scales with length is still unmodeled.

Chasing it further is not obviously worth it.  The remaining error lives
in six groups at `h/lambda < 0.02`, which is 160 m with a wire 6 to 16 ft
up over poor soil -- a marginal antenna whose real behavior is
dominated by the installation variance this model already refuses to
predict.  x1.22 median is comfortably inside the severalfold spread that
height, counterpoise and common-mode current impose on a real
installation.

## The decision metric: how often a recommended length is not usable

The error bound above is about `|Z|`, and `|Z|` is not what the page
decides on.  A user asks whether a length will match through their tuner,
which is SWR at the radio, from R and X together.  `nec/miscall_check.py`
measures that directly: the shipped table and NEC, at the same geometry,
each taken through the unun, each compared against the tuner's limit.  A
miscall is a length the model calls usable and NEC does not.

Against the converged sweeps the tables are now fitted from, in sample:

| unun into tuner | flat top offers | of those, wrong | sloper offers | wrong |
|---|---|---|---|---|
| 9:1 into 3:1 | 35.8% | **23.6%** | 34.7% | 18.7% |
| 9:1 into 5:1 | 64.7% | 19.4% | 64.6% | 14.0% |
| 9:1 into 9:1 | 87.9% | 11.7% | 86.3% | 8.6% |
| 4:1 into 3:1 | 17.2% | 25.0% | 13.2% | 17.1% |
| 1:1 into 3:1 | 0.5% | 32.6% | 0.3% | 21.9% |

At the page's own defaults -- 9:1 into a 3:1 rig tuner -- nearly one
length in four that it offers is not usable.  By band, flat top, same
setting: 160 m 46.2 percent wrong, 40 m 27.6, 20 m 25.3, 10 m 15.0.  It
is worst on the low bands and the tight tuners, which is the case a
random wire exists for.  (Measured against the density-1 sweeps the
constant-`alpha` table read 21.9 percent overall and 26.0 against the
converged ones; the first difference is the flattery documented under
the converged re-sweep, the second the falling loss documented under
the peaks.)

Three things this says that the `|Z|` bound does not.

The error lives in the reactance.  Computing the same table with the
reactance discarded -- taking `|Z|` as a resistance -- gave 8.2 percent
where the honest figure was 21.9 (both against the density-1 data).
The fit's objective does carry phase, and the table now records it, but
a magnitude-only bound hides most of what a user meets.

It is not an interpolation problem, so snapping a user's height or
counterpoise to a table node would not help: the table is evaluated at
each group's own geometry when this is measured, and the misses
concentrate at the resonance structure the form gets wrong (see "The
peaks are too sharp").

And it is not a measurement problem either, which was tested twice
rather than assumed.  The decks were rebuilt to fix a segment-grading
defect at the feedpoint and re-swept -- 480,000 NEC-4.2 solves -- which
moved individual impedances by a median of x1.03, a 99th percentile of
x2.2 and a worst of x6.5, and the miscall rate did not move at all:
21.9 percent before, 21.9 after.  Then the converged re-sweep replaced
the data outright and the rate moved only because the scoring got
honest, not because the model got better.  The fit re-absorbs data
changes.  What sets this number is the model form, and better data
cannot reach it.

This is the number for judging any change to the model.

## What it does to the recommendations

Swapping the model moved the picks a long way, which is the change worth
checking hardest since recommending lengths is the whole job.  At the
page's defaults -- 30 ft up, 25 ft of return, medium soil, 9:1, the
80/40/20/15/10 band set:

| old model | new model |
|---|---|
| 180.0 ft (SWR 1.59) | 80.5 ft (2.02) |
| 169.1 ft (1.61) | 151.2 ft (2.38) |
| 116.3 ft (2.00) | 180.1 ft (2.93) |
| 99.9 ft (2.09) | 195.2 ft (2.99) |
| 89.9 ft (2.22) | 110.4 ft (3.56) |
| 78.1 ft (2.28) | 126.5 ft (4.19) |

Agreement with the published tables improved: the median gap from a pick
to a published length falls from 6.5 ft to 5.5 ft, and picks landing
within 5 ft go from 1 in 6 to 3 in 6.  The new model is also uniformly
less optimistic, best score 2.02 against 1.59, which is what adding a
lossy return path should do.

But it rates two staples badly -- 71 ft at 6.56 where the old model said
2.72, and 119 ft at 4.44 against 2.03 -- so both were checked against
NEC directly rather than trusted.  **NEC agrees with the model**, and
the two lengths fail for entirely different reasons.

**71 ft is a velocity-factor casualty.**  NEC gives it SWR 10.9 on 40 m
and 5.6 on 20 m at the default site.  A published table dodges
`n * lambda/2` computed at vf 0.95, which puts the 40 m half wave at
65.3 ft and leaves 71 ft 8.7 percent clear.  The fitted antenna line
runs at 1.00, putting it at 68.8 ft and leaving 71 ft 3.2 percent clear;
on 20 m the second half wave moves from 15.4 percent clear to 4.6.  So
71 ft sits on the shoulder of a resonance on two bands at once, and the
published tables miss it because they assume a wire slower than the one
NEC models.

That generalises uncomfortably: if the effective velocity factor is
nearer 1.00 than 0.95, the published lengths are systematically placed
against resonances about 5 percent too short.  Stated carefully, `vf_a`
is a parameter of the antenna line inside a two-line model, not a
directly measured wave speed -- but NEC confirms the behavior it
predicts at 71 ft without reference to the fit.

Checked for a published refutation of 71 ft, and there is none.  The
only documented criticism of the source list is James KB5YN catching
that VE3EED's original table called 220 ft good when it is the tenth
half-wave multiple on 15 m; VE3EED accepted it and recomputed out to
500 ft.  That is an arithmetic slip inside the method, not a challenge
to it.

The nearest independent corroboration is J.C. Sprott's technote, which
runs the same avoid-the-resonances search from scratch and arrives at
74 ft excluding 160 m, never mentioning 71.  That is 4 percent off the
staple in the same direction as this model, and 74 ft is what this
page's classical mode already picks for that band set.  Sprott also
treats the feedline as part of the electrical length, which is finding 4
in print years earlier, and handles velocity factor explicitly, which is
the parameter the 71 ft result turns on.

Cutting the other way, Ham Radio Outside the Box measured an 84 ft wire
at 21-307 ohms across the bands, challenging the 450 ohm and 9:1
convention rather than the lengths.  Those figures are lower than this
model or NEC gives and sit against finding 2, though a commenter
attributed them to the 3 ft coax jumper used, and the piece reports no
height, counterpoise or modeling.

So the 71 ft result here is novel rather than a restatement of known
criticism, which is a reason to hold it more loosely, not less: it rests
on one sweep with an unswept return height worth up to 4.6x and
segmentation unconverged at 13 percent.

The 25 ft return default was the obvious suspect for the 71 ft verdict,
and it is not the cause.  Scored across return runs from 10 to 130 ft at
the default height, 71 ft reads 7.4, 6.6, 7.5, 6.5, 5.9 and 5.6: bad at
every one of them, and worst nowhere near the default.  The verdict is
robust to the parameter most likely to have produced it.

Two things did come out of that check.  Most published lengths improve
with a longer return -- 29 ft goes 4.5 to 2.4, 41 ft goes 3.7 to 2.0,
107 ft goes 3.8 to 2.4 -- which supports the ARRL's quarter-wave
counterpoise advice against this page's 25 ft default.  And with a long
return the whole curve flattens: at 130 ft every offered length scores
between 2.1 and 2.3, where at 25 ft they spread 2.0 to 3.6.  **Get the
counterpoise right and the wire length matters less**, which is arguably
the more useful advice than any particular length.

Against changing the default: 25 ft gives the best agreement with the
published tables of any return length tried, median gap 3.5 ft against
5.1 to 9.5 elsewhere.  That looks like coincidence rather than a reason,
but it is worth knowing before moving it, and a typical user really does
just have their coax run.

Later, with the return redefined as the whole conductor including the
drop, the same question was asked again and answered by sweeping.  The
best return is about 75 ft, and it stays about 75 ft whichever bands are
selected: 75 with 40 m lowest, 87 with 80 m, 72 with 20 m.  It therefore
tracks neither a quarter nor a half wave of anything, which disposes of
two tidy explanations -- the ARRL counterpoise figure, and the idea that
a half-wave return keeps its own resonance out of the way.  A long
return simply holds its impedance high and flat across the bands.

The default stays at 55 ft, a 25 ft coax run off a 30 ft drop, because
it is what people have rather than what they would build.  It costs
about 0.7 in the best worst-band SWR.

It is not an artifact of the near-ground trouble described below,
either.  Located directly in NEC rather than through the fit, the 40 m
resonance peak sits at 69.5 ft, implying a velocity factor of 1.010,
against the 65.3 ft that 0.95 predicts.  Raising the return path from
5 cm to 2 m moves that peak by three inches, 69.5 to 69.8 ft, so the
regime where implementations part company has no bearing on where the
resonance is.  `|Z|` at 71 ft reads 3900 to 4800 ohms across the same
range.

That the peak is measured slightly *above* unity is worth noting: the
model's `vf_a` was capped at 1.0, so it places the resonance marginally
short of where NEC puts it, and is if anything generous to 71 ft.

The rejection has since survived every parameter that could have caused
it.  71 ft scores 6.2 to 10.1 across heights from 15 to 60 ft and all
three soils, and 5.6 to 7.5 across return runs from 10 to 130 ft.  84 ft
over the same ground runs 2.4 to 6.2.  There is no corner of the
parameter space where 71 ft comes good.

That makes it the page's biggest problem of trust rather than of
accuracy.  71 ft is the best known random wire length there is; a user
who finds it missing from the suggestions will conclude the tool is
broken long before concluding the tables are wrong.  Silently omitting
it is the worst of the options available, and the page should say what
it thinks and why.

**119 ft fails the other way.**  At vf 1.00 it is *more* clear of the
80 m half wave than at 0.95, 9.3 percent against 4.5, yet NEC still
gives SWR 13.6 there.  It is not near a half wave; it is carrying large
reactance, which a keep-out on `n * lambda/2` cannot see by
construction.  This is the "continuous cost instead of a binary
keep-out" gain, appearing in a real case.

84 ft checks out on both counts -- NEC 7.7 / 2.0 / 1.3 / 1.5 / 3.0 --
and the new model's best pick of 80.5 ft sits beside it.

## Known unchecked

Things the numbers above rest on that were never tested, kept here so
they are not mistaken for settled.

**Segmentation is not converged.**  Every solve used 20 segments per
wavelength, the usual accuracy rule, and that choice was never checked.
Against 80 segments per wavelength the same geometry moves 13 percent at
both a quarter and a half wave, 4 percent at one wavelength and 2
percent at two.  So the x1.5 bound is measured against NEC-at-20-
segments, not against converged NEC, and part of it is the discretisation
rather than the model.  Convergence is also not monotonic between 40 and
80, so the true figure is not simply "13 percent worse".

**The return conductor is the same wire as the antenna.**  Both take one
radius, so the gauge sweep moved them together.  A real coax shield is
nearer 8 mm than 0.8 mm, a factor of ten the sweep never explored, and
the return is the term the low-height error already lives in.

**The wire is horizontal.**  No slope, no inverted L, no sag, though a
sloper is at least as common as a flat top for a random wire.  That was
an assumption and is now a measurement: `slope_check.py` puts a sloper
fed at 1.5 m against the flat model, and neither obvious substitution
holds.

| | apex | vs flat at the apex | vs flat at the mean height |
|---|---|---|---|
| 7.15 MHz | 10 m | med x5.72, worst x22.10 | med x1.66, worst x4.23 |
| 7.15 MHz | 20 m | med x1.57, worst x2.20 | med x5.22, worst x24.22 |
| 14.175 MHz | 10 m | med x1.81, worst x3.15 | med x2.78, worst x5.79 |
| 14.175 MHz | 20 m | med x1.80, worst x3.89 | med x1.49, worst x2.15 |

The best cell is x1.49 median, outside the model's own x1.35 bound, and
there is no consistent winner: the mean height is far closer at a 10 m
apex on 40 m and far worse at 20 m.  So a sloper is a different antenna
and the page does not cover it.

An effective height does exist -- searched per case, the best flat height
reproduces a sloper to x1.05 to x1.09 median, better than the model's own
bound, so the two-line form can represent one.  It cannot be used,
because the height it wants depends on frequency: the same 6 m apex needs
2.5 m at 7.15 MHz and 1.0 m at 14.175.  One antenna cannot have two
heights and the page scores several bands at once, so no geometric
remapping survives.  Supporting slopers means modeling them.

**The classical mode still defaults to vf 0.95.**  The impedance mode's
71 ft result says that figure places the resonances about 5 percent too
short, so the two modes now disagree about which lengths are safe, and
the classical one agrees with the published tables partly by sharing
their assumption.  Changing its default would move every classical
recommendation and break agreement with tables the user can look up, so
it is a decision rather than a fix.

## The return path's geometry, measured

Two things about the return were fixed for the whole sweep and are
choices rather than measurements.  `geometry_check.py` puts numbers on
both, at the page's default site.

**Bearing barely matters.**  A counterpoise wire often runs out along
the antenna; a feedline acting as counterpoise usually heads away, at
anything from in line to square.  Across 0 to 180 degrees the feedpoint
moves 1.20x on 80 m and 1.07x or less on every other band.  The return
lies close to lossy ground, whose image largely cancels its coupling to
the elevated wire, so which way it points is nearly irrelevant.  All the
arrangements are real and the model does not need to choose between
them.

**Height matters more than anything else in the model.**  Raising the
return from 5 cm to 1-2 m moves the feedpoint by up to 4.6x on 20 m,
2.6x on 10 m, 2.3x on 15 m -- far outside the x1.5 bound, and larger
than height, soil or gauge.

| 84 ft, return height m | 0.01 | 0.05 | 0.25 | 1.0 | 2.0 |
|---|---|---|---|---|---|
| 20 m SWR | 1.7 | 1.3 | 2.4 | 4.1 | 6.2 |
| 10 m SWR | 3.3 | 3.0 | 2.6 | 3.8 | 6.6 |

The sweep's 5 cm stands for a feedline or counterpoise **lying on the
soil**, which is the common install.  It is not safe in general.  An
elevated counterpoise, elevated radials, or a feedline on standoffs is a
different antenna, and the fitted coefficients say nothing about it.

### The 5 cm standoff, revisited with NEC-4

This section used to add that 0.01 m gives nearly the same answer as
5 cm, so the standoff was safe for a wire on the ground.  **That is a
PyNEC observation and NEC-4.2 does not reproduce it.**  On the 107 ft
wire, 30 ft up, 25 ft return at 7.15 MHz:

| return z | PyNEC | NEC-4.2 |
|---|---|---|
| 0.01 m | 1296.9 | 2584.9 |
| 0.05 m | 1405.9 | 1969.4 |
| ratio | x0.92 | x1.31 |

Eight percent against thirty-one.  The claim held for the solver it was
measured on and not for the one that models this regime better.

The standoff exists because NEC-2 cannot do better: a wire bonded to the
ground plane shorts the source, so the return must float.  NEC-4 can put
wires at and below the interface, so the assumption is testable.
`ground_contact.py` does it, and three things have to be right: the
vertical drop must be split at z = 0, because no segment may span the
interface; `GE 0` rather than `GE 1`, which rejects anything at or below
it; and z = 0 exactly must be avoided, since a wire lying *in* the
interface returns 281 ohms where 1 cm above gives 2585 and 1 cm below
gives 2123.

Below the surface the answer is stable -- 2123, 2059, 2069, 2147 at 1,
5, 10 and 50 cm down -- so this is a real regime rather than a numerical
edge.  Comparing 5 cm above against 5 cm below across frequency, height
and length:

- near half- and full-wave multiples, where `|Zin|` is high and the
  antenna wire dominates, burying the return moves it about 15 percent
- at a quarter wave, where `|Zin|` is low and the return path dominates,
  it moves it by up to **x5.02**

The second is the one that matters, because that is the regime the
length picker operates in.  So the standoff is not a harmless artifact;
it is a modeling assumption with teeth, and it was adopted for a
solver's convenience rather than for a physical reason.

#### The case we want is the one NEC cannot express

Neither position is the real one, and closing the bracket does not
help.  Narrowing it from 5 cm either side to 1 cm leaves it no tighter
overall and makes it worse where it matters:

| bracket | all | at a quarter wave |
|---|---|---|
| +/- 5 cm | median x1.15, worst x5.02 | median x1.57, worst x5.02 |
| +/- 1 cm | median x1.14, worst x5.24 | median **x2.19**, worst x5.24 |

The two limits do not converge on contact, and they cannot.  The
thin-wire kernel assumes a homogeneous medium around the conductor.  A
wire lying on the surface has half its near field in air and half in
soil, which is neither branch: approached from above it is entirely in
air, from below entirely in soil.  That is why z = 0 returns a value
consistent with neither side.  The above branch also runs out before
contact -- at 1 mm a #14 wire is 1.2 radii up, its surface 0.19 mm from
the soil, and the answer breaks an otherwise monotonic trend -- so it is
usable to about 1 cm and no further.

**Insulation does not rescue this**, which was worth checking because it
looks like it should.  A jacket is a few-percent effect, the same one
that gives insulated wire a velocity factor near 0.95 rather than 1.0:
it raises the effective radius and lightly loads the line.  It does not
move the conductor into the air regime, because soil at HF is a lossy
dielectric rather than a conductor:

| | 1.9 MHz | 7.15 MHz | 14.175 MHz | 28.85 MHz |
|---|---|---|---|---|
| loss tangent | 3.64 | 0.97 | 0.49 | 0.24 |

Skin depth is meters throughout -- 5.2 m at 1.9 MHz, 1.3 m at 28.85 --
so a wire in contact is not shorted to anything, and touching against a
millimeter off is not a discontinuity a jacket would protect against.
Coax and bare wire are the same case here.  That table also says the
soil changes character across the bands the page covers, from
conductor-like at 160 m to dielectric-like at 10 m, which is likely part
of why the bracket refuses to close uniformly.

So what justifies keeping the return above ground is mechanical rather
than electrical: **real ground is not flat.**  Coax drapes over grass,
leaf litter and ruts, so a centimeter or two of average clearance is a
fair description of a real installation, and it is a statement about the
install rather than a modeling convenience.  Burial is the wrong model
for something lying on top and the right one for radials under the turf,
which is a different antenna the page also invites.

### Swept, and the model can absorb it

53424 further solves over seven return heights from 0.01 to 3 m,
`return_height_sweep.py`.  The degenerate case where the return sits at
the antenna's own height is skipped: it leaves no vertical drop, and it
is the only thing that failed.

Agreement first.  The shipped table, fitted at a 5 cm return, holds only
while the return stays near the ground:

| return height m | median | 90th | worst |
|---|---|---|---|
| 0.01 | x1.31 | x1.42 | x1.43 |
| 0.05 | x1.25 | x1.33 | x1.37 |
| 0.15 | x1.31 | x1.40 | x1.44 |
| 0.50 | x1.44 | x1.89 | x2.15 |
| 1.00 | x1.57 | x2.02 | x2.19 |
| 2.00 | x1.69 | x2.71 | **x4.15** |
| 3.00 | x1.86 | x2.21 | x2.85 |

So the x1.5 bound survives to about 15 cm and breaks past that, which
puts a number on "assumed to lie on the ground".

Dependence is the good news.  Refitted per return height the model
reaches x1.16 to x1.38, so it can describe every one of these, and the
parameters move exactly where the two-line decomposition says they
should:

| return height m | `alpha_a` | `ka` | `alpha_r` | `vf_r` | `kr` |
|---|---|---|---|---|---|
| 0.01 | 0.109 | 0.784 | 0.959 | 0.874 | 0.710 |
| 0.05 | 0.107 | 0.782 | 0.570 | 0.944 | 0.810 |
| 0.15 | 0.105 | 0.780 | 0.383 | 0.964 | 0.797 |
| 0.50 | 0.103 | 0.788 | 0.271 | 0.985 | 0.834 |
| 1.00 | 0.101 | 0.807 | 0.308 | 1.000 | 0.877 |
| 2.00 | 0.104 | 0.746 | 0.296 | 0.988 | 0.922 |
| 3.00 | 0.105 | 0.771 | 0.159 | 1.000 | 0.796 |

The antenna line does not notice: `alpha_a` stays near 0.10, `ka` near
0.78, `vf_a` exactly 1.0000 throughout.  Everything happens in the
return line, where lifting the wire off lossy ground drops `alpha_r`
sixfold and pulls `vf_r` up to unity as the ground stops loading it.
That is the decomposition earning its keep: a change to one conductor
shows up in that conductor's parameters and nowhere else.

That suggested return height was an axis to tabulate rather than a
caveat to carry.  The full sweep says otherwise, and the reason is worth
recording.

### Why it stays a caveat

228960 solves over soil by frequency by antenna height by return height
by return length, `unified_sweep.py`, then fitted per group.

First, the axis to index on is **return height in meters**, not
`rh/lambda`.  That breaks the dimensionless-ratio convention and does so
for a reason: the return lies over a lossy half-space, and the image sits
about a skin depth down, which is an absolute length.  In these soils
that is 0.5 to 11.5 m across HF, the same order as the return heights
themselves, so absolute height is what the return line feels.  The
fitted parameters agree, moving monotonically against meters while
`rh/lambda` barely separates them.

Second, and decisively, **the model form fails before the table does**.
Giving every group its own best-fit coefficients -- the most the two-line
form can possibly do -- the error grows with return height:

| return height m | median | 90th | worst |
|---|---|---|---|
| 0.01 | x1.20 | x1.31 | x2.20 |
| 0.05 | x1.20 | x1.32 | x2.10 |
| 0.15 | x1.20 | x1.31 | x2.09 |
| 0.50 | x1.24 | x1.31 | x2.02 |
| 1.00 | x1.34 | x1.43 | x2.00 |
| 2.00 | **x1.60** | **x2.20** | x2.42 |

A 2D table over `h/lambda` and return height was built and measured
anyway, 480 numbers against the present 120.  Below 15 cm it matches
what ships, median x1.27 and worst x1.44.  Above it, median x1.36 and
worst x4.30 -- worse than the low-`h/lambda` corner the page already
hedges.  Tabulating cannot beat the form it tabulates.

The physical reading is that the additive decomposition is what breaks.
H1 was measured at a return lying on the ground, where the image
cancels most of the coupling between the two conductors.  Lift the
return a meter or two and it becomes a radiator in its own right,
coupled to the antenna, and `Za + Zr` stops being the whole story --
which is the same mutual coupling the finding 7 residual tail pointed
at.

So the return stays assumed to lie on the ground, and that assumption
keeps its caveat rather than becoming a control.

### The coupling term, tried and not kept

If the additive form is what breaks, the obvious repair is a mutual
term, `Zin = Za + Zr + 2 Zm`.  For two conductors carrying comparable
current the mutual impedance scales as the geometric mean of the two
self impedances, so

    Zm = km * exp(-(h - rh) / (kd * lambda)) * sqrt(Za * Zr)

with the separation in wavelengths.  That has the limits the physics
demands -- full coupling as the conductors approach, none as they
separate -- and the five-parameter form is nested inside it at
`km = 0`, so the comparison is fair.

Fitted, it buys almost nothing:

| return height m | without | with |
|---|---|---|
| 0.01 | x1.20 | x1.20 |
| 0.15 | x1.20 | x1.20 |
| 0.50 | x1.24 | x1.23 |
| 1.00 | x1.34 | x1.34 |
| 2.00 | x1.60 | x1.46 |

Nine percent at the one place it exists to help, nothing anywhere else,
and the 90th percentile at a 2 m return barely moves, x2.20 to x2.18.
The fit is also unhealthy: `kd` runs to its upper bound of 20
wavelengths in some groups and `km` to its bound of 2 in others, while
sitting at zero in 14 percent.  A parameter that is either absent or
railed is not measuring anything.

Two parameters for that is a bad trade, so it is not kept.  The reading
is that a scalar mutual term is too weak a description: at a meter or
two of separation the return is not a lumped neighbour of the antenna
but a second radiator with its own current distribution, which wants a
genuinely coupled two-port rather than one number scaling
`sqrt(Za Zr)`.  That is a different model, not a term on this one.

## The two modes against each other

The classical keep-out is a proxy for the impedance spike, so the two
methods should agree about which lengths are bad.  Tested in
`docs/tools/model.test.mjs`, holding both at `MODEL_VF_A` so the
5 percent velocity-factor offset does not stand in for a real
disagreement.

They do agree, on both checks that can be made directly.  Every peak the
impedance model draws across 2 to 60 m falls inside a zone the classical
rule marks out.  And scoring a length grid, the lengths the rule rejects
score worse at the median than the ones it accepts, which is the proxy
being sound: two independent methods, one arithmetic on wavelength and
one a fitted impedance model, ranking the same lengths the same way.

The third check needed qualifying, and the reason is the better
argument for the impedance mode than anything in the original list of
gains.  Ask for four bands at the default 8 percent margin and the
classical zones cover 71.5 m of a 60 m axis -- more than all of it, once
overlaps are counted -- leaving a widest usable span of 2.4 m.  Every
length is in a zone, so "avoid resonance" has stopped being advice.  The
impedance mode still ranks them, because a continuous cost can say
*which* compromise is least bad where a binary keep-out can only say no.

That is now pinned by a test, so the saturation cannot quietly become a
solution space again.

## What the classical margin is worth, in ohms

`marginPct` defaults to 8 and has never been justified against anything.
Now that the two modes agree about where the bad lengths are, the model
can price it.  At the page's defaults, over the 80/40/20/15/10 set:

| margin | axis left usable | worst \|Z\| still reachable |
|---|---|---|
| 0 % | 54.2 % | 10487 |
| 2 % | 46.0 % | 6557 |
| **5 %, shipped** | **33.0 %** | **3792** |
| 8 % | 23.0 % | 2761 |
| 12 % | 9.5 % | 2090 |
| 15 % | 3.9 % | 1829 |

Read the other way, which is the way a user can actually state, since
nobody knows what percentage they want but everybody knows what their
tuner will reach:

| hold \|Z\| under | margin needed | axis left usable |
|---|---|---|
| 600 | unreachable | -- |
| 1000 | unreachable | -- |
| 1500 | 18 % | 0.6 % |
| 2500 | 10 % | 15.5 % |
| 4000 | 5 % | 33.0 % |

Two things follow.  The shipped 5 percent buys about 3800 ohms and
leaves a third of the axis usable.  That is a weaker guarantee than the
8 percent an earlier draft of this note assumed -- 8 buys 2800 ohms and
leaves 23 percent -- but it is the one the page actually makes, and
3800 ohms through a 9:1 is still inside what a wide-range tuner will
reach.

But the range it can express is narrow, and the shipped default sits
near the loose end of it.  Below about 1800 ohms the
margin stops being a usable control: 1500 ohms costs 18 percent and
leaves 0.6 percent of the axis, and 1000 ohms cannot be had at any
margin because the resonances are wide enough that no length escapes
every one of them.  So deriving `marginPct` from a user-set `|Z|max` is
possible and would be honest, but the honest answer over much of the
range is that no length qualifies.  That is the same saturation as
above, arriving from the other direction.

## The two NEC-2s do not agree over ground

Before building the browser check, its solver was put against the PyNEC
references in `nec/reference_cases.json`.  It failed: 26 of
30 cases outside the 2 percent tolerance, worst 65.7 percent.  The
fixture existed for exactly this, and the cause took some finding.

Ruled out in turn.  The extended thin-wire kernel, which `buildDeck`
emits and the Python side did not: no effect, and none expected, since
these segments are thousands of radii long.  The `GE` ground-plane flag,
`-1` against `1`: no effect, since no wire touches the ground.
Segmentation: both converge, and they converge to different numbers --
PyNEC near 1400 ohms, nec2c near 1860, on the same deck at 160 segments
per wavelength.

The isolating test settles it.  A plain center-fed dipole in free space,
no ground solver involved:

| | 14.2 MHz | 7.15 MHz |
|---|---|---|
| PyNEC | 79.09 + j45.15 | 78.48 + j44.87 |
| nec2c | 79.09 + j45.12 | 78.48 + j44.85 |

Five significant figures.  The two are the same code in free space and
disagree by up to a third once a real ground is present, so **the
difference is entirely in the Sommerfeld-Norton implementation**.

That is worth stating plainly: every coefficient in this model is fitted
to *nec2++'s* ground, not to NEC-2 in the abstract, and the x1.5 bound is
a bound against that implementation.  A second implementation of the
same published method differs by more than the low-`h/lambda` corner the
page already hedges.

### One of them is wrong, and it is not the one we fitted against

The two are independent translations of Burke and Poggio's original
NEC-2 FORTRAN -- nec2c is Kyriazis's C, nec2++ is Molteno's C++ -- so
neither is a reference for the other, and at first "which is right" had
no answer here.  It does now, from two directions: a limit with a known
answer, below, and the FORTRAN itself, further down.  But the
disagreement is not uniform, and where it lives says what is wrong.

Sweeping the return path's height at 7.15 MHz over good ground:

| return height | h/lambda | nec2++ | nec2c | gap |
|---|---|---|---|---|
| 0.01 m | 0.00024 | 1582 | 3135 | **98 %** |
| 0.05 m | 0.00119 | 1490 | 2090 | **40 %** |
| 0.15 m | 0.00358 | 1344 | 1515 | 13 % |
| 0.50 m | 0.01192 | 1048 | 1065 | 1.7 % |
| 1.00 m | 0.02385 | 827 | 822 | 0.6 % |
| 5.00 m | 0.11925 | 213 | 207 | 2.9 % |

They agree to within about 3 percent everywhere except within roughly
0.01 wavelengths of the interface, where they diverge without limit.

Two tests locate the fault rather than splitting the difference.

**Perfect ground.**  Replace the soil with a perfect conductor, which is
image theory and involves no Sommerfeld integral at all.  At the same
heights the two agree to 0.01 percent: 1500.8 against 1500.6 at 1 cm,
1441.7 against 1441.5 at 5 cm.  So the geometry, the segmentation and
the near-field handling are identical and sound in both, and the whole
disagreement lives in the Sommerfeld evaluation.

**The conductivity limit.**  As the soil's conductivity rises, a lossy
half-space becomes a perfect ground plane, so the Sommerfeld result must
converge to the perfect-ground answer.  That answer is known, and both
compute it identically.  At 5 cm:

| sigma S/m | nec2++ | nec2c |
|---|---|---|
| 0.03 | 1489.7 | 2090.0 |
| 1 | 1454.9 | 1888.0 |
| 30 | 1444.1 | 1869.1 |
| 1000 | **1442.1** | **1867.6** |
| exact | 1441.7 | 1441.5 |

nec2++ converges to the known answer within 0.03 percent.  nec2c
converges to a figure 29.6 percent above it.  That is not two defensible
readings of a hard integral; it is a limit with a known answer, and one
implementation does not reach it.

So for a wire this close to ground, nec2++ reaches an answer that is
known and nec2c does not.  The literature says the method should work
here: the Sommerfeld-Norton ground is documented as accurate for wires
as close to it as to a perfect ground.

The consequence for this model is good news, arrived at the long way
round.  Every coefficient is fitted against PyNEC, which is nec2++, the
implementation that passes the limit test.  The near-ground behavior
the model rests on is the behavior that reduces correctly to a case
with a known answer, so the earlier finding stands unqualified: return
height really does move the feedpoint that much, and the 4.6x is
physical rather than numerical.

### It is the method, not the port

This was first written up as a bug in nec2c, to report upstream.  That
was wrong, and the correction matters more than the original finding.

The nec2c maintainer has a `validation` branch carrying two real
hand-transcription slips in `somnec.c`, both on the Sommerfeld path: a
misplaced parenthesis in gshank's convergence gate, which computed
`|Re + |Im||` instead of the L1 magnitude `|Re| + |Im|`, and a collapsed
GO TO ladder in evlua that could skip both of the two tail integrations
closing the spectral contour.  Both are genuine and both are fixed.

The branch also builds `nec2dx`, the original NEC-2 FORTRAN, which is
the oracle rather than another opinion: it is what every port was
transcribed from.  Running all four on the 5 cm case:

| sigma S/m | nec2++ | nec2c stock | nec2c fixed | nec2dx FORTRAN |
|---|---|---|---|---|
| 0.03 | 1489.7 | 2090.0 | 2107.3 | 2107.4 |
| 1000 | **1442.1** | 1867.6 | 1868.3 | 1868.4 |
| exact | 1441.7 | 1441.5 | 1441.5 | 1441.5 |

The fix works, and what it buys is fidelity to NEC-2: it moves nec2c
onto the FORTRAN to five figures, where stock was 0.8 percent off it.
It does not move it onto the limit.  Fixed nec2c misses by the same 29.6
percent stock does.

The half-wave dipole deck in `nec2-js/investigations/` says the same
thing at 0.02 wavelengths, where the fed element itself is near the
soil: stock nec2c is +91.90 percent past the limit, fixed nec2c +91.92,
nec2dx +91.92, and aegnec2 -- which links the original SOMNEC -- +91.90.
The entire FORTRAN lineage agrees with itself and misses.  nec2++ is the
outlier at +0.77 percent, and it is the one that is right.

So the ranking in this section survives but its reason does not.  nec2c
is not defective here; it is faithful.  **NEC-2's own Sommerfeld
evaluation fails the conductivity limit near the interface, and nec2++
is the only implementation tried that passes.**  The coefficients are
still fitted against the one that passes.

What in nec2++ accounts for that is not established.  The two `somnec.c`
sites upstream fixed read correctly in necpp today, so it is not those,
and the history between the two codebases has not been traced here.  The
warrant for preferring nec2++ is the measured limit, not a story about
why.

### Every implementation, against height

One horizontal half-wave dipole, center fed, 11 segments, 145.9 MHz,
swept in height over ground.  Each cell is the feedpoint resistance
under `GN 2` at sigma 1e10 against the same geometry under `GN 1`, which
must agree, so the number is the error in the Sommerfeld evaluation.
`nec2c` is master, `nec2c-val` the `validation` branch, `nec2dx` and
`nec2dxs` are FORTRAN NEC-2, and aegnec2 links the original SOMNEC.
From `nec/sommerfeld_cross.py`, which takes the solvers as
arguments and carries the invocation recipe.

| height | NEC-4.2 | nec2++ | nec2c | nec2c-val | nec2dx | nec2dxs | aegnec2 |
|---|---|---|---|---|---|---|---|
| 0.5 wl | +0.00% | +0.00% | +0.00% | +0.00% | -0.00% | -0.00% | +0.00% |
| 0.2 wl | +0.00% | +0.00% | +0.00% | +0.00% | +0.00% | *crash* | +0.00% |
| 0.1 wl | +0.00% | +0.00% | +0.00% | +0.00% | +0.00% | *crash* | +0.00% |
| 0.05 wl | +0.00% | +0.00% | +0.00% | +0.00% | +0.00% | *crash* | +0.00% |
| 0.02 wl | **+0.05%** | +0.77% | +91.89% | +91.91% | +91.92% | *crash* | +91.92% |
| 0.01 wl | **+0.46%** | -0.69% | -95.35% | -95.08% | -95.09% | *crash* | -95.09% |
| 0.005 wl | **+2.90%** | +8.21% | +3037.98% | +3039.24% | +3039.26% | *crash* | +3038.92% |
| 0.002 wl | **+50.53%** | +125.70% | +46607.55% | +46612.07% | +46613.28% | *crash* | +46609.83% |

PyNEC is omitted because it wraps nec2++ and reproduces it to every
figure printed; it is one implementation, not two.

Five things fall out of it.

Everything agrees perfectly down to 0.05 wavelengths, so this is a
near-ground effect with a clean onset and not a general disagreement.

The split below that is two-way and total.  NEC-4.2 and nec2++ are one
answer; nec2c, the validation branch, nec2dx and aegnec2 are the other,
and the second group agrees with itself to three or four figures across
five orders of magnitude of error.  There is no spectrum here to split
the difference along.

**NEC-4.2 settles which side is right**, and it is the side this model
is fitted to.  It shares no code with nec2++, its ground treatment was
reworked for exactly this regime, and it reaches the limit better than
nec2++ does at every height below 0.05 wl.  It also disposes of the
strongest objection to the test -- that sigma 1e10 is so far outside
anything physical that it might be probing numerical conditioning rather
than the method.  If that were what the table showed, NEC-4.2 would be
in trouble too; it returns +0.05 percent at 0.02 wl.

**The validation branch does not move nec2c out of that group**, which
is the direct answer to whether its `somnec.c` fixes bear on this.  They
move it *within* the group, onto nec2dx: at 0.01 wl master reads -95.35
and the branch -95.08 against the FORTRAN's -95.09, and at 0.005 wl
3037.98 becomes 3039.24 against 3039.26.  The fixes are real and they
buy fidelity to NEC-2.  NEC-2 is what is wrong here.

`nec2dxs` segfaults, with a core dump, immediately after printing the
ground constants -- so it dies in the Sommerfeld setup rather than
returning a wrong number.  It is the only build that fails loudly.

nec2++ holds to roughly 0.005 wavelengths and then goes the way the
FORTRAN went, just later.  Our return path sits at 0.0012 wavelengths on
40 m, which is past that -- but the fed point is 30 ft up, at 0.22
wavelengths, and the feedpoint impedance is dominated by the elevated
wire.  The 5 cm limit test above passes at 0.0 percent, so this
installation is inside the envelope by measurement rather than by
argument.  It is not a general license, and a model with the *source*
near the soil would need its own check.

Two limits on that reassurance, both worth keeping in view:

- The limit test only exercises the high-conductivity corner.  At sigma
  1000 there is an exact answer to check against; at the sigma 0.005 of
  real soil there is none.  Passing is necessary, not sufficient.
- A locally built `nec2++` binary reproduces PyNEC to every figure
  printed, which is reassuring about reproducibility and nothing else --
  PyNEC wraps that same nec2++, so it is one implementation checked
  twice.  NEC-4.2 is the independent opinion, and it agrees with
  nec2++ rather than with the lineage nec2++ came from.

The consequence for the browser check is worse than it looked, because
it is now structural.  Shipping it against `nec2c-wasm` would show the
user a second number about 30 percent high in exactly the configuration
the page assumes, and no upstream fix will lift that -- there is nothing
left to repair.  Either the button waits for a nec2++ wasm build, or the
offline fit moves to nec2c so both ends share a solver and both are
wrong the same way.  Reporting it as a known implementation spread is
still available but reads as an excuse now that we know which one is
right.

One limit on how far to carry this.  The dipole deck puts the *fed*
element near the soil and no engine meets the limit below about 0.002
wavelengths.  Here the near-ground wire is the return and the source
sits 30 ft up, at 0.22 wavelengths, which is milder -- and nec2++'s
measured pass at 0.0012 wavelengths is the evidence that it is mild
enough, rather than an assumption that it is.

### What refitting against NEC-4.2 would move

`nec4_compare.py` solves the whole fitted grid with both -- 106,848
points, an hour and fifty-four minutes -- and reports `|Z|` from NEC-4.2
against `|Z|` from nec2++ as a factor.  x1.000 would mean a refit cannot
change anything.

| | median | 90th | worst |
|---|---|---|---|
| all | x0.998 | x1.557 | x57.95 |
| h/lambda 0-0.05 | x0.979 | x2.528 | x57.95 |
| h/lambda 0.05-0.1 | x1.000 | x1.625 | x27.43 |
| h/lambda 0.1-0.2 | x1.004 | x1.523 | x25.94 |
| h/lambda 0.2-0.5 | x0.995 | x1.464 | x5.36 |
| h/lambda 0.5+ | x0.997 | x1.300 | x4.97 |

By frequency the split is cleaner than by height: 1.9 MHz is x2.207 at
the 90th and 28.85 MHz is x1.256.  Low and slow is where they part.

The medians say the two solvers agree to a couple of tenths of a percent
in the typical case.  The 90th percentiles say the tail is the size of
the model's own x1.35 bound, which is the number that decides the
question: **the choice of solver matters about as much as the model's
stated error**, so a refit moves real numbers rather than polishing.

Two tidy explanations were tested at this scale and neither holds.  It
is not resonance placement -- the spread is *widest* more than 0.15
wavelengths from a half-wave multiple, where `|Zin|` is flattest, rather
than on the steep flanks where a small shift would inflate a ratio.  And
it is not height alone: the 90th falls from 0.05 through 0.2 and rises
again through 0.2-0.5, so no monotonic story fits.

### And what it actually moves: nothing that ships

`nec4_sweep.py` solves the same grid with NEC-4.2 and the 1-D fitter,
since retired, fitted the same form to it.  The two fits, measured the
same way:

| | nec2++ (shipped) | NEC-4.2 |
|---|---|---|
| h/lambda >= 0.05 | x1.25 median, x1.32 90th, x1.38 worst | x1.25 median, x1.33 90th, x1.39 worst |
| h/lambda < 0.05 | x1.50 median, x3.12 worst | x1.37 median, x1.71 worst |

**Where the page claims accuracy the two are indistinguishable.**  Same
median, 90th percentiles a hundredth apart.  So the refit is declined:
it would swap the coefficients for others that deliver the same answer,
against a solver most readers cannot run.

Two things are worth keeping from it anyway.

The first is that the limit test does not discriminate *here*.  In this
geometry both solvers converge on the perfect-ground answer -- nec2++ to
+0.0 percent, NEC-4.2 to +0.2 -- because the feedpoint is 0.22
wavelengths up and only the return is near the soil.  NEC-4.2's
advantage was measured on a dipole with the *fed* element near ground,
which is not the antenna this page models.  All the disagreement between
them sits at realistic soil conductivity, where there is no exact answer
to appeal to: at sigma 0.03 nec2++ reads 1489.7 and NEC-4.2 2081.5.

The second is the low-`h/lambda` row, which was not predicted.  Below
0.05 the same form fits the NEC-4.2 grid about twice as well, worst case
x1.71 against x3.12.  The model has not improved; the target has got
smoother.  That is indirect evidence that NEC-4.2's near-ground
behavior is the more physical one, since a fixed form tracks a simpler
function more easily, and it is exactly the regime where nec2++ is
nearing its own envelope.

So the ordering inverts.  NEC-4.2 is not worth adopting for the antenna
modeled today, and it becomes the right target the moment the model
reaches below `h/lambda` 0.05 -- which is what a counterpoise-height
control would require.

### Spike: counterpoise height as an axis

`return_height_sweep.py` asked this against PyNEC over 0.01 to 3 m and
the answer was no -- the form failed before the table did, x1.60 median
at a 2 m return.  `spike_return_height.py` asks it again against NEC-4.2,
with the axis expressed as a fraction of the wire height rather than as
an absolute height, and the answer is different.

Per-group error, each height given its own best coefficients:

| counterpoise height | median | worst |
|---|---|---|
| ground (1 cm) | x1.13 | x1.20 |
| 0.02h | x1.16 | x1.22 |
| 0.05h | x1.17 | x1.23 |
| 0.1h | x1.18 | x1.21 |
| 0.25h | x1.17 | x1.25 |
| 0.5h | x1.19 | x1.21 |
| 0.9h | x1.25 | x1.44 |

**The form carries the axis.**  Flat from the ground to half the wire
height, degrading only at 0.9h where there is barely any drop left, which
is a different antenna anyway.

The coefficients move enough to need tabulating -- `alpha_a` by x2.89 and
`kr` by x2.49 -- which is expected and is what the `h/lambda` table
already does for height.

One thing must be fixed before a real fit.  `alpha_r` reads 0.0010 at the
top of the axis, which is its own lower bound: the fit is railing.  That
is physically sensible, since a counterpoise well clear of the soil is a
low-loss line, so the bound is wrong rather than the model.  Lower it
before fitting, or the tabulated return loss will be a fence rather than
a measurement.

Two caveats on the spike's own reach.  It is two frequencies, three
heights, one return length and one soil, so it establishes feasibility
and not coefficients.  And a real fit needs this axis crossed with the
existing grid, which multiplies a 77-minute sweep by about seven.

### Counterpoise height, on the table's own axes

The spike said the form carries this axis on two frequencies and one
soil.  `nec4_return_height_sweep.py` asks the same on every axis the
coefficient table indexes -- 138,240 NEC-4.2 solves, 67 minutes, none
refused.

Per-group error, each step given its own coefficients, n=96 apiece:

| counterpoise height | median | 90th | h/lambda >= 0.05 median | 90th |
|---|---|---|---|---|
| ground (1 cm) | x1.20 | x1.34 | x1.21 | x1.35 |
| 0.02h | x1.19 | x1.27 | x1.20 | x1.27 |
| 0.05h | x1.20 | x1.26 | x1.21 | x1.26 |
| 0.1h | x1.20 | x1.27 | x1.21 | x1.27 |
| 0.25h | x1.22 | x1.28 | x1.24 | x1.28 |
| 0.5h | x1.24 | x1.32 | x1.24 | x1.33 |

Flat from the ground to half the wire height, and level with the shipped
model's own x1.25 median and x1.32 at the 90th.  Raising the counterpoise
costs the fit nothing.

The coefficients are the better news.  Only two of the six move, and both
monotonically:

| step | alpha_a | vf_a | ka | alpha_r | vf_r | kr |
|---|---|---|---|---|---|---|
| ground | 0.1168 | 1.0000 | 0.7780 | 0.5383 | 0.8244 | 0.7698 |
| 0.02h | 0.1100 | 1.0000 | 0.7729 | 0.3701 | 0.9139 | 0.8084 |
| 0.05h | 0.1094 | 1.0000 | 0.7921 | 0.2773 | 0.9510 | 0.7760 |
| 0.1h | 0.1083 | 1.0000 | 0.7778 | 0.2375 | 0.9621 | 0.7756 |
| 0.25h | 0.1071 | 1.0000 | 0.7577 | 0.2026 | 0.9849 | 0.7968 |
| 0.5h | 0.1048 | 1.0000 | 0.7275 | 0.1888 | 0.9950 | 0.8096 |

`alpha_r` falls by x2.9 as the counterpoise rises, which is the return
line shedding ground loss, and `vf_r` climbs from 0.82 towards 0.995,
which is the same line approaching free space as it leaves the soil.
Both are physically legible rather than fitted noise.  `alpha_a`, `ka`
and `kr` are flat to within a few percent, and `vf_a` is railed at unity
as it is everywhere else.

Two things follow.  `alpha_r` reads 0.1888 at the top rather than sitting
on its bound, so lowering that floor from 1e-3 to 1e-6 was necessary and
is now vindicated.  And because only two coefficients carry the axis,
this may not need a third table dimension: a one-dimensional correction
on `alpha_r` and `vf_r` against z/h could be enough, which is a much
smaller change to the page than a 3-D table would be.

### The two geometries disagree about where the counterpoise runs

Not by design, and it is recorded rather than fixed.  The flat top runs
its counterpoise along the antenna, `RETURN_DIRECTION = 1`, which is 0
degrees of bearing.  The sloper deck was written with it heading away,
180 degrees.  So the two tables were fitted under different conventions.

`geometry_check.py` measures what bearing is worth, at the page's
default site with the counterpoise on the ground:

| band | 0 deg | 45 | 90 | 135 | 180 | spread |
|---|---|---|---|---|---|---|
| 80 m | 7.4 | 7.2 | 6.7 | 6.3 | 6.2 | 1.20x |
| 40 m | 10.9 | 10.7 | 10.5 | 10.3 | 10.3 | 1.06x |
| 20 m | 5.6 | 5.7 | 5.9 | 6.0 | 6.1 | 1.07x |
| 15 m | 5.8 | 5.7 | 5.6 | 5.6 | 5.6 | 1.03x |
| 10 m | 5.3 | 5.2 | 5.2 | 5.1 | 5.1 | 1.04x |

Square, back-angled and straight away cluster -- 6.7, 6.3, 6.2 on 80 m
-- and **running underneath is the outlier** at 7.4.  So the flat top is
fitted at the unusual bearing and the sloper at the typical one.

Left as it is for now, on three grounds.  The spread is only material on
80 m, which is not in the default band set; it is under 1.1x everywhere
else; and making them agree means re-sweeping, which moves shipped
numbers for an effect smaller than the model's own bound.  The page says
so in the geometry panel rather than leaving it implicit.

Worth revisiting if the counterpoise axis is used in anger: bearing was
measured with the counterpoise on the ground, where its image largely
cancels its coupling to the wire above.  Raised clear of the soil that
cancellation weakens, so the bearing may matter more there than this
table shows, and nothing has measured that.

### Where NEC-2 is bad, and where it is not

Two results that look contradictory until the regimes are separated, and
the difference decides whether an exported deck can be trusted.

**Fed element near the ground, at the conductivity limit.**  Every NEC-2
descendant fails and fails hugely -- +91.9 percent at 0.02 wavelengths,
+46,608 at 0.002 -- while NEC-4.2 and nec2++ hold.  That is the table
above, and it is why NEC-2 was distrusted near ground.

**Source high, counterpoise near the ground, real soil.**  This is the
antenna the page models: the feedpoint is 0.22 wavelengths up and only
the return is low.  Running the page's own exported deck through both,
at 7.15 MHz:

| counterpoise z | z/lambda | NEC-4.2 | nec2c | ratio |
|---|---|---|---|---|
| 1.0 m | 0.0239 | 818 | 818 | 1.00 |
| 0.25 m | 0.0060 | 1295 | 1300 | 1.00 |
| 0.05 m | 0.0012 | 1969 | 1977 | 1.00 |
| 0.02 m | 0.0005 | 2581 | 2574 | 1.00 |
| 0.01 m | 0.0002 | 2585 | 2554 | 1.01 |

Within one percent all the way down to a centimeter, on average and on
good soil alike.  **NEC-2's Sommerfeld failure needs the fed element
near the interface**, and a counterpoise there is a far milder case.

Two things follow, and both correct earlier conclusions here.

An exported NEC-2 deck agrees with this page, so the panel does not warn
about the solver.  What it warns about is this model: up to 2x near a
half wave, and a deck segmented for the shortest wavelength where the
fit segmented per frequency.

And the reason for fitting against NEC-4.2 is not the one recorded
above.  In this geometry NEC-2 is fine and **nec2++ is the outlier** --
1490 ohms against 2081 and 2090 for NEC-4.2 and nec2c on good soil at a
5 cm counterpoise.  nec2++ passes the limit test and disagrees here by
30 percent; NEC-4.2 is right in both regimes, which is the case for it.

It also reopens the in-browser check, which was declared blocked on the
grounds that nec2c-wasm would be about 30 percent off in exactly this
configuration.  It would not be, and the check now ships; see "The
check runs both, and draws where they part".

The exported deck needs no variant per solver: it is plain NEC-2 cards
and NEC-4 reads them, so one file serves all three.  What differs is
which to trust.  The same deck, average soil, 7.15 MHz:

| counterpoise z | NEC-4.2 | nec2c | nec2++ |
|---|---|---|---|
| 1.0 m | 818 | 818 | 810 |
| 0.25 m | 1295 | 1300 | 1195 |
| 0.05 m | 1969 | 1977 | 1406 |
| 0.01 m | 2585 | 2554 | 1297 |

nec2c holds to 1 percent of NEC-4.2 throughout.  nec2++ falls away as the
counterpoise descends -- 29 percent low at the shipped 5 cm default, and
half at a centimeter.  So **nec2++ is the one to avoid for this antenna**,
which is the reverse of what the limit test alone would suggest, and the
reverse of what this note said before the geometries were separated.

### The sloper closes the question

A sloper puts the fed element itself near the ground, and no
implementation carve survives it.  A 67.97 m sloper -- apex 16.5 m,
balun 0.61 m, counterpoise 7.62 m at 3 cm, average soil -- solved at 25
frequencies across 80 through 10 m, SWR through a 9:1, per band:

| band | feed h/lambda | NEC-4.2 | nec2++ | nec2c |
|---|---|---|---|---|
| 80 m | 0.007 | 3.0-4.5 | agrees | agrees |
| 40 m | 0.014 | 3.1-4.6 | ~10% high | garbage |
| 20 m | 0.029 | 3.3-3.5 | **1.4-1.5** | **1.1-1.2** |
| 15 m | 0.043 | 1.6-1.9 | close | 3.9-4.9 |
| 10 m | 0.058 | 1.8-4.1 | erratic | erratic |

The failures are not monotone in feed height -- 80 m agrees, 20 m is
broken, 15 m splits the two -- so no h/lambda threshold rescues a band.
And 20 m is the failure mode that matters: both NEC-2s report a
plausible near-match where NEC-4.2 reads 3.5, silently.  An exploding
answer indicts itself; this one does not.  So the in-page check warns
below 0.05 wavelengths of feedpoint height and runs only on request,
and a sloper's real confirmation is NEC-4.

The same solve answers the other question, because the model was run
beside the solvers: at this length the model reads a geometric mean of
2.8 and a worst of 4.4 against NEC-4.2's 2.9 and 4.6, and on 80 and
40 m it matches NEC-4.2 to a tenth of an SWR unit at every frequency.
**Fitted to NEC-4.2, the model carries that solver's ground into the
regime no browser-runnable NEC-2 can reach, and tracks it better there
than either NEC-2 does.**

### The length offset that wasn't

The in-page check's overlay can look shifted in length against the
model curve, as if the resonances sat at different wire lengths.
Measured, they do not.  Peak positions of |Z| against length on a
default flat top, in half-waves at that frequency:

| freq | NEC peaks | model peaks |
|---|---|---|
| 14 MHz | 1.04 2.03 3.01 3.99 5.03 | 0.98 1.96 3.01 3.99 4.97 |
| 21 MHz | 1.01 2.03 ... 8.01 | same, within one sample |
| 28 MHz | 0.98 ... 11.05 | same, within one sample |

Every difference is inside the 2 percent measurement grid, out to
eleven half-waves: `vf_a = 1.0` puts the walls where NEC puts them.
The apparent shift is composite skew.  A bump in the multi-band
geometric mean is the interference of several bands' structure, and
when per-band amplitudes differ -- the model's median x1.4 optimism on
a many-band whole-band set -- the composite bump moves sideways with
no band's comb moving at all.

What is real underneath, from a fine scan at 7 MHz between the second
and third peaks (NEC-4.2 and nec2c agreeing within 1 percent there):
the model's inter-peak valley floor reads 1.2-1.3x low.  Not a missing
resonance -- a broad elevation the two-line series model has no term
for, presumably the return system that a series Za + Zr cannot couple.
That is the same model-form gap the falling-alpha experiment
approached, and no refit of the present form can produce it.

### Neither browser NEC-2 survives the region past a peak

The fine scan also broke the claim that nec2c tracks NEC-4.2 to 1
percent at low counterpoise.  It does at 1.5 half-waves, where that
table was measured.  Just past the second half-wave peak it comes
apart, at every counterpoise height tried -- |Z| against NEC-4.2 at
7 MHz:

| halves | z = 5 cm, nec2c | z = 25 cm, nec2c | z = 5 cm, nec2++ | z = 25 cm, nec2++ |
|---|---|---|---|---|
| 2.00 | x1.34 | x1.17 | x0.90 | x0.98 |
| 2.05 | x4.79 | x2.31 | x0.94 | x0.99 |
| 2.10 | x5.41 | x2.97 | x0.95 | x1.00 |
| 2.25 | x8.51 | x14.41 | x0.68 | x0.89 |
| 2.45 | x0.93 | x2.38 | x0.72 | x0.92 |

nec2c invents a second peak after the real one, up to x14; nec2++
tracks NEC-4.2 through the same region within about 10 percent -- the
reverse of the low-counterpoise ranking at 1.5 half-waves, where
nec2++ reads half and nec2c is exact.  **Each browser-runnable NEC-2
fails somewhere the other does not, and everywhere sampled, when the
two agree they also sit near NEC-4.2.**  The in-page check runs nec2c
alone, so its overlay near and past half-wave peaks at a low
counterpoise can read several times high -- some of what the overlay
paints as model error there is the checker.  The model's own error
figures are unaffected: they are measured against NEC-4.2 directly.

### The check runs both, and draws where they part

Seen live before it was measured: at the page's defaults on 40 m --
30 ft up, 25 ft of counterpoise on the ground, average soil, 49:1 --
the single-solver overlay left the 15:1 chart near 185 ft and called
207 ft a 3.5:1 length where the model said 1.8:1.  The page's own probe
decks, at the check's own segmentation, through every solver to hand
at 7.15 MHz, |Z| and SWR through the 49:1; the first column is the
converged answer, NEC-4.2 Richardson-extrapolated from 2x and 4x that
segmentation, and the rest are what each solver reads from the deck as
the check writes it:

| length | converged | NEC-4.2 | NEC-5 | nec2c | nec2++ |
|---|---|---|---|---|---|
| 69 ft | 3281, 2.78 | 6085, 2.70 | 6384, 2.61 | 6095, 2.70 | 5438, 2.42 |
| 138 ft | 2810, 2.21 | 5372, 2.33 | 6055, 2.47 | 7367, 3.53 | 4754, 2.06 |
| 172 ft | 1649, 4.17 | 1919, 3.10 | 3544, 1.45 | 1210, 3.64 | 1340, 3.82 |
| 180 ft | 1996, 4.14 | 2135, 3.30 | 3743, 1.56 | 803, 3.50 | 1550, 3.95 |
| 185.7 ft | 2343, 4.02 | 2358, 3.36 | 3932, 1.62 | 723, 3.56 | 1754, 3.91 |
| 193 ft | 3147, 3.58 | 2760, 3.44 | 4249, 1.78 | 677, 3.70 | 2140, 3.78 |
| 207 ft | 2578, 1.90 | 4855, 2.09 | 5795, 2.37 | 658, 3.77 | 4293, 1.84 |

Three things in that table.  nec2c is exact at the half wave and falls
away past two half-waves, to a seventh of NEC-4.2 by 207 ft, where
nec2++ sits within 10 percent of the converged SWR; the verdict the
overlay had given was the checker's error, not the model's, which reads
1.8:1 against a converged 1.9.  The suspect-band gate keys on the
feedpoint's height, 0.22 wavelengths here, and could not fire.  And
every solver at the check's segmentation carries the density bias the
density study measured -- even NEC-4.2 reads |Z| x1.85 high at the
half wave, which the 49:1 hides in SWR -- so the overlay is a
measurement at one density, not the limit; NEC-5 at that density is
the furthest off between 172 and 193 ft, though it agrees with NEC-4.2
within x1.03 once both are converged.  Densifying the check's decks
would cost the 7-14x per solve the campaign paid and is not offered.

So the check now runs both.  The worker hands each probe deck to nec2c
as text and, read back into nec2++'s API by `deckModel` -- the same
wires, ground, jacket loads, source and frequency -- to nec2++, which
answers with numbers.  Where the two agree within `NEC_AGREE_FACTOR`
(1.15 in SWR) the overlay is the line it was; where they part it is a
band between them, the verdict and the table read as a range, and the
status line says the check is unsure rather than that the model is
wrong.  nec2++ solves a deck in the time nec2c does, about 40 ms, so a
run costs twice what it did.  The standing-wave profiles stay nec2c's,
which is the one that prints them.  Should nec2++ fail to load, the
check runs on nec2c alone and draws no band, which is its way of saying
so.  necpp-wasm 0.2.1 trapped on memory above about 140 segments --
Eigen putting its matrices on a WebAssembly stack -- which would have
sent every long wire on a high band to nec2c alone; 0.2.2 fixed that
and solves the page's largest decks, 233 segments, in about 120 ms.

### Which solver to believe, where

The band says the check is unsure; this measures which side of it to
stand on.  `nec/solver_ranking_decks.mjs` generates 4,104 of the page's
own probe decks -- flat top at 3, 9.1 and 20 m with the counterpoise at
1, 5, 30 and 100 cm, sloper apexes at 10 and 20 m with it at 5 and 30
cm, three soils, 40, 20 and 10 m, thirty lengths from 3 to 66 m -- and
solves each with nec2c and nec2++ exactly as the check does.
`nec/solver_ranking.py` adds NEC-4.2 at 1x, 2x and 4x the deck's
segmentation and NEC-5 at 1x, takes the (2x, 4x) Richardson pair as the
converged answer, and scores every solver's SWR at the radio against it
through the page's 9:1 and 49:1.  The error factor is exp|ln(swr /
swr_converged)|, median and 90th percentile:

| regime | n | nec2c | nec2++ | NEC-4.2 at 1x | NEC-5 at 1x |
|---|---|---|---|---|---|
| everything | 8208 | x1.24 / x3.16 | x1.23 / x1.90 | x1.16 / x1.79 | x1.32 / x2.72 |
| flat top | 6480 | x1.22 / x2.71 | x1.22 / x1.85 | x1.16 / x1.77 | x1.32 / x2.69 |
| sloper | 1728 | x1.38 / x12.6 | x1.27 / x2.03 | x1.17 / x1.85 | x1.29 / x2.84 |
| under 1 half-wave | 1152 | x1.10 / x1.67 | x1.20 / x1.85 | x1.10 / x1.67 | x1.16 / x2.18 |
| 1 to 2 half-waves | 1440 | x1.17 / x1.92 | x1.23 / x2.03 | x1.18 / x1.92 | x1.33 / x3.11 |
| 2 to 3 half-waves | 1608 | x1.36 / x10.5 | x1.23 / x2.02 | x1.18 / x1.96 | x1.31 / x2.90 |
| past 3 half-waves | 4008 | x1.31 / x4.06 | x1.24 / x1.83 | x1.17 / x1.73 | x1.38 / x2.64 |
| flat, z 5 cm, under 1 half-wave | 270 | x1.09 / x1.50 | x1.29 / x1.67 | x1.10 / x1.51 | x1.15 / x2.03 |
| flat, z 5 cm, 2 to 3 half-waves | 306 | x1.34 / x11.7 | x1.24 / x1.83 | x1.15 / x1.92 | x1.27 / x2.95 |
| flat, z 30 cm, past 3 half-waves | 756 | x1.28 / x2.99 | x1.15 / x1.60 | x1.18 / x1.63 | x1.39 / x2.78 |
| sloper, z 5 cm, past 3 half-waves | 492 | x1.57 / x358056 | x1.39 / x2.10 | x1.19 / x1.77 | x1.39 / x2.42 |

Four things.  NEC-4.2 at the check's own segmentation is the floor:
x1.16 median is the density bias measured under "The density study",
and no browser solver can do better than that from the same deck.
nec2++ sits just above the floor everywhere and never falls off it;
its 90th is x1.90 against nec2c's x3.16, and nec2c's tail past two
half-waves is not a tail but a cliff, x10 at the 90th and six figures
at the worst where its reflection pins at the cap.  Below two
half-waves the ranking reverses: over a counterpoise within 5 cm of
the soil nec2c is the floor itself, x1.09 to x1.18, where nec2++ reads
x1.29 to x1.35 -- the low-counterpoise misread measured earlier, now
placed.  And NEC-5 at the fitting density is the worst solver on this
table, x1.32 / x2.72, though converged it agrees with NEC-4.2 within
x1.03: whatever NEC-5 does differently, it converges from further away.

Agreement is a real signal.  Where the two browser solvers agree
within 1.15 in SWR -- 51 percent of points -- each reads x1.17 /
x1.90, which is the density floor; where they part, nec2c reads x1.40
/ x12.8 and nec2++ x1.29 / x1.91.  So the line is as good as the deck
allows and the band is where one solver, usually nec2c, has failed.

The rule the page follows is two constants: nec2c on a wire under two
half-waves over a counterpoise within 5 cm of the soil, nec2++
everywhere else, chosen frequency by frequency since the same wire is
short on 40 m and long on 10 m.  It scores x1.21 / x1.86 / x2.78 at
the median, 90th and 99th against x1.24 / x3.16 / x688641 for nec2c
alone and x1.23 / x1.90 / x2.82 for nec2++ alone; an oracle picking
the better solver at every point would reach x1.14 / x1.70 / x2.52,
so the rule takes most of what is there to take.  Averaging the two
geometrically is worse than either where they part (x3.88 at the 90th),
because nec2c's failures are not noise to average out.  The measured
line now follows the rule, the verdict quotes it, and the band still
shows the other reading where they part.  And the check's status
line says what its segmentation costs: about x1.2 from a converged
answer for any solver, so the overlay is read as a measurement at one
density.  A converged check -- 2x and 4x, extrapolated -- would cost
7-14x the solve time and is not offered.

## NEC-5 arrives: the ground stands, the density does not

NEC-5 (`nec5cl`) passed the conductivity limit on arrival, matching
NEC-4.2 nearly digit for digit -- +0.04 percent at 0.02 wavelengths,
+0.34 at 0.01 -- so its Sommerfeld is sound where correctness is
decidable.  On the reference cases it then disagreed with NEC-4.2 by
x1.3-1.6, worst x1.98, which looked like the better ground model
talking.  It was not.  A convergence ladder (1x to 8x the fitting
density) showed both solvers approaching the same answers from
opposite sides, and a 144-geometry slice across the table's axes
settled it:

| | median | 90th | worst |
|---|---|---|---|
| NEC-4.2, its 1x against its 8x | x1.17 | x1.49 | x1.88 |
| NEC-5, its 1x against its 8x | x1.52 | x2.38 | x4.54 |
| NEC-4.2 vs NEC-5, both 8x | x1.03 | x1.07 | x1.12 |

**Converged, the two ground treatments agree** -- confirmed
independently on the Sommerfeld path in a separate comparison.  What
does not stand is the fitting density: at the 20 segments per
wavelength every shipped sweep used, NEC-4.2 sits x1.17 median and
x1.49 at the 90th percentile off its own converged answers --
statistically indistinguishable from the model's entire quoted error
budget (x1.14, x1.43).  Some unknown share of what this note books as
model error is measurement error in the fit data.  The worst density
errors cluster at 1.45 wavelengths, between the resonance peaks, so
the inter-peak valley-floor finding above is itself partly suspect:
the reference it was measured against is least converged exactly
there.

Consequences.  A re-sweep is justified -- for density, not for
solver: either solver serves once converged, and NEC-4.2's tooling
exists.  Naively converged (8x) costs roughly 100x per solve, so a
density-requirement study -- where 2x or 4x suffices per regime --
prices the campaign before anyone approves it.  On 80 m NEC-5 is
converged at 1x where NEC-4.2 needs 8x, and the reverse on 40 m, so
mixed strategies exist.  Practical note: `nec5cl` clobbers a
fixed-name scratch file under parallelism and must run in per-job
directories, as `nec4_table_sweep.py` already does for NEC-4.2.

## Insulation is a scalar

A jacket slows the wire.  Measured with NEC-4.2's IS card on the real
end-fed geometry -- all three conductors sheathed, epsr 3, at twice the
fitting density, peak positions extracted by parabola -- the velocity
factor against bare wire:

| regime | 0.3 mm wall | 0.6 mm wall |
|---|---|---|
| 1.9 MHz, 9.1 m up | 0.990 | 0.981 |
| 7.15 MHz, 9.1 m | 0.988 | 0.979 |
| 28.85 MHz, 9.1 m | 0.986 | 0.974 |
| 7.15 MHz, 2 m | 0.988 | 0.978 |
| 7.15 MHz, 20 m | 0.989 | 0.980 |

Across a 15x frequency span and h/lambda from 0.013 to 0.48 the factor
moves a few tenths of a percent while the effect is one to two and a
half: **one number per jacket covers the page's domain**, about 0.98
for a typical PVC jacket on #14, with no new table axis.  The page can
carry it as a wire-type control scaling the fitted lines' velocity
factors.

Provenance is NEC-4.2 alone: this NEC-5 console build parses the IS
card but its storage is stubbed out in the source (RSETIS counts and
discards), so insulated wires are not in that distribution.

The page carries this as a Wire control scaling both fitted lines'
velocity factors by 0.98.  The in-page check keeps working for
insulated wire because NEC-2 -- which has no insulation -- can carry
the jacket as an equivalent uninsulated wire, by K6OIK's method
(S. Stearns, "Modeling Insulated Wire", ARRL): radius
a' = a (b/a)^(1 - 1/epsr) plus distributed series inductance
(mu0/2pi)(1 - 1/epsr) ln(b/a) per meter.  Measured against the IS
card's answer on this page's wire, that lands within 0.02 percent of
the true insulated resonance -- better than the Cebik/4nec2 curve fit
(0.1 percent when calibrated) and far better than the inductance alone
(a fifth of the shift missing) -- identically in nec2c and nec2++.
His conductivity correction is moot here: the probe decks leave the
wire perfect.

### The density study: extrapolate, do not densify

The density error does not converge away.  On nec_model's own
junction-matched decks -- the geometry the tables were actually fitted
from -- a 1x-to-16x ladder over 144 regimes shows the same first-order
creep the probe decks showed: |Z| approaches its limit like 1/N, still
moving a few percent per doubling at 16x, worst at the half-wave peaks
and the inter-peak valley.  At the fitted density the error against the
limit is x1.20 median, x1.60 at the 90th, x2.21 worst, and no uniform
multiplier reaches the limit at tolerable cost.

What does reach it is Richardson extrapolation.  The 1/N behavior is
clean: extrapolations from (2x, 4x, 8x) and from (4x, 8x, 16x) agree
within 0.5-3 percent on every worst case tried.  The pairs price out
as:

| strategy | median | 90th | worst | cost per point |
|---|---|---|---|---|
| raw 1x (shipped) | x1.20 | x1.60 | x2.21 | 1.0 |
| R(1x, 2x) | x1.14 | x1.45 | x2.97 | 2.2 |
| R(2x, 4x) | x1.02 | x1.07 | x1.33 | 3.2 |

R(1x, 2x) is poisoned -- the fitted density is pre-asymptotic, and
extrapolating from it can amplify rather than cancel.  R(2x, 4x) cuts
the measurement error by an order of magnitude.

The cost column above, measured on this study's probe solves, did not
survive the real campaign: on the full fitting decks a 2x solve costs
7-14x a 1x solve and a 4x solve runs about 3.3 s flat across the
frequency range, so the pair prices out near 20x the original sweep
per point, not 3.2x.  The converged re-sweep of both geometries took
83.5 wall hours at 12 workers, not 14 -- and most of that was waste,
found afterwards: nec4d42 is an OpenMP build that starts a thread per
core for every solve, so twelve workers were a hundred and ninety
runnable threads on sixteen, thrashing at a load average over a
hundred.  Pinned to one thread per solve (`OMP_NUM_THREADS=1`, now set
by every tool that calls a solver), the same solve is no slower and a
plane that had not finished a group in six and a half hours completed
in ten minutes.  The campaign's honest price at one thread is a few
hours, not days.

So the re-sweep the density finding calls for is priced and shaped:
solve every point at 2x and 4x the current density, extrapolate real
and imaginary parts separately, and fit to the extrapolated
impedances.

### The converged re-sweep: the old figures were flattered, not inflated

The campaign ran in August 2026: 922,706 NEC-4.2 solves -- both
geometries at 2x and 4x, plus an 8x third rung for the 669 points
whose (2x, 4x) extrapolation crossed into negative resistance and a
16x fourth rung for the 41 of those (all sitting exactly on the first
half-wave peak) that the (4x, 8x) pair still could not tame.  Zero
solves failed.  The rung gap came out at 6.2 percent median flat top,
7.1 sloper, and spot re-solves of randomly drawn rows reproduce the
stored impedances digit for digit.  `nec/extrapolate_sweep.py` refuses
bit-identical rungs after a first attempt at this campaign solved both
rungs at the fitting density: a Python 3.14 machine starts pool workers
under forkserver, where a parent-side segmentation override never
arrives, so the density now rides inside each job.

The question the campaign was asked -- how much of the model's error
budget was measurement -- has an answer nobody predicted: none of it.
The old figures were flattered, not inflated.  Refit to the converged
impedances and measured against them:

| per group |Z| factor | median | 90th | worst |
|---|---|---|---|---|
| flat top, old fit vs density-1 data | x1.25 | x1.33 | x1.59 |
| flat top, refit vs converged data | x1.29 | x1.43 | x1.83 |
| sloper, old fit vs density-1 data | x1.16 | x1.27 | x1.39 |
| sloper, refit vs converged data | x1.24 | x1.35 | x1.45 |

Fitting to biased data and scoring against the same biased data
understates the honest error: the fit absorbed the density bias the
way it absorbed the deck-grading fix, and the in-sample statistics
never saw it.  Per length the flat top read x1.18 median and
x1.55 at the ninetieth against these data (was x1.14 and x1.43 against
the old), and the headline miscall rate at 9:1 into a 3:1 tuner moved
from 21.9 to 26.0 percent; the falling loss under "The peaks are too
sharp" has since taken those to x1.16, x1.49 and 23.6.

Which closes the density question the way the ground question closed:
the shipped tables now stand on converged measurements, the honest
error is known, and what remains is model form -- the same conclusion
the decision metric reached from the other direction.

### Coefficients on their bounds are measurements

The converged refit left more coefficients on their refinement bounds
than the old one: 74 flat-top cells have `vf_r` at its 1.0 ceiling (47
fitted, the rest copied into unsupported nodes), 34 have `alpha_r_lam`
on its 0.05 floor, and `alpha_a_lam` sits at its 0.4 ceiling in 19
flat-top and 33 sloper cells.  A parameter on a bound is a warning that
the fit is compensating for the form, so each was mapped and probed by
moving it off the bound and re-measuring the groups nearest it.

`vf_r` rails in one corner only: `h/lambda >= 0.5` with `z/lambda >=
0.06`, the counterpoise well above ground.  There the bound is the
answer.  Moving it to 0.9 takes those groups from x1.25 median to
x2.11; moving it past the bound to 1.05 takes them to x1.64.  An
elevated return conductor is a wire in air, its phase velocity is c,
and the fit finds exactly that.  `alpha_a_lam` rails at the lowest
heights, `h/lambda <= 0.012`, where the wire is loaded by soil it
nearly touches; 0.4 was within a percent of optimal for the flat top
and a ceiling of 0.6 was worth x1.37 to x1.35 on the sloper's lowest
cells, so the ceiling is now 0.6.  Some cells rail there too -- the
lowest wires want still more loss -- but the probe showed 0.8 buys
them nothing the aggregate does not pay back.  `alpha_r_lam` rails at low heights over good soil and
does not matter: lifting it to 0.15 leaves the nearest groups unchanged
to three decimals.

None of the three hides a model defect.  The groups nearest railed
cells fit better than the rest, x1.25 / x1.28 against x1.31 / x1.45,
which puts the model-form error in the unrailed interior -- at the
resonance structure the peaks section describes -- and not at the
edges the bounds guard.

### Out of sample: geometries the sweeps never carried

Every figure above is in sample in every axis but frequency.
`nec/holdout_oob.py` solves 9,504 fresh decks between and beyond the
sweeps' grid -- flat tops at 4, 6, 8.5, 12 and 17 m with the
counterpoise at 3, 15 and 60 cm; slopers with apexes at 8 and 14 m, the
counterpoise at 10 and 25 cm and the balun at 0.61 and 1.0 m; returns
of 5.5 and 15 m; 80, 30 and 15 m, none of them sweep frequencies; three
soils; 24 lengths from 3 to 66 m -- at 2x and 4x the fitting density,
Richardson-extrapolated, and scores the shipped tables against them
exactly as the in-sample figures were scored.  All 9,504 converged.

| | in sample | out of sample |
|---|---|---|
| flat top, per length median / 90th / 99th | x1.16 / x1.49 / x2.06 | x1.20 / x1.58 / x2.29 |
| sloper, per length | x1.15 / x1.43 / x1.97 | x1.14 / x1.45 / x2.45 |
| flat top, phase median / 90th | 10.9 / 31.4 deg | 10.8 / 31.6 deg |
| flat top, miscall at 9:1 into 3:1 | 23.6% | 24.4% |
| sloper, miscall at 9:1 into 3:1 | 18.7% | 23.3% |

The tables generalize.  Per length they read a few percent worse than
in sample; the flat top's miscall rate moves one point and the
sloper's four and a half, on a holdout that leans on apexes and balun
heights its sweep never had.  The worst axis is 80 m, x1.74 at the
90th, which the sweeps bracket only from 1.9 MHz, and good soil, x1.63,
against x1.47 on poor.  No axis is a cliff: heights read x1.13 to
x1.22 median, counterpoise heights x1.13 to x1.22, the two returns
x1.16 and x1.19.

That also answers a question the fixture check raised.  The refinement
has flat directions wherever a node is thinly supported -- with one
group behind it, kr and alpha_r trade off freely -- so the tables'
coefficients are not unique across machines even where their cost and
predictions agree to many figures; `nec/pipeline_check.py` holds its
fixture to the cost and the error for that reason.  Where
non-uniqueness could cost something is between nodes and outside the
sweeps, and this holdout puts that cost at the few percent above.

### An 80 m plane, and what coverage does not buy

The holdout's weakest axis was 80 m, x1.74 at the 90th, which the
sweeps bracketed only from 1.9 MHz.  `nec4_table_sweep.py --only-mhz
3.75` swept a 3.75 MHz plane for both geometries at 2x and 4x --
48,960 and 28,035 points, 154,125 solves with the 135 third-rung
repairs, about two hours at one OpenMP thread per solve -- and both
tables were refit from the old sweeps and the plane together, 1,455
groups for the flat top and 891 for the sloper.

| | before the plane | with it |
|---|---|---|
| holdout, 80 m, per length median / 90th / 99th | x1.19 / x1.74 / x2.93 | x1.19 / x1.71 / x2.70 |
| holdout, everything | x1.17 / x1.54 / x2.33 | x1.17 / x1.53 / x2.27 |
| in sample, flat top per length | x1.16 / x1.49 / x2.06 | x1.17 / x1.51 / x2.11 |
| in sample, sloper per length | x1.15 / x1.43 / x1.97 | x1.16 / x1.45 / x2.05 |
| miscall at 9:1 into 3:1, flat / sloper | 23.6% / 18.7% | 23.4% / 18.6% |

The plane trims the 80 m tail and moves nothing else; the in-sample
figures rise slightly because they are now measured over the harder
plane too.  So the 80 m weakness was never coverage.  80 m puts every
wire the page can describe below a tenth of a wavelength up, where the
loss is the soil's and the form has the least to say -- the same regime
the falling-loss exponent leaves at zero.  Better data cannot reach it;
the page quotes the new figures and the tables stand on 1,076,831
solves.

## References

Sources for the published length tables this page is measured against,
and for the literature check on 71 ft.

- Jack Clarke VE3EED (SK), *The "Best" Random Wire Antenna Lengths*.
  The origin of the widely copied good/bad length tables.
  https://ve3ips.wordpress.com/2021/11/02/the-best-random-wire-antenna-lengthsrandom-wire-lengths-you-should-and-should-not-use-jack-ve3eed-sk/
  Mirrors: https://www.hamuniverse.com/randomwireantennalengths.html and
  https://ve7sar.blogspot.com/2019/01/the-best-random-wire-antenna-lengths.html
  The one documented correction to it is James KB5YN pointing out that
  220 ft was listed good while being the tenth half-wave multiple on
  15 m; VE3EED recomputed out to 500 ft in response.

- Mike Markowski AB3AP, *Random Wire Antenna Lengths*.
  https://udel.edu/~mm/ham/randomWire/
  The keep-out calculation this page's classical mode implements, and
  the origin of the C and Matlab versions in `random_wire/`.

- J.C. Sprott, *Optimal Length of Random Wire Antenna*, University of
  Wisconsin-Madison technote.
  https://sprott.physics.wisc.edu/technote/randwire.htm
  Independent run of the same avoid-the-resonances search, arriving at
  74 ft excluding 160 m and 143 ft for all bands.  Treats the feedline
  as part of the electrical length and handles velocity factor
  explicitly.

- *Random Wire Antennas -- A Challenge to Common Knowledge*, Ham Radio
  Outside the Box, 2024.
  https://hamradiooutsidethebox.ca/2024/09/04/random-wire-antennas-a-challenge-to-common-knowledge/
  Measures an 84 ft wire at 21-307 ohms and challenges the 450 ohm and
  9:1 convention rather than the lengths.

- ARRL, *Random Wires*.
  http://www.arrl.org/random-wires
  Offers **no** recommended wire lengths at all, only that a shorter wire
  reaches fewer bands.  It does specify a counterpoise, and the wording
  matters: "a long, insulated wire that attaches to the ground connection
  on your antenna tuner", best at "1/4-wavelength at the lowest frequency
  you intend to use", and installed by looping "the wire around the room".

  That is not the conductor this model has.  ARRL's counterpoise starts at
  the tuner, in the shack; this model's return starts at the feedpoint.
  Theirs is indoors, elevated and folded around a room; this one is a
  straight run 5 cm off the soil.  Their configuration sits squarely in
  the elevated-return regime the two-line form was measured to fail in --
  x1.60 median at 2 m, the reason a return-height axis was tried and
  rejected.

  So the quarter-wave preset borrows their number and applies it to a
  different geometry.  That, rather than any resonance argument, is why
  it does not behave the way their advice implies.

- S.A. Schelkunoff, *Theory of Antennas of Arbitrary Size and Shape*,
  Proc. IRE 29(9), 1941.  Source of the average characteristic
  impedance `Z0 = 60 (ln(2l/a) - 1)` used for both lines.

Not searched: QST, QEX and the ARRL Antenna Compendium, which is where a
serious treatment of end-fed feedpoint impedance would more likely sit,
and where a real refutation of 71 ft would most likely be found.  The
literature check above covers amateur web sources only.

## The peaks are too sharp, which matters most to end-fed half waves

Checked by asking whether the results make sense for an EFHW through a
49:1, where the physics is unambiguous.  Structurally they do: at the
page's defaults the second suggestion is 69.0 ft against a 68.8 ft half
wave on 40 m, and the first is 139 ft, a full wave on the same band.
The model knows where those lengths are.

The values there are wrong, though, and in a specific way.  Sweeping
across the 40 m half wave and comparing with NEC:

| l/lambda | NEC | model | ratio |
|---|---|---|---|
| 0.400 | 2066 | 1672 | 0.81 |
| 0.475 | 3897 | 3843 | 0.99 |
| **0.500** | **5388** | **10042** | **1.86** |
| 0.525 | 3811 | 2380 | 0.62 |
| 0.600 | 816 | 819 | 1.00 |

Within a couple of percent of the resonance the model runs nearly twice
high, and just past it nearly half.  Everywhere else it tracks within
about 20 percent.  The modeled peak is taller and narrower than the
real one, which is what `coth` does: it has a true pole where an antenna
has a finite maximum, and `alpha` is not damping it enough.

The consequences are opposite for the two ways this page gets used.  A
random wire is chosen to *avoid* the peaks, so exaggerating them is
conservative and harmless.  An end-fed half wave is chosen to sit *on*
one, so the error lands exactly on the length being picked: 69 ft on
40 m scores 5.0:1 through a 49:1 where NEC says 2.5:1, which would send
someone after a wide-range tuner when a compact auto would do.

It is not a fitting problem, which was checked rather than assumed.  A
fit dedicated to this one geometry, reaching x1.11 overall, still misses
the peak by x1.85: that is the ceiling for any technique, because the
peak height is `ka Z0 / (alpha l)` and the same `alpha` sets the loss
everywhere else.  Forcing it to fit the first peak -- 0.13 to 0.25
nepers per wavelength -- wrecks the higher ones, taking `l = lambda` from
0.87 of NEC to 0.53, and makes the overall error worse, x1.50 to x1.67.

The obvious form change fails, and its opposite half works.  Letting
`alpha` *grow* with electrical length, on the physical grounds that
radiation loss accumulates along a wire, makes the peak worse: at a power
of 0.5 the peak ratio goes from 1.85 to 3.19 and the overall error from
x1.11 to x1.17.

The measurement says the other direction.  Inverting NEC's peaks for the
`alpha_lam` each one would need gives a monotone *fall*:

| l/lambda | 0.5 | 1.0 | 1.5 | 2.0 | 2.5 | 3.0 | 3.5 |
|---|---|---|---|---|---|---|---|
| implied `alpha_lam` | 0.160 | 0.096 | 0.073 | 0.062 | 0.055 | 0.051 | 0.048 |

Fitted per group with `alpha_lam * (l/lambda) ** -p`, `p` comes out at
0.60 across 200 groups, with a tenth to ninetieth of 0.09 to 0.69 and
only seven groups in a hundred wanting none of it, and it helps where the
argument above says it should -- in the tail:

| per group, own coefficients | median | 90th | 99th | miscall at 9:1 into 3:1 |
|---|---|---|---|---|
| constant `alpha` | x1.106 | x1.349 | x2.056 | 17.0% |
| falling, `p` per group | x1.091 | x1.290 | x1.605 | 14.4% |
| falling, one shared `p` | x1.098 | x1.310 | x1.661 | 15.2% |

**And none of it survives the table.**  Shipped as one constant and put
through the real pipeline -- fit per group, weighted median onto the
nodes, joint refinement, interpolate -- the decision metric gets worse
almost everywhere: 9:1 into a 3:1 tuner improves from 21.9 to 20.9
percent on a flat top while every looser tuner degrades, the sloper goes
from 14.5 to 16.1, and the rate at which good lengths are called bad
climbs from 36 to 57 percent at 1:1.  The per-length 99th improves
(x2.23 to x1.88) and the decision does not.

That reading -- the length term makes each group fit better but the
surface of coefficients rougher, so tabulation gives back what the form
wins -- was the natural one, and measuring it on the converged sweeps
shows it is wrong.  Fitting every flat-top group both ways and comparing
each coefficient with its nearest neighbour on the (h/lambda, z/lambda)
grid, the exponent is the smoothest coefficient in the model: a median
step of 0.024 between neighbours, against a x1.11 jump in `alpha_a` and
x1.21 in `alpha_r`, and adding it roughens the others only slightly.
What the per-group fits show instead is a step in height:

| h/lambda | groups | constant | falling | fitted `p` |
|---|---|---|---|---|
| below 0.03 | 87 | x1.069 | x1.069 | 0.00 |
| 0.03 to 0.10 | 228 | x1.172 | x1.172 | 0.00 |
| 0.10 to 0.30 | 333 | x1.239 | x1.199 | 0.52 |
| 0.30 to 1.0 | 378 | x1.232 | x1.169 | 0.61 |
| above 1.0 | 225 | x1.225 | x1.157 | 0.63 |

A quarter of the domain, every wire under a tenth of a wavelength up,
wants no length dependence at all; everything above wants about 0.6.
Which is physical: near the ground the loss is soil loss, the same at
every length, and higher up it is radiation loss, which the measurement
says thins out along the wire.  The experiment above shipped one shared
exponent for the whole table, forcing 0.6 onto the quarter that wants
zero -- and the low wires are where the tight-tuner, low-band miscalls
concentrate, so the shared value helped the high wires and hurt the
decision where it is most sensitive.  That is the "better at 3:1, worse
on every looser tuner" signature.  `nec/alpha_length_check.py` is the
per-group experiment; the pipeline test was reverted, not shipped.

So the form change was not dead; it had been shipped in the wrong
shape.  Through the real pipeline -- fit per group, tabulate, refine,
fill -- a step (zero below h/lambda 0.1, 0.58 above) and a log-linear
ramp (zero at 0.1, 0.63 from 0.2 up, the shape the per-group exponents
trace) come out equivalent to a few tenths of a point everywhere, and
neither is worse than the constant-`alpha` table on both counts in any
unun-by-tuner cell of either geometry.  The ramp ships, as a closed
form rather than a table column: `p = 0.63 * clip(log2(h/lambda / 0.1),
0, 1)`, three constants in `nec/table_spec.py` the page evaluates from
the height it already knows.  Refit with it:

| | per group median / 90th / worst | per length median / 90th / 99th | miscall, 9:1 into 3:1 |
|---|---|---|---|
| flat top, constant `alpha` | x1.29 / x1.43 / x1.83 | x1.18 / x1.55 / x2.35 | 26.0% |
| flat top, falling by height | x1.25 / x1.40 / x1.79 | x1.16 / x1.49 / x2.06 | 23.6% |
| sloper, constant `alpha` | x1.24 / x1.35 / x1.45 | x1.16 / x1.45 / x2.09 | 20.7% |
| sloper, falling by height | x1.23 / x1.34 / x1.45 | x1.15 / x1.43 / x1.97 | 18.7% |

The gain grows with frequency, since that is where wires sit high in
wavelengths: on the flat top at the defaults 10 m goes from 18.3 to
15.0 percent wrong, 20 m 27.5 to 25.3, 40 m 29.4 to 27.6, and 160 m,
whose wires never clear a tenth of a wavelength, 45.6 to 46.2.  Where
the loose tuners offer more lengths the rate of good lengths called bad
falls by more than the miscall rate rises.  What remains true is that
the first half-wave peak reads nearly twice high in every form tried,
so an end-fed half wave through a 49:1 is the case the model serves
worst, and the random-wire case, which is what the page is for, is the
one it serves best.

One per-length figure in the json is not the model's: the flat top's
worst, x26.6, is three points at exactly a half wave on a 2 m wire at
7.15 MHz, where the resonance is so sharp that the 2x and 4x rungs sit
on different sides of it (19 and 96 kilohm) and the extrapolation
doubles it to 180.  The neighbouring lengths are ordinary.  It is a
measurement artifact at a peak, left in the data as measured.

## What the model deliberately does not do

- Predict a specific installation's feedpoint impedance.
- Model common-mode current on the feedline shield.  With a poor return
  path, "the feedpoint impedance" is not a well-defined single number at
  all, whatever the model prints.
- Model sag, insulation, nearby structures, or coupling to house wiring.
- Claim accuracy better than the installation variance, which is the
  dominant term and is not modeled.
