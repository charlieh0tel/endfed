# random-wire.html TODO

Open work and decisions still to make.  The modeling approach, the
parameter split, and everything NEC measured -- including the record
of what was tried and settled -- are in `MODEL.md`.

Tooling: `nec/`, Python, `uv`-managed; NEC-4.2 and NEC-5 local,
nec2c and nec2++ in the page.

## The model

- [ ] **Radials or a counterpoise under the turf.**  What remains of
      the ground-contact question.  The physics half is settled and in
      MODEL.md ("The 5 cm standoff, revisited"): wire *on* the surface
      is not expressible, the above branch is usable to about 1 cm, and
      the default now describes a drape (2 cm) rather than a standoff.
      The open half is burial: radials under the turf measure nearly
      flat from 1 to 50 cm down, so a buried-return variant needs no
      depth from the user -- but it is a different antenna, and wants
      its own sweep and table before the page can offer it.

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

## The page

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
