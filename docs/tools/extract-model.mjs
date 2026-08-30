// Pull the DOM-free part of a single-file page out as an ES module, so the
// logic can be exercised from the command line and in CI.
//
// The type checker (extract.mjs) proves the code compiles; nothing proved it
// computes.  That gap let the impedance mode draw half-wave lengths at one
// velocity factor while scoring against another, which typed cleanly and was
// wrong on screen.
//
// The page marks its own boundary with BEGIN PURE and END PURE.  Everything
// between is free of React, window and document; the extracted module appends
// an export list so tests can reach it.  The extracted file is generated and
// gitignored; the shipped HTML is untouched.

import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

import { extractScript } from './extract.mjs';

const BEGIN = '// BEGIN PURE';
const END = '// END PURE';

/**
 * Names the tests import.  Explicit rather than inferred: an export list that
 * quietly tracks whatever the page happens to define would let a rename pass
 * unnoticed.
 */
const EXPORTS = [
  // constants
  'C_SPEED', 'FT_PER_M', 'PAGE_VERSION', 'CHANGELOG',
  'UNITS', 'SOILS', 'REGIONS', 'SEGMENTS', 'MODES',
  'MODEL_H_NODES', 'MODEL_COEFFS', 'MODEL_VF_A', 'MODEL_LENGTH_POWER',
  'lengthPower', 'WIRE_RADIUS_M', 'deckModel', 'NEC_AGREE_FACTOR', 'necSwrText',
  'DEFAULT_VELOCITY_FACTOR', 'DEFAULT_HEIGHT_M', 'DEFAULT_COUNTERPOISE_M',
  'DEFAULT_COUNTERPOISE_Z_M',
  'DEFAULT_BALUN_M',
  'GEOMETRIES',
  'DEFAULT_GEOMETRY',
  'returnConductorM',
  'feedHeightM',
  'riseShortfallM',
  'counterpoiseCeilingM',
  'withSiteInvariants',
  'MIN_RETURN_M',
  'RETURN_DIRECTION',
  'SLOPER_REACH_MARGIN',
  'DEFAULT_SOIL', 'DEFAULT_UNUN_RATIO', 'UNUN_RATIOS', 'Z_SYSTEM_OHMS',
  'WIRES', 'DEFAULT_WIRE', 'wireOf',
  'PUBLISHED_FT', 'TUNERS', 'DEFAULT_TUNER', 'isGoodScore',
  'HEIGHT_RANGE_M', 'COUNTERPOISE_RANGE_M',
  'COUNTERPOISE_Z_RANGE_M',
  'BALUN_RANGE_M', 'MODEL_FIT_RANGE_HZ',
  'MODEL_TYPICAL_FACTOR', 'MODEL_BOUND_FACTOR',
  // length math
  'halfWaveM', 'bandsIn', 'bandEdgesHz', 'resonanceInterval', 'avoidIntervals',
  'tooShortM', 'solve', 'judgeLength',
  // impedance model
  'wireZ0', 'interpCoeff',
  'interpCoeff2',
  'MODEL_Z_NODES', 'MODEL_DOMAIN', 'outOfDomainBands', 'lineZ', 'endFedZin', 'swrAtRadio', 'scoreLength',
  'solveImpedance', 'worstSuggestedSwr',
  // NEC deck
  'deckWires', 'deckSegments',
  'DECK_MAX_SEGMENTS', 'DECK_SEGMENTS_PER_WAVELENGTH',
  // in-page NEC check
  'NEC_LENGTH_SAMPLES', 'NEC2_FEED_MIN_LAMBDA', 'SWR_SAMPLES_PER_BAND',
  'necSuspectBands',
  'necSampleFreqsHz', 'buildProbeDeck', 'parseNecZ', 'geometricMeanSwr',
  'refineGapsM', 'necCheckFreqs', 'measuredScore', 'medianOverlayRatio',
  'bandSweep', 'BAND_SWEEP_POINTS', 'waveMaximaM',
  'parseNecProfile', 'envelopeProfile', 'profileFloor', 'PROFILE_POINTS',
  'necOverlayKey',
  // display
  'toDisplay', 'fromDisplay', 'fmtLen', 'fmtBandEdges', 'tickStep',
  // URL and state helpers
  'clamp', 'parseNum', 'isKeyOf', 'entriesOf', 'readWireLenM',
  'readCounterpoiseM',
  'LEGACY_RETURN_KEY',
  'URL_KEYS', 'DEFAULTS', 'LEGACY_LEN_FT_KEY',
  // classical internals worth exercising directly
  'mapSpanM',
  'pickInSpan', 'mergeIntervals', 'usableIntervals', 'bestFeasibleMargin',
  'nearestClearLength', 'PICK_STEPS', 'MARGIN_PCT_RANGE',
  'roundToUnit',
  'DEFAULT_MARGIN_PCT',
];

