# random-wire.html TODO

Task status and open decisions.  The modeling approach, the parameter
split, and what NEC measured are in `MODEL.md`.

## Impedance-based length selection

Today the tool picks lengths by avoiding `n * lambda/2` with a fixed
percentage margin (AB3AP style).  That keep-out is a proxy: those
lengths are bad because the end-fed feedpoint impedance spikes there
(current node at the feed, `|Zin|` in the kilohms).  Selecting on
impedance directly is the same criterion with the proxy removed.

Potential gains:

- Continuous cost instead of a binary keep-out.  Rank candidate lengths
  by worst-case `|Zin|` (or post-unun SWR) across the selected bands.
- Catches the low-Z case.  Odd `lambda/4` gives ~35 ohm, which is ~4 ohm
  after a 9:1 unun.  The current model only avoids high-Z and is blind
  to this.  *Superseded:* NEC finding 2 measures 133-3500 ohm there, so
  the low-Z case is largely an artifact of ignoring the return path.
- Physically motivated zone widths.  The right margin scales with wire
  diameter and effective Q; a fixed percentage cannot express that.
- Better visual.  A predicted `|Z|` / SWR-vs-frequency trace for the
  recommended length beats keep-out bars for showing *why* a length is
  good.
- Makes the tuner a parameter: keep the match inside a stated range,
  e.g. `|Z|/9` within 25-600 ohm with bounded reactance.

Costs:

- Accuracy is worst exactly where it matters.  End-fed `Zin` is
  dominated by height, ground quality, counterpoise length, feedline
  common-mode current, and sag.  Real resonant peaks vary severalfold
  from predicted, so precise output would be false precision.
- Defensibility.  "Avoids half-wave resonance by 8%" is checkable
  arithmetic; "keeps `|Z|` under 1500 ohm" is true only under
  assumptions the user cannot see.
- Verification burden.  AGENTS.md wants math checked against
  references; `n * lambda/2` is trivially verifiable, an impedance
  model is not.

### Candidate model

Transmission-line approximation, open-circuited far end:

    Zin  = Z0 * coth(gamma * l),  gamma = alpha + j*beta
    Z0   = 60 * (ln(2l/a) - 1)    # Schelkunoff avg characteristic impedance
    beta = 2*pi/lambda * velocityFactor

Calibrate `alpha` so the model reproduces known anchors: `Zin ~ 36 ohm`
at `l = lambda/4`, which then yields `Z0^2/36` (several kilohms) at
`lambda/2`.  That gives a defensible envelope without pretending to
predict a specific installation.  Cheap enough for the browser, no new
dependencies.

### Status

Done: the page carries both methods behind a Method toggle (`?mode=`),
classical by default.  The default moved to impedance while that model
was being fitted and has moved back: the impedance mode carries an
EXPERIMENTAL ribbon.  Of the three reasons it went on, the first is now
gone -- the return height is swept and tabulated, and is a control --
while unconverged segmentation and a disagreement with the published
tables over staple lengths stand.  Neither geometry has been checked
against anything but NEC.  The impedance mode scores every
length by the geometric mean of the modeled SWR at the radio and
offers the local minima.  A worst-case score was tried first and
discarded: the lowest band always sets it, so it collapses into "prefer
the longest wire".

The model is anchored on the end-fed half wave at 2450 ohms, the figure
a 49:1 is wound for.  It was first anchored on the textbook 36 ohm
quarter-wave monopole, which assumes a perfect ground plane and put the
half wave near 5000 ohms, about twice what real antennas show; a 49:1
then read 1.7-2.2:1 where reality is near flat.  Re-anchored, the half
wave lands within 2 percent of target and a quarter wave falls at
44-70 ohms.

The half-wave end of that has since been confirmed against NEC; the
quarter-wave end has not survived it.  See the NEC findings below: a
quarter-wave antenna wire has no characteristic impedance to anchor to,
because the resonator includes the drop and the return path.

### Controls, decided

