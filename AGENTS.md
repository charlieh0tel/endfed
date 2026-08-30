# Agent Instructions

## Project Overview

One page and the measurements behind it.

- `docs/random-wire.html` is the tool: end-fed random wire lengths that
  avoid half-wave resonances on selected bands, with a fitted impedance
  model. React + inline JSX transpiled by Babel standalone in the
  browser, no other runtime dependencies. Band plans (US, IARU regions
  1-3) are a data table. GitHub Pages serves `docs/` from `master`, so
  pushing to `master` is a deployment.
- `docs/tools/` is dev-time only: nothing there is served.
- `nec/` is the instrument: NEC sweeps, the fits, and the coefficient
  tables the page ships. Python, `uv`-managed.

The whole repo is GPL-3.0-or-later, `LICENSE` at the root and a notice
in the page header. Nothing here is MIT; if a file says otherwise it is
stale. The page is GPL by choice, settled before the nec2c-wasm path it
anticipates, not because PyNEC is a dependency of `nec/`.

Companion notes, not served. `docs/MODEL.md` is the modeling approach
-- what the impedance model claims, the parameter split, and what NEC
measured. `docs/TODO.md` is task status. `docs/BROWSER_CHECKS.md` is the
by-hand pass, for what no automated check can judge. Keep findings and
design decisions in the model note and task state in the TODO.

## General

- Be extremely concise; sacrifice grammar for concision.
- Always list unresolved questions at end.
- Use built-in tools for file operations: globs for file search, grep
  for content search, read for viewing files.
- Do not request grep/sed/fd/find/ls/cat or similar CLI tools when you
  already have these capabilities built-in.
- Prefer ASCII in all code and user-facing strings (logs, CLI output,
  error messages).  Ask before using Unicode.
- Never use `pkill` with a regex, or `pkill -f` at all.  It matches every
  process on the machine, not this project's: it has killed a browser
  because a tab had a source file open.  Kill by PID.
- Use US spellings everywhere -- prose, comments, identifiers and
  user-facing strings: modeling, meter, center, license, color,
  behavior, labeled, normalized, analyzer.

## Documentation

- Keep documentation (.md files) up to date with code changes.
- When work completes a tracked item, remove it from `docs/TODO.md` in
  the same commit and put what it found in `docs/MODEL.md`.  The TODO
  holds open work only; the model note is the record.

## Revision Control

- Do not add Claude or other agent attribution to anything (commit
  messages, pull requests, issues).
- Do not commit without permission.
- Never use -a to commit; always enumerate the files.
- All tests must pass before committing.
- Suggest making a commit before moving onto something unrelated; a PR
  should generally be one functional change.

## Programming

- Read code before modifying it.  Understand existing patterns and
  context before proposing changes.
- Prefer consistency above most other concerns.
- Be DRY.
- Keep functions short and focused; extract helpers when logic is
  reused.
- Avoid magic constants.
- Use meaningful names, especially for RF and math quantities
  (`zLoad`, `gammaL`, `susceptance`; not `x`, `tmp`).
- Don't abbreviate by dropping letters from the middle of a word.
  Truncation (cutting from the end) is OK.
- Comment only unintuitive or hard to understand code; always comment
  data structures.  Do not leave diaries in comments: a comment says
  what the code does now, not what it used to do.
- Comment non-obvious RF and math formulas, and cite their sources.
- Verify math against known references.  Watch sign conventions and
  unit conversions (degrees/radians, MHz/Hz).
- Calculate in SI internally.  Convert at the edges: read input and
  format output in whatever unit the user wants, but keep one coherent
  system in between.  Name the unit in the type, not only in the
  identifier.
- The unit aliases here (`Feet`, `KiloHertz`, `MegaHertz`, `Meters` in
  `random-wire.html`) are plain `@typedef {number}` aliases, so they
  document intent but do not enforce it: `tsc` sees them as `number` and
  will not catch meters added to hertz.  Treat them as naming
  discipline, not a type system.
- The one exception to calculating in SI is roundness: a recommended
  length is rounded in whatever unit the user is reading, so the picker
  takes the display unit.
- Do not annotate a lookup table with `Object<string, ...>`. That widens
  its keys to `string` and defeats the narrowing that keeps a bad URL
  parameter out of the table.
- No trailing whitespace.
- Do not add dependencies without discussion.
- Run a type check (if appropriate), a syntax check and a style check
  before committing.

## Python

- Use `uv` for all dependency and environment management.  `nec/uv.lock`
  is committed: the sweeps take hours of NEC time and the coefficient
  tables are fitted from them, so a silent resolver change is a silent
  change to the shipped page.
- Run `ruff format` and `ruff check` after changes and before commits.
- There is no pytest suite. `nec/validate.py` is the regression check for
  the physics and prints numbers a human reads.
- `nec4d42` and `nec5cl` are OpenMP builds that start a thread per core
  for every solve.  Anything that runs them in a pool sets
  `OMP_NUM_THREADS=1` in the subprocess environment (`SOLVER_ENV` in the
  sweep tools); without it a dozen workers are two hundred runnable
  threads, a load average over a hundred, and a forty-fold slowdown.
- `nec/deck_check.py` reads the NEC decks the geometry builds -- wires,
  segmentation, source, ground card, both geometries -- without solving
  them, so CI runs it.  `nec/validate.py` is the other half and needs a
  solver: textbook physics, by hand, locally.
