# NEC modeling for the random wire picker

Offline instrument behind the impedance model in `docs/random-wire.html`.
It does not run at the site: it produces fitted coefficients that are
copied into the page, along with the error bound that becomes the page's
caveat text.  The approach and the measured findings are in
`docs/MODEL.md`.

The point of keeping it in the repo is auditability.  The page's claim
to be defensible rests on constants with stated assumptions and a
bounded error, and constants whose producing code has been discarded
cannot be checked.  This is the source for them.

## License

These scripts are GPL-3.0-or-later, like the rest of the repo.  They
import PyNEC, which is GPL-3.0-only; PyNEC is a declared dependency
fetched from PyPI, not vendored here, and copying PyNEC or nec2c source
into this repo would be a different matter, which is why nothing does.

The numeric output is a separate matter again: a program's output is not
covered by the program's license, so the fitted constants carry no
obligation of their own into the page.

## The Sommerfeld comparison

`sommerfeld_report.html` is the write-up prepared for the NEC
maintainers: NEC-4.2 and six NEC-2 builds measured against a limit with
an exact answer, showing that the near-ground failure is NEC-2's
Sommerfeld evaluation rather than any port of it.  Open it in a browser;
it is self-contained.  The same findings, with more of the surrounding
argument, are in `docs/MODEL.md`.

Two scripts produce its numbers.  `sommerfeld_cross.py` sweeps a dipole
in height, which is where an implementation's envelope shows;
`nec2c_ground_bug.py` sweeps conductivity for this page's own
installation.  Both take solvers as `name=style:path`.

## Running

```sh
uv run validate.py       # textbook cases; run this first
uv run sweep.py          # the full grid, ~9 minutes on 16 cores
uv run analyze.py        # tests the series decomposition against sweep.npz
```

`validate.py` is the regression test.  A quarter-wave monopole over
perfect ground should read near 36+j21 and a free-space half-wave dipole
near 73+j42, both overshooting slightly for a thin wire.  If those move,
distrust everything else.

`sweep.npz` is generated, not committed; `sweep.py` rebuilds it.  Note
that it is a NEC-2 grid: what the page ships is fitted to the NEC-4.2
sweeps instead, for the reason the Sommerfeld comparison below gives.

## Files

What ships comes from one chain, and only this chain:

    nec4_return_height_sweep.py |  ->  fit.py  ->  table2d.py
    nec4_sloper_sweep.py        |        ->  coefficients2d.py  ->  the page

- `table_spec.py` -- what is tabulated, over what nodes, within what
  bounds.  The specification the other three are built to.
- `fit.py` -- fits one group of NEC solves to the two-line form.
- `table2d.py` -- collapses the per-group fits onto the table's axes.
- `coefficients2d.py` -- refines the table jointly, writes
  `coefficients2d.json`, and patches the page.  `--write-page` is the
  only thing that may touch the generated block.

The rest are instruments:

- `nec_model.py` -- the geometry: antenna wire at height h, vertical
  drop at the feedpoint, horizontal return run standing for the coax
  shield or a counterpoise.  Everything else imports this.
- `validate.py` -- textbook cases and an end-fed smoke test.
- `sweep.py` -- the full parameter grid, written to `sweep.npz`.
- `analyze.py` -- tests whether the return path is additive.
- `probe.py` -- compares NEC against the page's shipped model at both
  anchors, over height, return length and soil.
- `return_sweep.py` -- return length alone, showing its resonance.
- `chase.py` -- decomposes the quarter-wave disagreement.
- `ground_low.py` -- soil behavior at low height, as curves.
- `sommerfeld_cross.py` -- every NEC build against the conductivity
  limit, swept in height.  `--decks=DIR` writes the decks out.
- `nec2c_ground_bug.py` -- the same limit for this page's installation,
  swept in conductivity.
- `sommerfeld_report.html` -- the write-up of both, for upstream.
