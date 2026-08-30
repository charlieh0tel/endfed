# random-wire.html TODO

Open work and decisions still to make.  The modeling approach, the
parameter split, and everything NEC measured -- including the record
of what was tried and settled -- are in `MODEL.md`.

Tooling: `nec/`, Python, `uv`-managed; NEC-4.2 and NEC-5 local,
nec2c and nec2++ in the page.

## The model

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

- [ ] **The first half-wave peak.**  It reads nearly twice high in
      every form tried, and the falling loss did not touch it: at
      `l/lambda` 0.5 the exponent barely acts.  It is the end-fed half
      wave through a 49:1, the one case chosen to sit *on* a peak, and
      it needs a structural idea rather than another exponent.  In
      rough order of how much would have to change:

      - a length-resolved line, integrating Schelkunoff's local `Z0`
        along the wire rather than scaling one average;
      - a term that bites only near resonance, which is what the peaks
        actually want and what the current form cannot express;
      - a modal representation instead of one line.

      Research rather than a task.  See MODEL.md, "The peaks are too
      sharp".

- [ ] **Out-of-band holdout.**  Every figure the page quotes is in
      sample in every axis but frequency.  `holdout_check.py` covers
      frequency, and `MODEL.md` records what it cost: 1.9 points of
      miscall rate.  The stronger version is a holdout against fresh
      NEC solves -- a height, a counterpoise or a soil the sweeps never
      carried -- at 2x and 4x density, extrapolated, an evening of
      solver time on explicit approval.

- [ ] **The sloper's `alpha_a_lam` ceiling.**  Raising the refinement
      bound from 0.4 to 0.6 is worth about x1.27 to x1.25 in the
      sloper's lowest cells and nothing on the flat top.  A refit and a
      bump; marginal.  See MODEL.md, "Coefficients on their bounds".

- [ ] **The unun is not in the model.**  NEC measures the feedpoint and
      the page divides by the ratio, so an ideal, lossless,
      frequency-flat transformer is assumed at the one place in the
      system least likely to be any of those: a 9:1 on a wire that
      swings 130 to 3500 ohms is far from its design load over most of
      that range.  Whatever it costs is charged to the model's error
      budget, where it cannot be told apart from the table's own.

- [ ] **`nec_model._wires` segments the flat top's drop by the wire
      height** rather than by the drop's own length, so a counterpoise
      well up gets a finer drop than intended -- 49 segments where 25
      are asked for, at 28.85 MHz with a 25 m wire and the counterpoise
      at 12 m.  `sloper_deck` segments its drop correctly.  Finer is
      not wrong, and every shipped table was fitted with it, so
      correcting it means a re-sweep before the tables can be
      reproduced from source.

- [ ] **`sweep_grid.py`'s claim.**  It says every sweep imports it "so
      that two grids cannot drift apart and be read as one", and three
      no longer do: `gauge_sweep.py`, `ground_contact.py` and
      `nec4_gauge_sweep.py` each redeclare `FREQS_HZ`, and
      `nec4_table_sweep.py` adds two frequencies of its own on top of
      it.  Either the claim goes or the imports come back.
      `segmentation_check.py` has the same kind of drift in its head:
      it reasons about NEC-2's junction assumption and solves with
      PyNEC, while every shipped table is now NEC-4.2.

## The page

- [ ] Decide the default return length.  25 ft is what a typical user's
      coax run is, and it gives the best agreement with the published
      tables of any value tried, but the ARRL specifies a quarter wave
      at the lowest band, about 66 ft on 80 m, and most published
      lengths do score better with a longer return.  Consider saying so
      in the page rather than moving the default: a long counterpoise
      flattens the score curve, so length choice matters less, which is
      more useful than any single length.

- [ ] **Accessibility of the length map.**  Decided, not yet built: the
      map is mouse-only, with no role, name or live region.

- [ ] Exercise the page in a browser for the things a machine cannot
      judge.  The mechanical half is automated in
      `docs/tools/browser/random-wire.spec.mjs` and runs in CI;
      `BROWSER_CHECKS.md` is now only the judgment calls --
      whether the caveat text reads well, whether the recommendations
      look right for a real installation, whether anything has drifted
      that no assertion covers.

## Considered and declined

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

- A separate odd-`lambda/4` keep-out in the classical mode.  Measured,
  it empties the solution space (HF-all returns nothing, the classic
  set drops to a 0.63 ft widest span), and the published tables sit
  *closer* to odd quarter waves than chance because those points are
  the midpoints between the half waves they avoid.  The impedance mode
  sees the low-Z case as cost, which is the useful form of it.

## Open questions

- Counterpoise is an explicit axis rather than a calibration constant,
  but the two real cases differ: a thrown-out wire is well defined,
  while the coax shield carries common-mode current that makes "the
  feedpoint impedance" not a single well-defined number at all.  How
  much of that caveat reaches the user?
- How should the soil control be labeled so it does not imply that
  "good" ground gives a better match?  Measured, it does not.