The model gained three parameters the user can actually measure --
height, return-path length and soil type -- and lost one they cannot,
the velocity factor.  All four shipped.  The velocity factor survives in
the classical mode only, where it is part of that method's checkable
arithmetic rather than a model parameter.

Once height and diameter are explicit, leaving `vf` settable would let
the user set the same physical effect twice and double-count it.

Dropped: a separate odd-`lambda/4` keep-out.  Measured, it empties the
solution space (HF-all returns nothing, the classic set drops to a
0.63 ft widest span), and the published tables sit *closer* to odd
quarter waves than chance because those points are the midpoints
between the half waves they avoid.  The impedance mode sees the low-Z
case as cost, which is the useful form of it.

## NEC: offline only, not in the loop

NEC does not belong at runtime.  It models the environmental unknowns
only if told what they are, and a web calculator's user cannot supply
them; assumed values yield a precise answer to a question nobody asked.
The error bar does not shrink, it just hides behind more decimals.
Cost is real: wasm NEC in a single-file Pages doc, sweeping every
candidate length x band x frequency step.

Use it instead as a one-time calibration and validation instrument.
Results ship as constants and caveat text, never as code.

Measured results are in `MODEL.md`, under "What NEC
measured".  The findings referenced by number above and below live
there.

Remaining:

- [ ] **Ship the two geometries.**  Modeling is done and measured;
      what is left is the page.  Refined, for `h/lambda >= 0.05`:

      | | median | 90th | worst |
      |---|---|---|---|
      | flat top | x1.25 | x1.33 | x1.62 |
      | sloper | x1.15 | x1.21 | x1.27 |
      | shipped today | x1.25 | x1.32 | -- |

      So the flat top matches what is live while gaining counterpoise
      height as a real axis, and the sloper is better than either.
      Coefficients are in `nec/coefficients2d.json`.

      Decided:

      - **Inline, stored sparsely.**  `alpha_a` and `ka` once per
        `h/lambda` node rather than repeated across every counterpoise
        node, which is 672 numbers instead of 960.  The page stays one
        self-contained file.
      - **New URL keys, old ones still read.**  `ret_m` means the whole
        return conductor and cannot keep that meaning, so the page
        writes the counterpoise run and height separately and still
        accepts `ret_m`, backing out the run on the assumption the
        counterpoise lay on the ground.  An old link resolves to the
        antenna it always meant, per the `len`/`len_m` precedent.
      - **Refuse unbuildable slopers.**  The wire must be longer than
        the rise from balun to apex, and the check is on the physical
        length rather than per band.  Say so, and say what length would
        reach, rather than modeling something that cannot be put up.
      - **Ribbon stays on both, text updated.**  Its first stated reason
        was an unswept return height, and that is now swept and
        tabulated.  The other two stand, and neither geometry has been
        checked against anything but NEC.

- [ ] **Slopers.**  Measured as not covered: against the flat model a
      sloper runs x1.57 to x5.72 median depending on which equivalent
      height is tried, and no substitution is consistent.  A common
      arrangement -- arguably the default, since the unun usually sits at
      the shack and the wire goes up to a tree.

      Remapping is out.  An effective height fits each case to x1.05-1.09
      median, so the form can represent a sloper, but the height it needs
      is frequency dependent (2.5 m at 7.15 MHz against 1.0 m at 14.175
      for the same antenna), and the page scores several bands at once.

      So it wants modeling, as a second geometry with its own table
      rather than another axis on this one.  A sloper's return really is
      different: the balun is already low, so there is almost no drop and
      the return is essentially just the counterpoise, where a flat top's
      return is dominated by the drop from h.  Same control, different
      line.

      The balun height needs no axis and no fixed value.  It looked
      like it did -- deviation up to x1.44 on 10 m across a stake-to-reach
      range -- but that measurement was confounded.  The balun height is
      the drop, the drop is part of the return conductor, and the model
      already solves the whole conductor analytically.  Holding the total
      return constant while moving the balun collapses the deviation to
      x1.08 worst, over every band and the whole range.

      So the page computes the return as `(balun height - counterpoise
      height) + run`, which is structurally what the flat top already
      does with wire height in place of balun height.  Nothing new is
      tabulated for it.