- `nec/pipeline_check.py` is the regression check for the fitting code: it
  runs `fit.py`, `table2d.py` and `coefficients2d.py` over a committed cut
  of a NEC-4.2 sweep and compares the cost and error statistics against
  committed values, in about
  two seconds and with no solver.  CI runs it, because CI cannot have
  NEC-4.2.  After an intended change, `--write` and say in the commit what
  moved.

## TypeScript Rules

- Write clean, readable JavaScript. Use modern ES6+ patterns and style;
  `const`/`let`, never `var`.
- Consistent 2-space indentation.
- Use template literals over string concatenation.
- Type every function parameter and return with JSDoc; the checker below
  runs under `strict`, so an unannotated parameter is an error.
- Use `npm` (the committed `package-lock.json`) for dependency management.

## Type Checking

`docs/tools/` holds a dev-time type checker.

```sh
npm --prefix docs/tools install   # once
npm --prefix docs/tools run check   # tsc and eslint
npm --prefix docs/tools run lint    # eslint alone
```

`check` runs eslint after `tsc`, over the same extracted `.jsx`.  The rule
it exists for is `react-hooks/exhaustive-deps`: a dependency array that
listed a derived object rather than the inputs behind it let switching
display units silently discard the user's wire length, and nothing but a
linter finds that.

`tools/extract.mjs` pulls the `<script type="text/babel">` body into a
gitignored `.check/` directory, padded so a diagnostic's line number
matches the HTML. `tsc` then checks it with `checkJs` and `strict`.
`docs/tools/extract.test.mjs` holds both extractors to that: the padding,
the purity guard, and that importing either one does not run it.

The check must pass before committing and before pushing. A `pre-push`
hook is in `githooks/`; enable it with
`git config core.hooksPath githooks`. It runs the check, the tests and
the browser tests, since pushing master deploys. CI runs the same, plus
`ruff` over `nec/`.

## Tests

`docs/tools/model.test.mjs` exercises the DOM-free half of
`random-wire.html` -- the band tables, the length arithmetic, the
impedance model and the formatters -- under `node --test`, with no test
framework beyond the one built into node.

```sh
npm --prefix docs/tools test
```

The page marks that half with `// BEGIN PURE` and `// END PURE`.
`tools/extract-model.mjs` pulls the region between them into a module and
appends an export list, so the tests run the shipped code rather than a
copy. Keep the region free of React, `window` and `document`: the
extractor scans it for those names, with comments stripped first, and
refuses to write a module that touches the DOM. Importing alone would
only catch a top-level reference, so a helper that read `document.title`
when called would have imported and tested cleanly.

## Browser tests

`docs/tools/browser/` drives the real page under Playwright, served the
way GitHub Pages serves it.

```sh
npm --prefix docs/tools run test:browser
npm --prefix docs/tools run serve      # to look by hand
```

It covers control wiring, the tuner verdicts, presets, unit and URL
round trips, phone-width layout, contrast, console cleanliness and
keyboard access.  CI runs it alongside the type check.
`docs/BROWSER_CHECKS.md` holds what is left for a human.

Two traps worth knowing before adding a test.  The option buttons carry
`role="radio"` and `aria-checked`, so `getByRole('button')` will not find
them.  And Playwright unescapes the pattern inside `:text-matches("...")`,
so a `\d` arrives as a literal `d`; pass a RegExp instead.

The type check proves the page compiles; it cannot prove the page
computes. It typed cleanly while the impedance mode drew half-wave
lengths at one velocity factor and scored against another. Both checks
must pass before committing and before pushing.

## Before Committing

0. **Type check**: `npm --prefix docs/tools run check` must pass clean.
1. **Tests**: `npm --prefix docs/tools test` and
   `npm --prefix docs/tools run test:browser`.
2. **Syntax check**: Verify the HTML is well-formed and all `<script>`
   blocks have valid JavaScript/JSX syntax.
3. **Style review**: No unused variables, no console.log left behind, no
   commented-out dead code.
4. **Math verification**: Pay special attention to complex number
   operations, impedance conversions, wavelength / frequency conversions
   and band edge data.
5. **Version and changelog**: a change a user would notice bumps
   `PAGE_VERSION` in `random-wire.html` -- the release date and a counter
   within it, `2026.08.28.001`, since master may deploy several times a
   day -- and adds the first `CHANGELOG` entry in the same commit, written
   for the user rather than as a commit message.  The footer's "what's
   new" dialog is the user's changelog; a test holds the two together.
   Internal changes bump nothing.

## Additional Guidelines

- **Preserve working state**: The page is a single file. A bad edit
  breaks everything. Be conservative with refactors.
- **Respect the single-file architecture**: Do not split the page into
  multiple files unless the user requests it. The single-file design is
  intentional for GitHub Pages simplicity.
- **External dependencies are loaded from CDN** (React, ReactDOM, Babel,
  and nec2c-wasm on demand for the NEC check).
- **Browser compatibility**: The page uses modern JS features transpiled
  by Babel. Ensure nothing relies on bleeding-edge APIs without checking
  browser support.
- **URL parameters**: The page encodes state in URL params. Ensure
  changes preserve backward-compatible URL parsing. When a parameter's
  unit changes, give the new unit a new key and keep reading the old
  one: the page writes `?len_m=` in meters and still accepts the older
  `?len=` in feet.
- **Accessibility**: Maintain readable contrast ratios in the dark
  theme. Ensure interactive controls are keyboard-accessible.