/**
 * Identifiers that make a region not pure.  Checked as whole words, so
 * `documentation` in a comment is fine and `document.title` is not.
 *
 * The list covers the ways back to a global as well as the globals
 * themselves: `globalThis['docu' + 'ment']` is not caught by any word list,
 * but reaching for globalThis at all is.  `top` and `open` are deliberately
 * absent, being MAP.top and prose about a wire open at the far end.
 */
const DOM_NAMES = new RegExp(String.raw`\b(?:${[
  'window', 'document', 'React', 'ReactDOM', 'navigator', 'localStorage',
  'sessionStorage', 'globalThis', 'self', 'parent', 'frames', 'location',
  'history', 'fetch', 'matchMedia', 'alert', 'confirm', 'prompt',
  'requestAnimationFrame', 'XMLHttpRequest', 'WebSocket', 'Image',
  'performance', 'postMessage',
].join('|')})\b`);

/**
 * Blank out comments and string bodies, keeping every newline so line numbers
 * survive.  Regexes cannot do this: a `'https://...'` hides the rest of its
 * line from a comment stripper, and a string holding `/*` swallows to the
 * next close.  Both are in the page today, which is how a DOM name could have
 * hidden in plain sight.
 *
 * @param {string} region
 * @returns {string}
 */
function blankLiterals(region) {
  let out = '';
  let i = 0;
  /** @type {null | '//' | '/*' | '"' | "'" | '`'} */
  let mode = null;
  while (i < region.length) {
    const c = region[i];
    const next = region[i + 1];
    if (mode === null) {
      if (c === '/' && next === '/') { mode = '//'; out += '  '; i += 2; continue; }
      if (c === '/' && next === '*') { mode = '/*'; out += '  '; i += 2; continue; }
      if (c === '"' || c === "'" || c === '`') { mode = c; out += ' '; i += 1; continue; }
      out += c; i += 1; continue;
    }
    if (mode === '//') {
      if (c === '\n') { mode = null; out += c; } else { out += ' '; }
      i += 1; continue;
    }
    if (mode === '/*') {
      if (c === '*' && next === '/') { mode = null; out += '  '; i += 2; continue; }
      out += c === '\n' ? c : ' '; i += 1; continue;
    }
    // Inside a string: a backslash escapes whatever follows, including the
    // quote that would otherwise end it.
    if (c === '\\') { out += '  '; i += 2; continue; }
    if (c === mode) { mode = null; out += ' '; i += 1; continue; }
    out += c === '\n' ? c : ' '; i += 1;
  }
  return out;
}

/**
 * Throw if the extracted region touches the DOM.
 *
 * Importing the module only fails on *top-level* DOM access, so a helper
 * that reads `document.title` when called would import and test cleanly
 * while making the marker a lie.  This is what makes "keep the region free
 * of React, window and document" an enforced rule rather than a request.
 *
 * @param {string} region
 */
export function assertPure(region) {
  // Comments and strings go first, in place, so line numbers survive: prose
  // says "document" often and means nothing by it.
  const code = blankLiterals(region);
  const offenders = code
    .split('\n')
    .map((line, i) => [i + 1, line])
    .filter(([, line]) => DOM_NAMES.test(line));
  if (offenders.length > 0) {
    const lines = region.split('\n');
    const shown = offenders.slice(0, 5)
      .map(([n]) => `  line ${n}: ${lines[n - 1].trim()}`).join('\n');
    throw new Error(
      `the PURE region touches the DOM, so the tests cannot run it:\n${shown}`);
  }
}

/**
 * @param {string} body  the full script body
 * @returns {string} the marked region
 */
export function pureRegion(body) {
  const start = body.indexOf(BEGIN);
  const end = body.indexOf(END);
  if (start === -1 || end === -1) {
    throw new Error(`page is missing ${BEGIN} / ${END} markers`);
  }
  if (end < start) throw new Error(`${END} precedes ${BEGIN}`);
  return body.slice(start + BEGIN.length, end);
}

// Only when run as a command, so a test can import assertPure without the
// extraction running underneath it.
const invokedAs = process.argv[1] ? pathToFileURL(process.argv[1]).href : null;
if (import.meta.url === invokedAs) {
  const [source, target] = process.argv.slice(2);
  if (!source || !target) {
    console.error('usage: extract-model.mjs <page.html> <out.mjs>');
    process.exit(2);
  }

  const html = await readFile(resolve(source), 'utf8');
  const { body } = extractScript(html);
  const region = pureRegion(body);
  // Checked before the file is written, so a region that touches the DOM
  // leaves the previous module in place rather than a page-sized wreck.
  assertPure(region);
  await mkdir(dirname(resolve(target)), { recursive: true });
  await writeFile(resolve(target), `${region}\nexport { ${EXPORTS.join(', ')} };\n`);
}