- [ ] **A sloper's wire has to be longer than the rise it climbs.**  Not
      a modeling choice but geometry: a wire from a 0.6 m balun to a
      20 m apex spans a 19.4 m rise, so nothing shorter reaches, and on
      10 m that rules out the entire length axis the page offers.  The
      page would have to refuse the combination rather than quietly
      model something unbuildable, and say why.

      That leaves the sloper with the same axes as the flat top: apex
      height, counterpoise height, counterpoise length, soil.  The sweep
      is `nec4_return_height_sweep.py` pointed at a sloper deck, and the
      page gains a geometry selector.

- [ ] **Counterpoise height as a control.**  Spiked and it works:
      `spike_return_height.py` fits NEC-4.2 across the axis from the
      ground to 0.9 of the wire height and the form holds, x1.13 to
      x1.19 median with only 0.9h degrading.  That reverses the earlier
      rejection, which was measured against PyNEC.

      Swept on the table's own axes and it holds: per-group error x1.19
      to x1.24 median from the ground to half the wire height, level with
      the shipped model's x1.25.  `alpha_r`'s bound is lowered and no
      longer rails.

      Only two of the six coefficients move along the axis, both
      monotonically -- `alpha_r` by x2.9 as the counterpoise sheds ground
      loss, `vf_r` from 0.82 towards 0.995 as it approaches free space.
      So what is left is:

      - decide the shape: a third table dimension, or a 1-D correction on
        `alpha_r` and `vf_r` against z/h.  The latter looks sufficient
        and is a far smaller change to the page.
      - fit it, ship the coefficients, and add the control
      - the model then has a regime where NEC-4.2 is measurably the
        better target, which is what would justify refitting on it

- [ ] Optional on-demand NEC run once a length is chosen, against the
      height, return path and soil already entered.  Different from the
      objection to runtime NEC, which was about sweeping every candidate:
      this is bounded work on a geometry the user has described, and it
      checks the installation rather than the envelope.

      `nec2c-wasm` and `nec2c-deck` now exist on npm (0.1.0, both
      GPL-3.0-or-later, both ours).  They split the license question
      rather than answering it:

      - `nec2c-deck` builds decks and parses output, no solver and no
        dependencies.  It is our own code with no nec2c in it, so it can
        be relicensed at will, and the page can use it either way.
      - `nec2c-wasm` is nec2c 1.3.1 compiled, so it carries Kyriazis's
        GPL and cannot be relicensed by us.  Serving it from `docs/` is
        distribution, and it makes the page a combined work.

      **Decided and done**: the whole repository is GPL-3.0-or-later,
      `LICENSE` at the root and the notice in the page header, so no
      part of this is a licensing question any more.  The
      wasm loads from a CDN on click, as React and Babel already do, so
      the classical mode never fetches it.  `nec2c-wasm/inline` is the
      entry point to use, 361 KB in one file, which avoids serving a
      separate `.wasm` from Pages.

      **Blocked on a solver gap.**  `nec2c-deck`'s `buildDeck` takes
      `ground: boolean` and emits `GN 1`, a perfect ground plane.  This
      model is fitted against `GN 2`, the Sommerfeld solution, with real
      soil constants, and ground loss is what dominates at the low
      heights the page warns about.  A button built on `GN 1` would
      compare the model against a different problem and disagree for
      reasons the user cannot see, which is worse than no button.

      Two ways out, both small:

      - add ground constants to `nec2c-deck`, an optional `{eps, sigma}`
        that emits `GN 2` instead of `GN 1`; it is our package
      - have the page emit its own cards and use `nec2c-deck` only for
        `parseOutput`, which the package explicitly supports

      **Done in nec2c-deck 0.1.1**, which takes `{epsR, sigmaSm}` and
      emits `GN 2`.  Verified against the fixture, and it uncovered a
      deeper problem: see below.

      Ready for it: `nec/reference_cases.json`, six
      installations with the feedpoint impedance PyNEC gives them across
      all five bands, generated by `reference_cases.py`.  The browser has
      to reproduce these within 2 percent before its output is worth
      showing anyone.  PyNEC wraps nec2++ and the page will carry
      Kyriazis's nec2c, so these are two independent translations of
      NEC-2 rather than the same code checking itself.

      The fixture is checked to discriminate: a deck built with `GN 1`
      instead of `GN 2` misses the reference by 5.3 to 36.9 percent, so
      the exact mistake that motivated it cannot pass.  The cases also
      span 329 to 3953 ohms and include the same length over poor and
      good ground, which differ by 11 percent, so a port that ignores
      soil constants fails too.

