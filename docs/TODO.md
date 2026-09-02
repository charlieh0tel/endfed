# random-wire.html TODO

Open work and decisions still to make.  The modeling approach, the
parameter split, and everything NEC measured -- including the record
of what was tried and settled -- are in `MODEL.md`.

Tooling: `nec/`, Python, `uv`-managed; NEC-4.2 and NEC-5 local,
nec2c and nec2++ in the page.

## The model

- [ ] **nec2c reads fiction on an insulated wire over a long, moderately
      high counterpoise, and the check still trusts it.**  Example:
      flat top 3.75 m up, insulated, a 21 m counterpoise at 1.87 m,
      9:1 into 40-10 m -- nec2c draws 37:1 to >99:1 across the map where
      the model and nec2++ agree near 3.5:1, and `nec2cCredible` calls it
      credible on every band.  The solver ranking says nec2c is reliable
      at z/lambda > 0.05 (which this config is on all but 40 m), so the
      cause is outside what the ranking measured: the insulated wire (the
      ranking was bare) or the long counterpoise.  Fix needs either a
      small nec2c run over insulated wire and long counterpoises to find
      the real boundary, or an a-posteriori gate -- suppress nec2c where
      it disagrees with nec2++ by orders of magnitude and nec2++ tracks
      the model -- which needs no solver time.  The electrical-height
      fix (2026.09.02.004) was a real correctness win but does not reach
      this regime.

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
