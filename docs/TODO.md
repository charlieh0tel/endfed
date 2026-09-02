# random-wire.html TODO

Open work and decisions still to make.  The modeling approach, the
parameter split, and everything NEC measured -- including the record
of what was tried and settled -- are in `MODEL.md`.

Tooling: `nec/`, Python, `uv`-managed; NEC-4.2 and NEC-5 local,
nec2c and nec2++ in the page.

## The model

- [ ] **`nec_model._wires` segments the flat top's drop by the wire
      height** rather than by the drop's own length, so a counterpoise
      well up gets a finer drop than intended -- 49 segments where 25
      are asked for, at 28.85 MHz with a 25 m wire and the counterpoise
      at 12 m.  `sloper_deck` segments its drop correctly.  Finer is
      not wrong, and every shipped table was fitted with it, so
      correcting it means a re-sweep before the tables can be
      reproduced from source.

## The page

- [ ] Exercise the page in a browser for the things a machine cannot
      judge.  The mechanical half is automated in
      `docs/tools/browser/random-wire.spec.mjs` and runs in CI;
      `BROWSER_CHECKS.md` is now only the judgment calls --
      whether the caveat text reads well, whether the recommendations
      look right for a real installation, whether anything has drifted
      that no assertion covers.

## Considered and declined

- A buried-radials variant.  The remainder of the ground-contact
  question, declined for want of anyone who wants it: it entered as
  modeling completeness (burial is the expressible neighbor of the
  inexpressible wire-on-ground), not as demand, and this page's users
  drape a counterpoise rather than bury a field.  The design is settled
  if that changes: depth is not an axis (measured flat 1 to 50 cm), the
  z axis drops so the table goes 1-D in h/lambda, radial count is the
  one real axis, and the whole campaign is about a solver-day.

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