- [x] **The browser check.**  Built, on `nec2c-wasm`.  Chosen over
      `necpp-wasm` because the shipped tables are NEC-4.2's and nec2c
      tracks NEC-4.2 to 1 percent in this geometry down to a
      counterpoise at 1 cm, where nec2++ reads half; the page's default
      standoff lives inside that zone, so the abstractly better NEC-2
      is the wrong one here.  See MODEL.md, "Where NEC-2 is bad, and
      where it is not", and `nec/sommerfeld_report.html`.

      The button solves the configured antenna at every selected band
      -- the model curve's own frequency grid at every other point --
      across 97 lengths, left to right, in a small worker pool with a
      Stop button, then solves the midpoint of any span whose neighbors
      disagree by more than 1.3x until the rough spans are smooth or at
      the model curve's own grid, then measures the wire in hand and
      every offered length at scoreLength's full grid, so the verdict
      and the Best lengths table show a measured figure beside each
      modeled one.  The overlay draws the same statistic as the model
      curve (geometric mean SWR at the radio) and is keyed to every
      input it depends on, so any change clears it.  What it disagrees with is the model, up to 2x near a half
      wave, which is the honest thing for it to show.  With the
      feedpoint under 0.05 wavelengths on a selected band -- NEC-2's own
      failure regime, a sloper fed low or a low wire on a long band --
      the check warns first and runs only on request, so a measurement
      of the solver is never passed off as one of the model.

      Open: nec2c has a second failure the gate does not cover.  Past a
      half-wave peak at a low counterpoise it invents a second
      resonance, up to x14 against NEC-4.2, where nec2++ tracks the
      same region within about 10 percent -- and the two fail in
      different places (MODEL.md, "Neither browser NEC-2 survives").
      Candidate fix: run both wasm solvers and draw only where they
      agree, marking a split as uncheckable in a browser.

- [ ] **Model the counterpoise in contact with the ground.**  Most
      people let the coax lie on the dirt.  The model holds it 5 cm up
      because NEC-2 must: a wire bonded to the ground plane shorts the
      source.  NEC-4 has no such limit, and `ground_contact.py` shows
      the standoff is not free -- 5 cm above against 5 cm below moves
      the feedpoint about 15 percent near half- and full-wave
      multiples, and up to x5.02 at a quarter wave, which is where the
      picker operates.

      It also retires the argument that made the standoff look safe:
      "0.01 m gives nearly the same answer" is true in PyNEC (x0.92)
      and false in NEC-4.2 (x1.31).

      Recipe, all three needed: split the drop at z = 0, since no
      segment may span the interface; `GE 0`, because `GE 1` rejects
      anything at or below it; and avoid z = 0 exactly, which puts the
      wire *in* the interface and returns a value inconsistent with
      both sides.  Buried is well behaved from 1 cm to 50 cm down.

      What it does not do is let the return sit *on* the ground.  That
      case is not expressible: the thin-wire kernel wants one medium
      around the conductor and a wire on the surface has half its field
      in each, so z = 0 returns a value consistent with neither side and
      the above branch fails below about 1 cm.  Closing the bracket from
      5 cm to 1 cm either side does not converge -- at a quarter wave it
      widens, x2.19 median against x1.57.  Insulation does not change
      this; soil at HF is a lossy dielectric, so contact is not shorting
      and coax and bare wire are the same case.

      So the decision is not a depth but a regime, and the honest
      justification for staying above ground is mechanical: real ground
      is not flat, and a centimeter or two of average clearance
      describes coax draped over grass and ruts.  Two things follow,
      both open:

      - is 5 cm the right clearance for that story, or 1-2 cm?  NEC-4
        puts 31 percent between them, and 5 cm was never chosen for a
        physical reason.
      - radials or a counterpoise under the turf are a genuinely
        different install, and burial models them well -- nearly flat
        from 1 to 50 cm down, so it needs no depth from the user.  That
        is where a second model would earn its keep, rather than
        between solvers.

