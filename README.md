# endfed

An end-fed random wire length calculator, and the NEC work behind it.

**The tool:** https://charlieh0tel.github.io/endfed/random-wire.html

Pick a wire length that avoids half-wave resonance on the bands you
care about, so an end-fed matching transformer sees an impedance a
tuner can reach. The page also estimates the feedpoint impedance from a
fitted two-line model, for a flat-top or a sloper, over soil you choose.

Everything runs in the browser. There is no server, no build step and
nothing to install.

## What is here

    docs/random-wire.html   the page
    docs/MODEL.md           what the impedance model claims, and what NEC measured
    docs/TODO.md            task status
    docs/BROWSER_CHECKS.md  the by-hand pass
    docs/tools/             dev-time type check and tests; not served
    nec/                    the sweeps, the fits, the coefficient tables

The coefficient tables in the page are fitted to NEC-4.2 sweeps and
regenerated from `nec/`, not hand-tuned. `docs/MODEL.md` says how well
they do and where they do not.

`nec/sommerfeld_report.html` is a separate finding: NEC-2's Sommerfeld
ground evaluation near the interface, across six NEC-2 builds and
NEC-4.2. It is why the sweeps use NEC-4.2.

## Development

    npm --prefix docs/tools install     # once
    npm --prefix docs/tools run check   # tsc and eslint
    npm --prefix docs/tools test        # the model, under node --test
    npm --prefix docs/tools run test:browser
    npm --prefix docs/tools run serve   # to look by hand

`uv run python <script>.py` in `nec/` for the measurement side; it needs
PyNEC, and the NEC-4.2 sweeps need a NEC-4 binary you supply yourself.

`master` is deployed by GitHub Pages, so pushing it publishes. A
`pre-push` hook is in `githooks/`: `git config core.hooksPath githooks`.

## Licence

GPL-3.0-or-later. See `LICENSE`.