- [ ] Decide the default return length.  25 ft is what a typical user's
      coax run is, and it gives the best agreement with the published
      tables of any value tried, but the ARRL specifies a quarter wave
      at the lowest band, about 66 ft on 80 m, and most published
      lengths do score better with a longer return.  Consider saying so
      in the page rather than moving the default: a long counterpoise
      flattens the score curve, so length choice matters less, which is
      more useful than any single length.
- [ ] Exercise the page in a browser for the things a machine cannot
      judge.  The mechanical half is automated in
      `docs/tools/browser/random-wire.spec.mjs` and runs in CI;
      `BROWSER_CHECKS.md` is now only the judgment calls --
      whether the caveat text reads well, whether the recommendations
      look right for a real installation, whether anything has drifted
      that no assertion covers.

Tooling: `nec/`, Python + PyNEC, `uv`-managed.

## The shipped table: bounds, convergence, and what re-checks it

From the three-way review of 14 Aug 2026 (two Claude passes and a codex
pass; the fixes that shipped that day are in the git log).

**Open, and next.**  Measure how smoothly the fitted coefficients vary
across `h/lambda` and `z/lambda`, which nothing here has ever looked at.

It came out of the length-dependent loss experiment (`MODEL.md`, "The
peaks are too sharp"): letting `alpha` fall with electrical length is
what the data asks for and improves every per-group figure -- the 99th
per-length error from x2.06 to x1.66, the miscall rate from 17.0 to 14.4
percent -- and then loses all of it through the table.  Fit per group,
weighted median onto the nodes, refine, interpolate, and the decision
metric comes out worse almost everywhere.

So a form that fits each group better is not the thing to look for.  The
thing to look for is a form whose coefficients make a smooth surface over
the two axes the table indexes, because that is what the tabulation can
carry.  The fits already on disk are enough to measure it: per-group
coefficients against `h/lambda` and `z/lambda`, how much a node's value
differs from its neighbours', and how much of the per-length error is
interpolation rather than form.  No solver time.

**Open, and a project rather than a task.**  Chasing the model form
itself.  The peaks read x1.86 high because one `alpha` sets the loss at
every length, and the measurement says it should fall as `(l/lambda)`
to about -0.6.  Per group that is worth taking the 99th per-length error
from x2.06 to x1.66 and the miscall rate from 17.0 to 14.4 percent.  It
does not survive the table, which is the finding above.

What that leaves, in rough order of how much it would have to change:

- a length-resolved line, integrating Schelkunoff's local `Z0` along the
  wire rather than scaling one average, which subsumes both the falling
  loss and the height-dependent `Z0` experiment already recorded here;
- a term that bites only near resonance, which is what the peaks
  actually want and what the current form cannot express;
- tabulating the exponent as a seventh coefficient, the obvious move and
  the one most likely to lose again to interpolation.

None of these is worth starting before the smoothness measurement above,
because that says whether a richer form can be carried by a table at
all.

**Open.**  Coefficients in `coefficients2d.json` sit exactly on
their refinement bounds.  Of 1440 values per geometry, after the 16 Aug
refit: the flat top has `vf_r` at its 1.0 ceiling 41 times,
`alpha_r_lam` on its 0.05 floor 14 times, `alpha_a_lam` at its 0.4
ceiling 11; the sloper has `alpha_a_lam` at that ceiling 22 times.
A parameter held at its constraint is the bound,
not a measurement -- the "compensating for the model rather than fitting
the antenna" case `table_spec.py` says the bounds exist to prevent.
*Decided:* investigate before refitting.  Find which (h/lambda, z/lambda,
soil) cells rail and whether they share a corner; a physical edge and a
model deficiency want different answers.

**Open.**  `coefficients2d.py` refines with `least_squares` and keeps
`out.x` while discarding `out.status` and `out.success`, so a run that
stopped at `max_nfev` is indistinguishable from a converged one after
the fact.  `fit.py` raises on `status <= 0`; this does not.  Nothing in
the json records nfev, status or the `--max-nfev` used, nor which
parameters were held out of the refinement and which came back on a
bound -- both are printed once and then lost, and both are what a reader
needs to know how much of a cell is measurement.  `scipy` is also
unpinned, which for a table that takes hours of NEC time to reproduce is
the same hazard `uv.lock` exists to close.

**Open.**  Every figure the page quotes is still in sample in every axis
but frequency.  `holdout_check.py` covers frequency, and `MODEL.md`
records what it cost: 1.9 points of miscall rate.  The stronger version
is an out-of-band holdout against fresh NEC solves -- a height, a
counterpoise or a soil the sweeps never carried -- and it wants machine
time rather than the fifteen minutes a refit takes.

**Open.**  `nec_model._wires` segments the flat top's drop by the wire
height rather than by the drop's own length, so a counterpoise well up
gets a finer drop than intended -- 49 segments where 25 are asked for, at
28.85 MHz with a 25 m wire and the counterpoise at 12 m.  `sloper_deck`
segments its drop correctly.  Finer is not wrong, and every shipped
table was fitted with it, so correcting it means a re-sweep before the
tables can be reproduced from source.

**Open.**  The unun is not in the model.  NEC measures the feedpoint and
the page divides by the ratio, so an ideal, lossless, frequency-flat
transformer is assumed at the one place in the system least likely to be
any of those: a 9:1 on a wire that swings 130 to 3500 ohms is far from
its design load over most of that range.  Whatever it costs is charged
to the model's error budget, where it cannot be told apart from the
table's own.

**Open.**  `sweep_grid.py` says every sweep imports it "so that two grids
cannot drift apart and be read as one", and three no longer do:
`gauge_sweep.py`, `ground_contact.py` and `nec4_gauge_sweep.py` each
redeclare `FREQS_HZ`, and `nec4_table_sweep.py` adds two frequencies of
its own on top of it.  Either the claim goes or the imports come back.
`segmentation_check.py` has the same kind of drift in its head: it
reasons about NEC-2's junction assumption and solves with PyNEC, while
every shipped table is now NEC-4.2.


**Decided, not yet built.**  Accessibility: the length map is mouse-only,
with no role, name or live region.

## NEC-5 and insulation: the plan

NEC-5 is coming up locally.  Insulation is likely the largest unmodeled
effect the user controls: a jacket lowers the wire's velocity factor by
a few percent, which moves every resonance in length -- the axis the
page picks on -- and the modeled mode cannot express it (vf_a is pinned
at 1.0 and everything was measured bare).  The insulation number is a
differential -- insulated against bare in the same solver -- so it does
not wait on the which-reference question, and the two tracks decouple:

- **A, done.**  NEC-5 passes the conductivity limit beside NEC-4.2.
- **B1, done, with a twist.**  The ground delta vanishes at
  convergence (x1.03 median, x1.12 worst over a 144-geometry slice);
  what it exposed instead is that the shipped fitting density of 20
  segments per wavelength carries x1.20 median / x1.60 90th error
  against converged answers -- the size of the model's whole quoted
  budget.  See MODEL.md, "NEC-5 arrives".
- **The density study, done.**  Convergence is first-order and never
  practically completes; Richardson extrapolation from a (2x, 4x) pair
  reaches within x1.02 median / x1.07 90th of the limit for 3.2x the
  solve time.  D is therefore: re-sweep at 2x and 4x, extrapolate re
  and im separately, refit -- about 14 wall hours, needing explicit
  approval before it runs.  See MODEL.md, "The density study".
- **B2, done.**  A scalar, as hoped: vf 0.986-0.990 for a 0.3 mm wall
  and 0.974-0.981 for 0.6 mm, near-constant over 1.9-28.85 MHz and
  2-20 m of height.  NEC-4.2's IS card alone -- this NEC-5 build has
  insulation stubbed out (RSETIS stores nothing).  See MODEL.md,
  "Insulation is a scalar".
- **C, done.**  A Wire control, bare/insulated, scaling both fitted
  lines' velocity factors by the measured 0.98, riding the URL as
  `wire=`.  The check's probe decks carry the jacket as K6OIK's
  equivalent wire, validated against the IS card to 0.02 percent, so
  the overlay stays a real check for insulated wire in both wasm
  solvers.  See MODEL.md, "Insulation is a scalar".
- **D, running.**  Re-scoped by B1 and priced by the density study:
  re-sweep both geometries at 2x and 4x the fitted density
  (`nec4_table_sweep.py --density`), Richardson-extrapolate real and
  imaginary parts separately (`extrapolate_sweep.py`), refit from the
  extrapolated impedances.  Solver stays NEC-4.2: converged, it agrees
  with NEC-5 within x1.03 median.

**Open, low priority.**  The maxima panel's per-band view could carry
measured profiles instead of arithmetic: the check's outputs already
hold the per-segment current tables, and NEC's PQ card (charge
density, which is the voltage profile) is verified in nec2c, nec2++,
NEC-4.2 and NEC-5, the first three agreeing to four digits on the
calibration dipole.  A day's work when a use asks for it; the union
view stays arithmetic, since a measured union washes out.

## Considered and declined

- Refitting the coefficients against NEC-4.2.  Measured rather than
  argued: fitted to each grid, the same form gives x1.25 median and
  x1.32 against x1.33 at the 90th for `h/lambda >= 0.05`.
  Indistinguishable where the page claims accuracy, so the refit would
  change the constants and not the answers.  Revisit if the model ever
  reaches below `h/lambda` 0.05, where the same form fits NEC-4.2 about
  twice as well, x1.71 worst against x3.12 -- that is the
  counterpoise-height direction, and it is what would make NEC-4.2 the
  right target.  See MODEL.md.

- Deriving `marginPct` from a user-set `|Z|max` instead of a magic
  percentage, in the classical mode.  Buildable and honest, and declined
  because over most of its range the honest answer is that no length
  qualifies.  Measured: 8 percent buys about 2800 ohms and leaves 23
  percent of the axis, which makes the shipped default a defensible
  thing to have reached by feel.  Below that it saturates fast -- 1500
  ohms costs an 18 percent margin and leaves 0.6 percent of the axis,
  and 1000 ohms is unreachable at any margin.  A control whose range is
  mostly "nothing qualifies" teaches the user less than the fixed
  percentage it would replace.

- Modeling the ARRL counterpoise configuration -- source at the tuner,
  counterpoise folded around a room a meter or two up -- as a spike.
  Cheap to build, about eighty lines beside `end_fed_zin` reusing the
  existing sweep and fit machinery, but limited in what it could settle.
  NEC-2 has no walls, no mains wiring and no plumbing, so "indoors"
  becomes "folded wire in free space over ground", and the room size is
  a parameter nothing determines.  More to the point, at one to three
  meters the two-line form is already measured at x1.60, so a successful
  spike would establish what that configuration does while confirming
  the page still cannot score it.

## Open questions

- Counterpoise is now an explicit axis rather than a calibration
  constant (finding 4 forced this), but the two real cases differ:
  a thrown-out wire is well defined, while the coax shield carries
  common-mode current that makes "the feedpoint impedance" not a single
  well-defined number at all.  How much of that caveat reaches the user?
- How should the soil control be labeled so it does not imply that
  "good" ground gives a better match?  Finding 6 says it does not.
- Does the fitted `alpha`/`beta` surface interpolate cleanly over
  `h/lambda` once the return resonance is pulled out into its own term,
  or does it still need a spline?
