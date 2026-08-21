// Tests for the DOM-free half of random-wire.html.
//
// Run with `npm test` in docs/tools.  The module under test is extracted from
// the page itself, so these exercise the shipped code rather than a copy.

import test from 'node:test';
import assert from 'node:assert/strict';

import * as m from './.check/model.mjs';

const close = (actual, expected, tolerance, what) =>
  assert.ok(Math.abs(actual - expected) <= tolerance,
    `${what}: got ${actual}, expected ${expected} +/- ${tolerance}`);

test('half wave reproduces the 468 / f(MHz) rule at vf 0.95', () => {
  for (const mhz of [3.75, 7.15, 14.175, 28.85]) {
    const feet = m.halfWaveM(mhz * 1e6, 0.95) * m.FT_PER_M;
    close(feet, 468 / mhz, 0.5, `468/f at ${mhz} MHz`);
  }
});

test('feet per meter is the international foot', () => {
  close(m.FT_PER_M, 1 / 0.3048, 1e-12, 'FT_PER_M');
});

test('display units convert against their definitions', () => {
  // Against the definition of the international foot, not against itself:
  // a round trip through a scale factor cannot fail.
  close(m.toDisplay(0.3048, 'ft'), 1, 1e-12, '0.3048 m is one foot');
  close(m.toDisplay(1, 'm'), 1, 1e-12, 'meters are the internal unit');
  close(m.fromDisplay(100, 'ft'), 30.48, 1e-12, '100 ft is 30.48 m');
});

test('a matched load is 1:1 through any transformer', () => {
  for (const ratio of m.UNUN_RATIOS) {
    const swr = m.swrAtRadio({ re: m.Z_SYSTEM_OHMS * ratio, im: 0 }, ratio);
    close(swr, 1, 1e-9, `${ratio}:1 into ${m.Z_SYSTEM_OHMS * ratio} ohms`);
  }
});

test('SWR is symmetric in impedance ratio', () => {
  const high = m.swrAtRadio({ re: m.Z_SYSTEM_OHMS * 4, im: 0 }, 1);
  const low = m.swrAtRadio({ re: m.Z_SYSTEM_OHMS / 4, im: 0 }, 1);
  close(high, low, 1e-9, '4x above and below 50 ohms');
  close(high, 4, 1e-9, 'a 4x mismatch is 4:1');
});

test('coefficient table is well formed', () => {
  // Generated into the page, so a short or misaligned row would interpolate
  // silently against the wrong node.  Stored sparsely: the two antenna-line
  // coefficients are one row along h/lambda, the three return-line ones a
  // row per node pair, because only they vary with counterpoise height.
  const ONE_D = ['alphaA', 'kA'];
  const TWO_D = ['alphaR', 'vfR', 'kR'];
  for (const [geometry, soils] of Object.entries(m.MODEL_COEFFS)) {
    assert.ok(geometry in m.GEOMETRIES, `${geometry} is a known geometry`);
    for (const soil of Object.keys(m.SOILS)) {
      assert.ok(soil in soils, `${geometry}.${soil} has coefficients`);
    }
    for (const [soil, coeffs] of Object.entries(soils)) {
      assert.ok(soil in m.SOILS, `${soil} is a known soil`);
      for (const name of ONE_D) {
        const values = coeffs[name];
        assert.equal(values.length, m.MODEL_H_NODES.length,
          `${geometry}.${soil}.${name} has one value per height node`);
        assert.ok(values.every(Number.isFinite),
          `${geometry}.${soil}.${name} is all finite`);
      }
      for (const name of TWO_D) {
        const rows = coeffs[name];
        assert.equal(rows.length, m.MODEL_H_NODES.length,
          `${geometry}.${soil}.${name} has one row per height node`);
        for (const row of rows) {
          assert.equal(row.length, m.MODEL_Z_NODES.length,
            `${geometry}.${soil}.${name} has one column per counterpoise node`);
          assert.ok(row.every(Number.isFinite),
            `${geometry}.${soil}.${name} is all finite`);
        }
      }
    }
  }
  for (const geometry of Object.keys(m.GEOMETRIES)) {
    assert.ok(geometry in m.MODEL_COEFFS, `${geometry} has coefficients`);
  }
  for (const nodes of [m.MODEL_H_NODES, m.MODEL_Z_NODES]) {
    assert.ok(nodes.every((v, i) => i === 0 || v > nodes[i - 1]),
      'nodes ascend, as the interpolation assumes');
  }
});

test('coefficients interpolate between nodes and clamp outside them', () => {
  const values = m.MODEL_H_NODES.map((_, i) => i);
  const last = m.MODEL_H_NODES.length - 1;
  close(m.interpCoeff(values, m.MODEL_H_NODES[0] / 10), 0, 1e-12, 'below the range');
  close(m.interpCoeff(values, m.MODEL_H_NODES[last] * 10), last, 1e-12,
    'above the range');
  for (let i = 0; i <= last; i++) {
    close(m.interpCoeff(values, m.MODEL_H_NODES[i]), i, 1e-9, `on node ${i}`);
  }
  // Interpolation is linear in log10, so the geometric midpoint is the
  // arithmetic midpoint of the values either side.
  const mid = Math.sqrt(m.MODEL_H_NODES[0] * m.MODEL_H_NODES[1]);
  close(m.interpCoeff(values, mid), 0.5, 1e-9, 'geometric midpoint');
});

test('feedpoint impedance peaks where the model puts its half wave', () => {
  // The regression behind the displayVf bug: the impedance model runs its
  // antenna line at MODEL_VF_A, so its peaks sit there and not at the
  // classical 0.95.  Drawing half waves at the wrong one put the table 5
  // percent away from the curve.
  const site = { geometry: 'flatTop', heightM: 9.144, balunM: m.DEFAULT_BALUN_M, counterpoiseM: 7.62, counterpoiseZM: m.DEFAULT_COUNTERPOISE_Z_M, soil: 'average' };
  const freqHz = 14.175e6;
  const expected = m.halfWaveM(freqHz, m.MODEL_VF_A);
  let bestLen = 0;
  let bestMag = -Infinity;
  for (let lenM = expected * 0.8; lenM <= expected * 1.2; lenM += 0.005) {
    const z = m.endFedZin(lenM, freqHz, site, m.WIRE_RADIUS_M);
    const mag = Math.hypot(z.re, z.im);
    if (mag > bestMag) { bestMag = mag; bestLen = lenM; }
  }
  close(bestLen / expected, 1, 0.03, 'peak sits within 3 percent of lambda/2');
  const classical = m.halfWaveM(freqHz, m.DEFAULT_VELOCITY_FACTOR);
  assert.ok(Math.abs(bestLen - classical) > Math.abs(bestLen - expected),
    'peak is nearer the model half wave than the classical one');
  assert.ok(bestMag > 1000, 'a half wave is a high-impedance point');
});

test('a quarter wave is not a high-impedance point', () => {
  const site = { geometry: 'flatTop', heightM: 9.144, balunM: m.DEFAULT_BALUN_M, counterpoiseM: 7.62, counterpoiseZM: m.DEFAULT_COUNTERPOISE_Z_M, soil: 'average' };
  const freqHz = 14.175e6;
  const quarter = m.halfWaveM(freqHz, m.MODEL_VF_A) / 2;
  const z = m.endFedZin(quarter, freqHz, site, m.WIRE_RADIUS_M);
  assert.ok(Math.hypot(z.re, z.im) < 1000, 'quarter wave stays below a kilohm');
});

test('raising the wire changes the answer', () => {
  // Height was unmodeled before the fit; a model that ignores it would
  // return the same impedance twice.
  const freqHz = 7.15e6;
  const lenM = 21.6;
  const low = m.endFedZin(lenM, freqHz,
    { geometry: 'flatTop', heightM: 3, balunM: m.DEFAULT_BALUN_M, counterpoiseM: 7.62, counterpoiseZM: m.DEFAULT_COUNTERPOISE_Z_M, soil: 'average' }, m.WIRE_RADIUS_M);
  const high = m.endFedZin(lenM, freqHz,
    { geometry: 'flatTop', heightM: 20, balunM: m.DEFAULT_BALUN_M, counterpoiseM: 7.62, counterpoiseZM: m.DEFAULT_COUNTERPOISE_Z_M, soil: 'average' }, m.WIRE_RADIUS_M);
  assert.ok(Math.abs(Math.hypot(low.re, low.im) - Math.hypot(high.re, high.im)) > 1,
    'height moves the feedpoint');
});

test('suggested lengths are ordered, distinct and long enough', () => {
  const site = { geometry: 'flatTop', balunM: m.DEFAULT_BALUN_M, counterpoiseZM: m.DEFAULT_COUNTERPOISE_Z_M, heightM: m.DEFAULT_HEIGHT_M, counterpoiseM: m.DEFAULT_COUNTERPOISE_M,
    soil: m.DEFAULT_SOIL };
  const out = m.solveImpedance('us', [80, 40, 20, 15, 10], 'full', site,
    m.WIRE_RADIUS_M, 9, 60, 'ft');
  assert.ok(out.suggestions.length > 0, 'something is suggested');
  for (let i = 1; i < out.suggestions.length; i++) {
    assert.ok(out.suggestions[i].swr >= out.suggestions[i - 1].swr,
      'suggestions are best first');
  }
  for (const s of out.suggestions) {
    assert.ok(s.lenM >= out.shortLimit, 'no suggestion below the short limit');
    assert.ok(Number.isFinite(s.swr) && s.swr >= 1, 'SWR is a real ratio');
  }
});

test('no bands selected yields no suggestions rather than throwing', () => {
  const site = { geometry: 'flatTop', balunM: m.DEFAULT_BALUN_M, counterpoiseZM: m.DEFAULT_COUNTERPOISE_Z_M, heightM: m.DEFAULT_HEIGHT_M, counterpoiseM: m.DEFAULT_COUNTERPOISE_M,
    soil: m.DEFAULT_SOIL };
  const out = m.solveImpedance('us', [], 'full', site, m.WIRE_RADIUS_M, 9, 30,
    'ft');
  assert.deepEqual(out.suggestions, []);
  assert.deepEqual(out.curve, []);
});

test('the classical rule keeps its stated clearance', () => {
  const marginPct = 8;
  const out = m.solve('us', [40], 'full', 0.95, marginPct, 60, 'ft');
  for (const span of out.suggestions) {
    for (const zone of out.merged) {
      const inside = span.pick > zone.lo && span.pick < zone.hi;
      assert.ok(!inside, `pick ${span.pick} avoids ${zone.lo}-${zone.hi}`);
    }
  }
});

// ---------------------------------------------------------------------------
// Band plans and segments
// ---------------------------------------------------------------------------

test('every region has bands, and every band a sane edge pair', () => {
  for (const region of Object.keys(m.REGIONS)) {
    const bands = m.bandsIn(region);
    assert.ok(bands.length > 0, `${region} has bands`);
    for (const band of bands) {
      for (const segment of Object.keys(m.SEGMENTS)) {
        const [lo, hi] = m.bandEdgesHz(band, segment);
        assert.ok(lo > 0 && hi > lo, `${region} ${band.m}m ${segment}: ${lo}-${hi}`);
        assert.ok(hi / lo < 1.2, `${region} ${band.m}m ${segment} spans < 20 percent`);
      }
    }
  }
});

test('band meters and frequency agree', () => {
  // A band labeled 40 m should sit near 300/40 = 7.5 MHz.  Catches a row
  // typed into the wrong place in the band table.
  for (const region of Object.keys(m.REGIONS)) {
    for (const band of m.bandsIn(region)) {
      const [lo, hi] = m.bandEdgesHz(band, 'full');
      const centerM = m.C_SPEED / ((lo + hi) / 2);
      close(centerM / band.m, 1, 0.15, `${region} ${band.m}m center wavelength`);
    }
  }
});

test('a sub-band lies inside the full band', () => {
  for (const region of Object.keys(m.REGIONS)) {
    for (const band of m.bandsIn(region)) {
      const [fullLo, fullHi] = m.bandEdgesHz(band, 'full');
      for (const segment of Object.keys(m.SEGMENTS)) {
        const [lo, hi] = m.bandEdgesHz(band, segment);
        assert.ok(lo >= fullLo && hi <= fullHi,
          `${region} ${band.m}m ${segment} within the full band`);
      }
    }
  }
});

// ---------------------------------------------------------------------------
// Length math
// ---------------------------------------------------------------------------

test('half wave scales inversely with frequency and with velocity factor', () => {
  close(m.halfWaveM(7e6, 1) / m.halfWaveM(14e6, 1), 2, 1e-9, 'halving frequency');
  close(m.halfWaveM(7e6, 0.5) / m.halfWaveM(7e6, 1), 0.5, 1e-9, 'halving vf');
});

test('a resonance interval brackets the half wave it is built from', () => {
  const band = m.bandsIn('us').find(b => b.m === 40);
  const [lo, hi] = m.bandEdgesHz(band, 'full');
  const interval = m.resonanceInterval(band, 'full', 0.95, 0.08, 1);
  assert.ok(interval.lo < m.halfWaveM(hi, 0.95), 'reaches below the shortest');
  assert.ok(interval.hi > m.halfWaveM(lo, 0.95), 'reaches above the longest');
  assert.ok(interval.lo < interval.hi, 'ordered');
});

test('a wider margin never narrows a keep-out zone', () => {
  const band = m.bandsIn('us').find(b => b.m === 20);
  let previous = null;
  for (const margin of [0, 0.02, 0.05, 0.1, 0.15]) {
    const interval = m.resonanceInterval(band, 'full', 0.95, margin, 1);
    if (previous) {
      assert.ok(interval.lo <= previous.lo, 'low edge moves down or holds');
      assert.ok(interval.hi >= previous.hi, 'high edge moves up or holds');
    }
    previous = interval;
  }
});

test('each avoid zone delivers the clearance it promises', () => {
  // avoidIntervals returns one zone per band per multiple; overlap between
  // bands is expected here and resolved by solve().
  const bands = m.bandsIn('us').filter(b => [40, 20, 15].includes(b.m));
  // The property worth asserting is the clearance itself: each zone must
  // reach at least marginPct of a half wave either side of the resonance it
  // guards, which is the whole claim the classical mode makes.
  const marginPct = 8;
  for (const band of bands) {
    const [loHz, hiHz] = m.bandEdgesHz(band, 'full');
    const shortest = m.halfWaveM(hiHz, 0.95);
    const longest = m.halfWaveM(loHz, 0.95);
    for (let n = 1; n * shortest <= 60; n++) {
      const zone = m.resonanceInterval(band, 'full', 0.95, marginPct / 100, n);
      assert.ok(zone.lo <= (n - marginPct / 100) * shortest + 1e-9,
        `${band.label} n=${n}: low edge clears by the stated margin`);
      assert.ok(zone.hi >= (n + marginPct / 100) * longest - 1e-9,
        `${band.label} n=${n}: high edge clears by the stated margin`);
    }
  }
});

test('solve merges the avoid zones into disjoint ones', () => {
  const out = m.solve('us', [40, 20, 15], 'full', 0.95, 8, 60, 'ft');
  for (let i = 1; i < out.merged.length; i++) {
    assert.ok(out.merged[i].lo > out.merged[i - 1].hi,
      'merged zones are disjoint and ascending');
  }
  for (const zone of out.merged) {
    assert.ok(zone.lo < zone.hi, 'merged zone is ordered');
  }
});

test('usable spans clear every avoid zone', () => {
  const out = m.solve('us', [40, 20], 'full', 0.95, 8, 60, 'ft');
  for (const span of out.usable) {
    for (const zone of out.merged) {
      const overlaps = span.lo < zone.hi && zone.lo < span.hi;
      assert.ok(!overlaps, `usable ${span.lo}-${span.hi} clears ${zone.lo}-${zone.hi}`);
    }
  }
});

test('the short limit is a quarter wave at the lowest band', () => {
  const bands = m.bandsIn('us').filter(b => [80, 40, 20].includes(b.m));
  const limit = m.tooShortM(bands, 'full', 0.95);
  const lowest = Math.min(...bands.map(b => m.bandEdgesHz(b, 'full')[0]));
  close(limit, m.halfWaveM(lowest, 0.95) / 2, 1e-9, 'quarter wave on 80 m');
});

// ---------------------------------------------------------------------------
// Impedance model
// ---------------------------------------------------------------------------

test('Schelkunoff Z0 rises with length and falls with radius', () => {
  assert.ok(m.wireZ0(40, 8.14e-4) > m.wireZ0(20, 8.14e-4), 'longer is higher');
  assert.ok(m.wireZ0(20, 1.6e-3) < m.wireZ0(20, 8.14e-4), 'fatter is lower');
  // 60 (ln(2l/a) - 1) at l = 20 m, a = 0.814 mm.
  close(m.wireZ0(20, 8.14e-4), 60 * (Math.log(2 * 20 / 8.14e-4) - 1), 1e-9,
    'matches the closed form');
});

test('feedpoint impedance is finite and positive-real everywhere sampled', () => {
  const site = { geometry: 'flatTop', heightM: 9.144, balunM: m.DEFAULT_BALUN_M, counterpoiseM: 7.62, counterpoiseZM: m.DEFAULT_COUNTERPOISE_Z_M, soil: 'average' };
  for (const mhz of [1.9, 3.75, 7.15, 14.175, 21.225, 28.85]) {
    for (let lenM = 2; lenM <= 60; lenM += 0.5) {
      const z = m.endFedZin(lenM, mhz * 1e6, site, m.WIRE_RADIUS_M);
      assert.ok(Number.isFinite(z.re) && Number.isFinite(z.im),
        `finite at ${lenM} m, ${mhz} MHz`);
      assert.ok(z.re > 0, `resistive part positive at ${lenM} m, ${mhz} MHz`);
    }
  }
});

test('every soil produces a usable model', () => {
  const freqHz = 14.175e6;
  for (const soil of Object.keys(m.SOILS)) {
    const z = m.endFedZin(20, freqHz, { geometry: 'flatTop', heightM: 9.144, balunM: m.DEFAULT_BALUN_M, counterpoiseM: 7.62, counterpoiseZM: m.DEFAULT_COUNTERPOISE_Z_M, soil },
      m.WIRE_RADIUS_M);
    assert.ok(Number.isFinite(z.re) && z.re > 0, `${soil} gives a real impedance`);
  }
});

test('SWR matches the closed form either side of a match', () => {
  // Values chosen against the closed form rather than against the code: a
  // load n times the system impedance is n:1, either side of the match.
  for (const [ohms, ratio, want] of [[450, 9, 1], [1800, 9, 4], [112.5, 9, 4],
                                     [2450, 49, 1], [50, 1, 1], [200, 1, 4]]) {
    close(m.swrAtRadio({ re: ohms, im: 0 }, ratio), want, 1e-9,
      `${ohms} ohms through ${ratio}:1`);
  }
  const matched = m.swrAtRadio({ re: 450, im: 0 }, 9);
  const reactive = m.swrAtRadio({ re: 450, im: 450 }, 9);
  assert.ok(reactive > matched, 'reactance makes the match worse');
});

test('scoring a length returns a mean bounded by its own worst case', () => {
  const site = { geometry: 'flatTop', heightM: 9.144, balunM: m.DEFAULT_BALUN_M, counterpoiseM: 7.62, counterpoiseZM: m.DEFAULT_COUNTERPOISE_Z_M, soil: 'average' };
  const bands = m.bandsIn('us').filter(b => [40, 20, 10].includes(b.m));
  const scored = m.scoreLength(21.6, bands, 'full', site, m.WIRE_RADIUS_M, 9);
  assert.ok(scored !== null, 'a score comes back');
  assert.ok(scored.swr >= 1, 'geometric mean is a ratio');
  assert.ok(bands.some(b => b.m === scored.worst.band.m),
    'the worst band is one that was asked for');
});

test('a longer return path changes the score', () => {
  // Finding 4: the return resonates in its own right.  A model that treated
  // it as a passive ground would return the same number twice.
  const bands = m.bandsIn('us').filter(b => [40, 20].includes(b.m));
  const short = m.scoreLength(21.6, bands, 'full',
    { geometry: 'flatTop', heightM: 9.144, balunM: m.DEFAULT_BALUN_M, counterpoiseM: 3, counterpoiseZM: m.DEFAULT_COUNTERPOISE_Z_M, soil: 'average' }, m.WIRE_RADIUS_M, 9);
  const long = m.scoreLength(21.6, bands, 'full',
    { geometry: 'flatTop', heightM: 9.144, balunM: m.DEFAULT_BALUN_M, counterpoiseM: 30, counterpoiseZM: m.DEFAULT_COUNTERPOISE_Z_M, soil: 'average' }, m.WIRE_RADIUS_M, 9);
  assert.ok(Math.abs(short.swr - long.swr) > 0.01, 'return length matters');
});

test('the transformer ratio moves the match', () => {
  const z = { re: 450, im: 0 };
  close(m.swrAtRadio(z, 9), 1, 1e-9, '450 ohms through 9:1');
  assert.ok(m.swrAtRadio(z, 1) > 8, '450 ohms direct is a poor match');
  assert.ok(m.swrAtRadio({ re: 2450, im: 0 }, 49) < 1.1, '2450 through 49:1');
});

// ---------------------------------------------------------------------------
// Formatting
// ---------------------------------------------------------------------------

test('lengths format in the unit asked for', () => {
  assert.match(m.fmtLen(30.48, 'ft'), /100/, '30.48 m is 100 ft');
  assert.match(m.fmtLen(30.48, 'm'), /30/, '30.48 m reads as meters');
  assert.match(m.fmtLen(30.48, 'ftin'), /100/, 'ft + in still leads with feet');
});

test('feet and inches never shows twelve inches', () => {
  for (let cm = 0; cm < 400; cm += 1) {
    const text = m.fmtLen(cm / 100, 'ftin');
    const inches = text.match(/([\d.]+)\s*in/);
    if (inches) {
      assert.ok(Number(inches[1]) < 12, `${text} carries into feet`);
    }
  }
});

// ---------------------------------------------------------------------------
// The page against the fit it came from
// ---------------------------------------------------------------------------

test('inlined coefficients match the fitted table they were generated from', async () => {
  // The page must stay self-contained, so its coefficients are inlined rather
  // than imported.  nec/coefficients2d.json is the original, and
  // this is what stops the two drifting: regenerate with
  // `uv run coefficients2d.py --write-page` and both move together.
  const { readFile } = await import('node:fs/promises');
  const url = new URL('../../nec/coefficients2d.json', import.meta.url);
  const data = JSON.parse(await readFile(url, 'utf8'));

  assert.deepEqual([...m.MODEL_H_NODES], data.h_nodes, 'height nodes agree');
  assert.deepEqual([...m.MODEL_Z_NODES], data.z_nodes, 'counterpoise nodes agree');
  close(m.MODEL_VF_A, data.vf_a, 1e-12, 'antenna velocity factor');

  // The json carries a dense (soil, height, counterpoise, parameter) array;
  // the page stores the two antenna coefficients once, since they do not
  // vary along the counterpoise axis.
  const JS = { alpha_a_lam: 'alphaA', ka: 'kA', alpha_r_lam: 'alphaR',
               vf_r: 'vfR', kr: 'kR' };
  const round = (v) => Math.round(v * 1e4) / 1e4;
  for (const [key, geometry] of [['flat_top', 'flatTop'], ['sloper', 'sloper']]) {
    const table = data[key].table;
    data.soils.forEach((soil, si) => {
      data.params.forEach((param, pi) => {
        const name = JS[param];
        const inlined = m.MODEL_COEFFS[geometry][soil][name];
        if (data.two_d_params.includes(param)) {
          table[si].forEach((row, ni) => {
            assert.deepEqual([...inlined[ni]], row.map((cell) => round(cell[pi])),
              `${geometry}.${soil}.${name} row ${ni} matches the fit`);
          });
          return;
        }
        assert.deepEqual([...inlined],
          table[si].map((row) => round(row[0][pi])),
          `${geometry}.${soil}.${name} matches the fit`);
      });
    });
  }
});

test('the fitted coefficients are physically plausible', () => {
  // Loss cannot be negative, a velocity factor above one is a wave outrunning
  // light, and a Z0 scale far from unity means the line form has stopped
  // describing a wire.  A bad sweep point reaching the fit shows up here.
  for (const [geometry, soils] of Object.entries(m.MODEL_COEFFS)) {
    for (const [soil, coeffs] of Object.entries(soils)) {
      const where = `${geometry}.${soil}`;
      for (const alpha of [...coeffs.alphaA, ...coeffs.alphaR.flat()]) {
        assert.ok(alpha > 0 && alpha < 5, `${where}: alpha ${alpha} in range`);
      }
      for (const vf of coeffs.vfR.flat()) {
        assert.ok(vf > 0.3 && vf <= 1.0001, `${where}: vf_r ${vf} at or below unity`);
      }
      for (const k of [...coeffs.kA, ...coeffs.kR.flat()]) {
        assert.ok(k > 0.2 && k < 2, `${where}: Z0 scale ${k} near unity`);
      }
    }
  }
});

// ---------------------------------------------------------------------------
// The two modes against each other
// ---------------------------------------------------------------------------
//
// The classical keep-out is a proxy: those lengths are bad because the
// feedpoint impedance spikes there.  The impedance mode drops the proxy and
// models the spike.  So the two should agree about where the bad lengths are,
// and where they disagree it should be for a reason that can be named.
//
// The comparison is made at MODEL_VF_A throughout.  The modes ship with
// different velocity factors, which offsets every zone by about 5 percent;
// that difference is a live decision recorded in TODO.md, and
// holding it fixed here is what lets these tests speak to anything else.

const AT_MODEL_VF = { region: 'us', segment: 'full', marginPct: 8 };

test('the classical avoid zones bracket the modeled impedance peaks', () => {
  const site = { geometry: 'flatTop', balunM: m.DEFAULT_BALUN_M, counterpoiseZM: m.DEFAULT_COUNTERPOISE_Z_M, heightM: m.DEFAULT_HEIGHT_M, counterpoiseM: m.DEFAULT_COUNTERPOISE_M,
    soil: m.DEFAULT_SOIL };
  const bandM = 20;
  const band = m.bandsIn(AT_MODEL_VF.region).find(b => b.m === bandM);
  const [loHz, hiHz] = m.bandEdgesHz(band, AT_MODEL_VF.segment);
  const midHz = (loHz + hiHz) / 2;

  const zones = m.avoidIntervals([band], AT_MODEL_VF.segment, m.MODEL_VF_A,
    AT_MODEL_VF.marginPct, 60);
  assert.ok(zones.length > 0, 'the rule marks something out');

  // Every peak the model draws should fall inside a zone the rule marks.
  const peaks = [];
  let previous = null;
  let rising = false;
  for (let lenM = 2; lenM <= 60; lenM += 0.02) {
    const z = m.endFedZin(lenM, midHz, site, m.WIRE_RADIUS_M);
    const mag = Math.hypot(z.re, z.im);
    if (previous !== null) {
      if (mag > previous) rising = true;
      else if (rising) { peaks.push(lenM - 0.02); rising = false; }
    }
    previous = mag;
  }
  assert.ok(peaks.length >= 3, `found ${peaks.length} peaks to check`);
  for (const peak of peaks) {
    const covered = zones.some(zone => peak >= zone.lo && peak <= zone.hi);
    assert.ok(covered, `peak at ${peak.toFixed(2)} m falls in an avoid zone`);
  }
});

test('lengths the classical rule rejects score worse than ones it accepts', () => {
  // The two methods are independent: one is arithmetic on wavelength, the
  // other a fitted impedance model.  If the proxy is sound they should rank
  // the same lengths the same way.
  const site = { geometry: 'flatTop', balunM: m.DEFAULT_BALUN_M, counterpoiseZM: m.DEFAULT_COUNTERPOISE_Z_M, heightM: m.DEFAULT_HEIGHT_M, counterpoiseM: m.DEFAULT_COUNTERPOISE_M,
    soil: m.DEFAULT_SOIL };
  const bandsM = [40, 20, 15];
  const bands = m.bandsIn(AT_MODEL_VF.region).filter(b => bandsM.includes(b.m));
  const zones = m.avoidIntervals(bands, AT_MODEL_VF.segment, m.MODEL_VF_A,
    AT_MODEL_VF.marginPct, 60);

  const inside = [];
  const outside = [];
  for (let lenM = 8; lenM <= 45; lenM += 0.25) {
    const scored = m.scoreLength(lenM, bands, AT_MODEL_VF.segment, site,
      m.WIRE_RADIUS_M, 9);
    const hit = zones.some(zone => lenM >= zone.lo && lenM <= zone.hi);
    (hit ? inside : outside).push(scored.swr);
  }
  assert.ok(inside.length > 5 && outside.length > 5, 'both sets are populated');

  const median = (xs) => [...xs].sort((a, b) => a - b)[Math.floor(xs.length / 2)];
  assert.ok(median(inside) > median(outside),
    `rejected lengths score worse: ${median(inside).toFixed(2)} ` +
    `against ${median(outside).toFixed(2)}`);
});

test('the two modes recommend lengths that are mutually acceptable', () => {
  // The strongest form: what one method offers, the other should not have
  // ruled out.  Checked on a band set where the classical rule still has room
  // to have an opinion -- see the saturation test below for why that
  // qualifier is needed rather than a way of ducking the comparison.
  const site = { geometry: 'flatTop', balunM: m.DEFAULT_BALUN_M, counterpoiseZM: m.DEFAULT_COUNTERPOISE_Z_M, heightM: m.DEFAULT_HEIGHT_M, counterpoiseM: m.DEFAULT_COUNTERPOISE_M,
    soil: m.DEFAULT_SOIL };
  const bandsM = [40, 20];
  const bands = m.bandsIn(AT_MODEL_VF.region).filter(b => bandsM.includes(b.m));
  const zones = m.avoidIntervals(bands, AT_MODEL_VF.segment, m.MODEL_VF_A,
    AT_MODEL_VF.marginPct, 60);

  const impedance = m.solveImpedance(AT_MODEL_VF.region, bandsM,
    AT_MODEL_VF.segment, site, m.WIRE_RADIUS_M, 9, 60, 'ft');
  assert.ok(impedance.suggestions.length > 0, 'the impedance mode offers something');
  for (const pick of impedance.suggestions) {
    const hit = zones.find(zone => pick.lenM >= zone.lo && pick.lenM <= zone.hi);
    assert.ok(hit === undefined,
      `impedance pick ${pick.lenM.toFixed(2)} m is not in a classical avoid zone`);
  }
});

test('the classical rule saturates once enough bands are asked for', () => {
  // Not a failure of either method, but the reason the mutual-acceptability
  // check above is qualified, and an argument for the impedance mode: with
  // four bands at the default margin the keep-out zones cover more than the
  // whole axis, so every length is in one and "avoid resonance" stops being
  // advice.  A continuous cost still ranks them; a binary rule cannot.
  const bands = m.bandsIn('us').filter(b => [40, 20, 15, 10].includes(b.m));
  const zones = m.avoidIntervals(bands, 'full', m.MODEL_VF_A, 8, 60);
  const covered = zones.reduce((sum, z) => sum + (z.hi - z.lo), 0);
  assert.ok(covered > 60, `zones cover ${covered.toFixed(1)} m of a 60 m axis`);

  const solved = m.solve('us', [40, 20, 15, 10], 'full', m.MODEL_VF_A, 8, 60, 'ft');
  const widest = Math.max(...solved.usable.map(u => u.hi - u.lo));
  assert.ok(widest < 5, `widest usable span is only ${widest.toFixed(2)} m`);

  // The impedance mode still returns a ranking over the same input.
  const site = { geometry: 'flatTop', balunM: m.DEFAULT_BALUN_M, counterpoiseZM: m.DEFAULT_COUNTERPOISE_Z_M, heightM: m.DEFAULT_HEIGHT_M, counterpoiseM: m.DEFAULT_COUNTERPOISE_M,
    soil: m.DEFAULT_SOIL };
  const scored = m.solveImpedance('us', [40, 20, 15, 10], 'full', site,
    m.WIRE_RADIUS_M, 9, 60, 'ft');
  assert.ok(scored.suggestions.length > 0,
    'the impedance mode still has an opinion where the rule has none');
});

test('the published lengths are scored rather than omitted', () => {
  // The page shows what it thinks of the standard tables, including where it
  // disagrees.  A user who knows 71 ft will otherwise read its absence from
  // the suggestions as a broken tool.
  const site = { geometry: 'flatTop', balunM: m.DEFAULT_BALUN_M, counterpoiseZM: m.DEFAULT_COUNTERPOISE_Z_M, heightM: m.DEFAULT_HEIGHT_M, counterpoiseM: m.DEFAULT_COUNTERPOISE_M,
    soil: m.DEFAULT_SOIL };
  const bands = m.bandsIn('us').filter(b => [80, 40, 20, 15, 10].includes(b.m));
  assert.ok(m.PUBLISHED_FT.includes(71), '71 ft is among the lengths shown');

  const scores = m.PUBLISHED_FT.map(ft => ({
    ft, swr: m.scoreLength(m.fromDisplay(ft, 'ft'), bands, 'full', site,
      m.WIRE_RADIUS_M, 9).swr,
  }));
  for (const { ft, swr } of scores) {
    assert.ok(Number.isFinite(swr) && swr >= 1, `${ft} ft scores a real SWR`);
  }
  // Mostly agreeing with the tables on the average is what makes the
  // disagreements worth reading; if this flips, the model has drifted rather
  // than dissented.  Judged against a fixed 5:1 rather than the default
  // tuner, so that changing which tuner the page opens on does not silently
  // change what this asserts.
  const AGREEMENT_SWR = 5;
  const passing = scores.filter(s => s.swr <= AGREEMENT_SWR).length;
  assert.ok(passing >= scores.length / 2,
    `${passing} of ${scores.length} published lengths pass on the mean`);
});

test('the worst-band gate is what separates the published lengths', () => {
  // The two agree on the average and part company on the worst band, and it
  // is 80 m that does it: a random wire is electrically short there and the
  // match is genuinely hard.  Recorded as a test because the default band set
  // includes 80 m, so this is what a first-time visitor sees.
  const site = { geometry: 'flatTop', balunM: m.DEFAULT_BALUN_M, counterpoiseZM: m.DEFAULT_COUNTERPOISE_Z_M, heightM: m.DEFAULT_HEIGHT_M, counterpoiseM: m.DEFAULT_COUNTERPOISE_M,
    soil: m.DEFAULT_SOIL };
  // Against a wide-range tuner, not the default: with a rig ATU almost
  // nothing passes either way and the comparison says nothing.
  const passing = (bandsM) => {
    const bands = m.bandsIn('us').filter(b => bandsM.includes(b.m));
    return m.PUBLISHED_FT.filter(ft => m.isGoodScore(
      m.scoreLength(m.fromDisplay(ft, 'ft'), bands, 'full', site,
        m.WIRE_RADIUS_M, 9), 'roller')).length;
  };
  const withEighty = passing([80, 40, 20, 15, 10]);
  const without = passing([40, 20, 15, 10]);
  assert.ok(without > withEighty,
    `dropping 80 m should help: ${withEighty} -> ${without}`);
});

test('every offered band lies inside the fitted frequency range', () => {
  // The impedance mode quotes an accuracy figure that only means anything
  // where the sweep has evidence.  Rather than warning at runtime about bands
  // outside it, the band tables are held inside it here: adding 6 m or 630 m
  // back means extending the sweep first, and this test is what says so.
  for (const region of Object.keys(m.REGIONS)) {
    for (const band of m.bandsIn(region)) {
      for (const segment of Object.keys(m.SEGMENTS)) {
        const [lo, hi] = m.bandEdgesHz(band, segment);
        assert.ok(lo >= m.MODEL_FIT_RANGE_HZ.min,
          `${region} ${band.label} ${segment} starts at ${lo} Hz, below the fit`);
        assert.ok(hi <= m.MODEL_FIT_RANGE_HZ.max,
          `${region} ${band.label} ${segment} ends at ${hi} Hz, above the fit`);
      }
    }
  }
});

test('impedance suggestions are round numbers whose score matches the length', () => {
  // A raw local minimum lands wherever the sample grid falls, so it is an
  // artefact of SCORE_SAMPLES rather than a length to cut wire to.  Each
  // suggestion must round in the display unit and carry the score of the
  // rounded length, not of the sample it came from.
  const site = { geometry: 'flatTop', balunM: m.DEFAULT_BALUN_M, counterpoiseZM: m.DEFAULT_COUNTERPOISE_Z_M, heightM: m.DEFAULT_HEIGHT_M, counterpoiseM: m.DEFAULT_COUNTERPOISE_M,
    soil: m.DEFAULT_SOIL };
  const bandsM = [40, 20, 15, 10];
  for (const units of Object.keys(m.UNITS)) {
    const out = m.solveImpedance('us', bandsM, 'full', site, m.WIRE_RADIUS_M,
      9, 60, units);
    assert.ok(out.suggestions.length > 0, `${units}: something is suggested`);
    const seen = new Set();
    for (const pick of out.suggestions) {
      const display = m.toDisplay(pick.lenM, units);
      close(display, Math.round(display * 100) / 100, 1e-9,
        `${units}: ${display} is round in the display unit`);
      assert.ok(!seen.has(pick.lenM), `${units}: no duplicate after rounding`);
      seen.add(pick.lenM);
      const rescored = m.scoreLength(pick.lenM, out.bands, 'full', site,
        m.WIRE_RADIUS_M, 9);
      close(pick.swr, rescored.swr, 1e-9,
        `${units}: the quoted SWR is the rounded length's own`);
    }
  }
});

// ---------------------------------------------------------------------------
// The classical verdict, which had no tests at all
// ---------------------------------------------------------------------------

/** The default site, spelled once. */
const SITE = { geometry: 'flatTop', balunM: m.DEFAULT_BALUN_M, counterpoiseZM: m.DEFAULT_COUNTERPOISE_Z_M, heightM: m.DEFAULT_HEIGHT_M, counterpoiseM: m.DEFAULT_COUNTERPOISE_M,
  soil: m.DEFAULT_SOIL };

test('judgeLength calls a length inside an avoid zone bad', () => {
  const bands = m.bandsIn('us').filter(b => b.m === 40);
  const zone = m.resonanceInterval(bands[0], 'full', 0.95, 0.08, 1);
  const middle = (zone.lo + zone.hi) / 2;
  const shortLimit = m.tooShortM(bands, 'full', 0.95);
  const verdict = m.judgeLength(middle, bands, 'full', 0.95, 8, shortLimit);
  assert.ok(verdict !== null, 'a length long enough gets a verdict');
  assert.equal(verdict.ok, false, 'the middle of a keep-out zone is not ok');
  assert.ok(verdict.hit !== null, 'and it names the zone it landed in');
  assert.ok(verdict.hit.lo <= middle && middle <= verdict.hit.hi,
    'the named zone actually contains the length');
});

test('judgeLength calls a length between zones good, and measures clearance', () => {
  const bands = m.bandsIn('us').filter(b => b.m === 40);
  const solved = m.solve('us', [40], 'full', 0.95, 8, 60, 'ft');
  const span = solved.usable.find(u => u.hi - u.lo > 1);
  assert.ok(span !== undefined, 'a usable span exists to test in');
  const middle = (span.lo + span.hi) / 2;
  const shortLimit = m.tooShortM(bands, 'full', 0.95);
  const verdict = m.judgeLength(middle, bands, 'full', 0.95, 8, shortLimit);
  assert.equal(verdict.ok, true, 'the middle of a usable span is ok');
  assert.equal(verdict.hit, null, 'nothing was hit');
  assert.ok(verdict.clearance > 0, 'clearance is positive');
  // The clearance must be the true distance to the nearest zone edge.
  const nearest = Math.min(...solved.merged.map(
    z => Math.min(Math.abs(middle - z.lo), Math.abs(middle - z.hi))));
  close(verdict.clearance, nearest, 1e-6, 'clearance is the real distance');
});

test('judgeLength explains a too-short wire rather than refusing one', () => {
  const bands = m.bandsIn('us').filter(b => b.m === 80);
  const shortLimit = m.tooShortM(bands, 'full', 0.95);
  const verdict = m.judgeLength(shortLimit * 0.5, bands, 'full', 0.95, 8,
    shortLimit);
  assert.ok(verdict !== null, 'a short wire still gets a verdict');
  assert.equal(verdict.ok, false, 'and it is not a good one');
  assert.equal(verdict.hit.kind, 'short',
    'the reason given is the length, not a resonance');
  // Only a nonsensical length gets nothing back.
  assert.equal(m.judgeLength(0, bands, 'full', 0.95, 8, shortLimit), null,
    'zero length has no verdict to give');
  assert.equal(m.judgeLength(-5, bands, 'full', 0.95, 8, shortLimit), null,
    'nor does a negative one');
});

test('a wider margin can only turn a good length bad, never the reverse', () => {
  // The zones only grow with the margin, so a length inside one at 5 percent
  // cannot be outside it at 12.  This is the monotonicity the whole rule
  // rests on, and it is what a sign error in resonanceInterval would break.
  const bands = m.bandsIn('us').filter(b => [40, 20].includes(b.m));
  const shortLimit = m.tooShortM(bands, 'full', 0.95);
  for (let lenM = 10; lenM < 50; lenM += 0.37) {
    let wasBad = false;
    for (const marginPct of [0, 2, 5, 8, 12, 15]) {
      const verdict = m.judgeLength(lenM, bands, 'full', 0.95, marginPct,
        shortLimit);
      if (verdict === null) continue;
      if (wasBad) {
        assert.equal(verdict.ok, false,
          `${lenM.toFixed(2)} m went bad then good again at ${marginPct}%`);
      }
      if (!verdict.ok) wasBad = true;
    }
  }
});

// ---------------------------------------------------------------------------
// Interval algebra and the pickers
// ---------------------------------------------------------------------------

test('mergeIntervals unions overlaps and leaves gaps alone', () => {
  const merged = m.mergeIntervals([
    { lo: 5, hi: 10 }, { lo: 8, hi: 12 }, { lo: 20, hi: 25 }, { lo: 1, hi: 3 },
  ]);
  assert.deepEqual(merged.map(i => [i.lo, i.hi]),
    [[1, 3], [5, 12], [20, 25]], 'sorted, unioned, gaps preserved');
});

test('mergeIntervals joins intervals that only touch', () => {
  const merged = m.mergeIntervals([{ lo: 0, hi: 5 }, { lo: 5, hi: 9 }]);
  assert.equal(merged.length, 1, 'abutting intervals are one');
});

test('usableIntervals is the complement of the merged zones', () => {
  const usable = m.usableIntervals([{ lo: 5, hi: 10 }, { lo: 20, hi: 25 }], 30);
  for (const span of usable) {
    assert.ok(span.lo < span.hi, 'each span is ordered');
    for (const zone of [{ lo: 5, hi: 10 }, { lo: 20, hi: 25 }]) {
      assert.ok(!(span.lo < zone.hi && zone.lo < span.hi),
        `${span.lo}-${span.hi} does not overlap ${zone.lo}-${zone.hi}`);
    }
  }
  // Coverage, which the old test never checked: every point not in a zone
  // has to be in a span.
  for (const probe of [1, 4.9, 12, 19, 26, 29.9]) {
    assert.ok(usable.some(s => probe >= s.lo && probe <= s.hi),
      `${probe} is covered`);
  }
});

test('pickInSpan returns a round number strictly inside the span', () => {
  for (const span of [{ lo: 10, hi: 20 }, { lo: 10.02, hi: 10.06 },
                      { lo: 0.5, hi: 0.51 }]) {
    for (const units of Object.keys(m.UNITS)) {
      const pick = m.pickInSpan(span, units);
      assert.ok(pick > span.lo && pick < span.hi,
        `${units}: ${pick} is inside ${span.lo}-${span.hi}`);
    }
  }
});

test('pickInSpan prefers the roundest number that fits', () => {
  // A wide span should give a whole number of feet, not a fractional one.
  const pick = m.toDisplay(m.pickInSpan({ lo: 10, hi: 20 }, 'ft'), 'ft');
  close(pick, Math.round(pick), 1e-9, 'a wide span picks a whole foot');
});

test('bestFeasibleMargin finds a margin that leaves something', () => {
  // Called only when the asked-for margin empties the axis, so what matters
  // is that what it returns actually works.
  const fallback = m.bestFeasibleMargin('us', [40, 20, 15, 10], 'full', 0.95,
    m.MARGIN_PCT_RANGE.max, 60, 'ft');
  if (fallback === null) return;
  assert.ok(fallback.marginPct >= m.MARGIN_PCT_RANGE.min);
  assert.ok(fallback.marginPct <= m.MARGIN_PCT_RANGE.max);
  const solved = m.solve('us', [40, 20, 15, 10], 'full', 0.95,
    fallback.marginPct, 60, 'ft');
  assert.ok(solved.suggestions.length > 0,
    `the margin it recommends (${fallback.marginPct}%) really does solve`);
});

// ---------------------------------------------------------------------------
// URL round-tripping, which the page promises and could not test
// ---------------------------------------------------------------------------

test('a length written as meters reads back unchanged', () => {
  const params = new URLSearchParams({ [m.URL_KEYS.wireLenM]: '21.336' });
  close(m.readWireLenM(params), 21.336, 1e-9, 'len_m is meters');
});

test('the legacy ?len= is still read as feet', () => {
  // docs/AGENTS.md promises links shared before the SI conversion resolve to
  // the same wire.  Nothing checked it until now.
  const params = new URLSearchParams({ [m.LEGACY_LEN_FT_KEY]: '70' });
  close(m.readWireLenM(params), 70 * 0.3048, 1e-9, '70 ft is 21.336 m');
});

test('the modern key wins when both are present', () => {
  const params = new URLSearchParams({
    [m.URL_KEYS.wireLenM]: '30', [m.LEGACY_LEN_FT_KEY]: '70' });
  close(m.readWireLenM(params), 30, 1e-9, 'len_m takes precedence over len');
});

test('a missing or unparseable length falls back to the default', () => {
  close(m.readWireLenM(new URLSearchParams()), m.DEFAULTS.wireLenM, 1e-9,
    'absent');
  close(m.readWireLenM(new URLSearchParams({ [m.URL_KEYS.wireLenM]: 'x' })),
    m.DEFAULTS.wireLenM, 1e-9, 'unparseable');
});

test('clamp and parseNum hold their ranges', () => {
  close(m.clamp(5, { min: 0, max: 3 }), 3, 1e-9, 'above');
  close(m.clamp(-5, { min: 0, max: 3 }), 0, 1e-9, 'below');
  close(m.parseNum('2.5', 9), 2.5, 1e-9, 'parses');
  close(m.parseNum(null, 9), 9, 1e-9, 'null falls back');
  close(m.parseNum('nonsense', 9), 9, 1e-9, 'garbage falls back');
});

test('isKeyOf keeps a bad URL parameter out of a lookup table', () => {
  assert.equal(m.isKeyOf(m.SOILS, 'average'), true);
  assert.equal(m.isKeyOf(m.SOILS, 'swamp'), false);
  assert.equal(m.isKeyOf(m.SOILS, null), false);
  assert.equal(m.isKeyOf(m.SOILS, 'toString'), false,
    'an inherited property is not a key');
});

test('the tuner preset decides what counts as a good length', () => {
  // The gates are the point of the preset, so a stricter tuner must accept a
  // subset of what a looser one does -- never something different.
  const site = { geometry: 'flatTop', balunM: m.DEFAULT_BALUN_M, counterpoiseZM: m.DEFAULT_COUNTERPOISE_Z_M, heightM: m.DEFAULT_HEIGHT_M, counterpoiseM: m.DEFAULT_COUNTERPOISE_M,
    soil: m.DEFAULT_SOIL };
  const bands = m.bandsIn('us').filter(b => m.DEFAULTS.bands.includes(b.m));
  const scored = m.PUBLISHED_FT.map(ft => m.scoreLength(
    m.fromDisplay(ft, 'ft'), bands, 'full', site, m.WIRE_RADIUS_M, 9));

  const passing = (tuner) => new Set(
    scored.map((s, i) => [s, i]).filter(([s]) => m.isGoodScore(s, tuner))
      .map(([, i]) => i));
  const rig = passing('rig');
  const wide = passing('wide');
  const roller = passing('roller');
  for (const i of rig) assert.ok(wide.has(i), 'rig ATU passes imply external');
  for (const i of wide) assert.ok(roller.has(i), 'external passes imply roller');
  assert.ok(roller.size >= wide.size && wide.size >= rig.size,
    `nested: rig ${rig.size} <= wide ${wide.size} <= roller ${roller.size}`);
});

test('every tuner preset states a limit a tuner could plausibly have', () => {
  for (const [key, def] of Object.entries(m.TUNERS)) {
    assert.ok(def.limit > 1, `${key}: the limit is a real SWR`);
    assert.ok(def.limit <= 30, `${key}: the limit is not fantasy`);
  }
  // The buttons show the ratio, so the presets must be distinguishable by it.
  const limits = Object.values(m.TUNERS).map(t => t.limit);
  assert.equal(new Set(limits).size, limits.length, 'no two presets share a limit');
  assert.ok(m.DEFAULT_TUNER in m.TUNERS, 'the default is a real preset');
});

test('the verdict follows the worst band, not the average', () => {
  // The failure this replaced: a mean under the limit while one band sat far
  // above it.  A scored length whose worst band exceeds the tuner cannot be
  // good however low its average is.
  const scored = { swr: 1.2, worst: { swr: 99 } };
  assert.equal(m.isGoodScore(scored, 'roller'), false,
    'a great average does not rescue an unmatched band');
  assert.equal(m.isGoodScore({ swr: 4.9, worst: { swr: 4.9 } }, 'wide'), true,
    'a length inside the limit on every band is good');
});

// ---- NEC deck export ----

/** Cards of one kind, split into fields, from a deck. */
const cardsOf = (deck, name) => deck.split('\n')
  .filter(line => line.startsWith(`${name} `))
  .map(line => line.split(/\s+/));

const defaultDeck = () => {
  const site = { geometry: 'flatTop', balunM: m.DEFAULT_BALUN_M, counterpoiseZM: m.DEFAULT_COUNTERPOISE_Z_M, heightM: m.DEFAULT_HEIGHT_M, counterpoiseM: m.DEFAULT_COUNTERPOISE_M,
    soil: m.DEFAULT_SOIL };
  return m.buildProbeDeck(m.fromDisplay(71, 'ft'), 14.175e6, site,
                          m.WIRE_RADIUS_M);
};

test('the deck describes the geometry the model was fitted at', async () => {
  // Checked against the fixture the browser run was always meant to be held
  // to, nec/reference_cases.json, so the deck and the PyNEC runs
  // behind the coefficients describe one antenna.  Its return_ft is the
  // horizontal run alone, which is exactly what counterpoiseM is.
  const { readFile } = await import('node:fs/promises');
  const url = new URL('../../nec/reference_cases.json', import.meta.url);
  const fixture = JSON.parse(await readFile(url, 'utf8'));

  close(m.WIRE_RADIUS_M, fixture.wire_radius_m, 5e-7, 'wire radius');
  close(m.DEFAULT_COUNTERPOISE_Z_M, fixture.return_height_m, 1e-12,
    'the default counterpoise height is the one the fixture was solved at');
  assert.equal(m.DECK_SEGMENTS_PER_WAVELENGTH, fixture.segments_per_wavelength,
    'segmentation rule');

  for (const kase of fixture.cases) {
    const heightM = m.fromDisplay(kase.height_ft, 'ft');
    const runM = m.fromDisplay(kase.return_ft, 'ft');
    const lenM = m.fromDisplay(kase.length_ft, 'ft');
    const site = { geometry: 'flatTop', heightM, balunM: m.DEFAULT_BALUN_M,
                   counterpoiseM: runM, counterpoiseZM: m.DEFAULT_COUNTERPOISE_Z_M,
                   soil: kase.soil };
    const deck = m.buildProbeDeck(lenM, 14.175e6, site, m.WIRE_RADIUS_M);

    const [antenna, drop, run] = cardsOf(deck, 'GW');
    const at = (card, i) => Number(card[i]);
    close(at(antenna, 5), heightM, 5e-4, `${kase.name}: wire height`);
    close(at(antenna, 6), lenM, 5e-4, `${kase.name}: wire length`);
    close(at(antenna, 8), heightM, 5e-4, `${kase.name}: wire stays level`);
    close(at(antenna, 9), m.WIRE_RADIUS_M, 5e-7, `${kase.name}: radius`);

    close(at(drop, 5), heightM, 5e-4, `${kase.name}: drop starts at the feedpoint`);
    close(at(drop, 8), m.DEFAULT_COUNTERPOISE_Z_M, 5e-4, `${kase.name}: drop ends low`);

    close(at(run, 5), m.DEFAULT_COUNTERPOISE_Z_M, 5e-4, `${kase.name}: run is low`);
    close(at(run, 6), runM, 5e-4, `${kase.name}: run length`);
    close(at(run, 8), m.DEFAULT_COUNTERPOISE_Z_M, 5e-4, `${kase.name}: run is level`);
    // Same direction as the antenna, per the fixture's geometry note.
    assert.ok(at(run, 6) > 0, `${kase.name}: run heads along the wire`);

    const [ground] = cardsOf(deck, 'GN');
    assert.equal(ground[1], '2',
      `${kase.name}: Sommerfeld ground, not the perfect plane of GN 1`);
    close(Number(ground[5]), kase.ground.eps, 1e-9, `${kase.name}: permittivity`);
    close(Number(ground[6]), kase.ground.sigma_s_per_m, 1e-9,
      `${kase.name}: conductivity`);
  }
});

test('the soil constants are the ones the fit was run at', async () => {
  // The page inlines them; nec/nec_model.py is where they came
  // from, and a deck built at some other soil would ask NEC a question the
  // coefficients cannot be compared against.
  const { readFile } = await import('node:fs/promises');
  const url = new URL('../../nec/nec_model.py', import.meta.url);
  const source = await readFile(url, 'utf8');
  for (const [key, soil] of Object.entries(m.SOILS)) {
    const line = new RegExp(`"${key}": \\(([\\d.]+), ([\\d.]+)\\)`).exec(source);
    assert.ok(line, `${key} appears in nec_model.py`);
    close(soil.epsR, Number(line[1]), 1e-9, `${key}: permittivity`);
    close(soil.sigmaSm, Number(line[2]), 1e-9, `${key}: conductivity`);
  }
});

test('segments are odd, bounded, and short against the shortest wave', () => {
  // Odd so a center segment exists, and dense enough at the top of the sweep,
  // where segments are electrically longest.  The source sits on segment 1 of
  // tag 1, so a wire described by too few segments moves the feedpoint.
  const site = { geometry: 'flatTop', balunM: m.DEFAULT_BALUN_M, counterpoiseZM: m.DEFAULT_COUNTERPOISE_Z_M, heightM: m.DEFAULT_HEIGHT_M, counterpoiseM: m.DEFAULT_COUNTERPOISE_M,
    soil: m.DEFAULT_SOIL };
  const topHz = 29.7e6;
  const deck = m.buildProbeDeck(m.fromDisplay(203, 'ft'), topHz, site,
                                m.WIRE_RADIUS_M);
  const wavelengthM = m.C_SPEED / topHz;
  for (const wire of cardsOf(deck, 'GW')) {
    const segments = Number(wire[2]);
    const lengthM = Math.hypot(Number(wire[6]) - Number(wire[3]),
                               Number(wire[8]) - Number(wire[5]));
    assert.equal(segments % 2, 1, 'odd segment count');
    assert.ok(segments <= m.DECK_MAX_SEGMENTS, 'inside the cap');
    if (segments < m.DECK_MAX_SEGMENTS) {
      assert.ok(segments >= m.DECK_SEGMENTS_PER_WAVELENGTH * lengthM / wavelengthM - 1,
        `${lengthM.toFixed(1)} m wire has ${segments} segments`);
    }
  }
});

test('the deck feeds the end of the antenna wire and ends properly', () => {
  const deck = defaultDeck();
  const [excitation] = cardsOf(deck, 'EX');
  assert.deepEqual(excitation.slice(0, 4), ['EX', '0', '1', '1'],
    'a voltage source on segment 1 of the antenna wire');
  assert.ok(deck.startsWith('CM '), 'the deck opens with a comment');
  assert.ok(deck.includes('\nCE\n'), 'comments are terminated');
  assert.ok(deck.includes('\nGE 1\n'), 'geometry completes over a ground plane');
  // NEC-2 solves at an execution card, not at FR.  A deck that went FR / EN
  // was well formed, loaded, and computed nothing: nec2c echoed the geometry
  // and stopped.
  assert.ok(deck.includes('\nXQ\n'), 'something tells NEC to run');
  assert.ok(deck.endsWith('EN\n'), 'and the deck ends');
});

test('the counterpoise ceiling follows the geometry it hangs from', () => {
  const flat = { geometry: 'flatTop', heightM: 9.144, balunM: 0.61 };
  assert.equal(m.counterpoiseCeilingM(flat), 9.144 / 2,
    'a flat top reaches half the wire height, as the fit does');
  const sloper = { geometry: 'sloper', heightM: 30, balunM: 0.61 };
  assert.equal(m.counterpoiseCeilingM(sloper), 0.61,
    'a sloper hangs from its balun');
  const tall = { geometry: 'flatTop', heightM: 60, balunM: 0.61 };
  assert.equal(m.counterpoiseCeilingM(tall), m.COUNTERPOISE_Z_RANGE_M.max,
    'and never past the range the table was fitted over');
});

test('a sloper is never offered a wire shorter than its own rise', () => {
  // Apex well up, balun at a stake: the rise is 29.7 m, and a quarter wave on
  // 20 m is a much shorter wire, so the short limit alone lets unbuildable
  // lengths through.
  const site = { geometry: 'sloper', balunM: 0.3, heightM: 30,
    counterpoiseM: m.DEFAULT_COUNTERPOISE_M,
    counterpoiseZM: m.DEFAULT_COUNTERPOISE_Z_M, soil: m.DEFAULT_SOIL };
  const out = m.solveImpedance('us', [20, 15, 10], 'full', site,
    m.WIRE_RADIUS_M, 9, 60, 'm');
  for (const s of out.suggestions) {
    assert.equal(m.riseShortfallM(site, s.lenM), null,
      `${s.lenM} m does not reach a 29.7 m rise`);
  }
});

test('the deck runs the counterpoise on the bearing each geometry was fitted at',
  () => {
    const base = { counterpoiseM: 7.62, counterpoiseZM: 0.05,
      soil: m.DEFAULT_SOIL };
    const flat = { ...base, geometry: 'flatTop', heightM: 9.144, balunM: 0.61 };
    const sloper = { ...base, geometry: 'sloper', heightM: 20, balunM: 0.61 };
    const runOf = (site) => m.deckWires(21.336, site, m.WIRE_RADIUS_M, 10)
      .find(w => w.tag === 3);
    assert.equal(runOf(flat).x2, 7.62, 'a flat top lays it along the antenna');
    assert.equal(runOf(sloper).x2, -7.62,
      'a sloper heads it away, as nec/nec_model.py sloper_deck does');
  });

test('a recommended length is rounded to its unit own grid', () => {
  close(m.toDisplay(m.roundToUnit(m.fromDisplay(42.4, 'ft'), 'ft'), 'ft'), 42,
    1e-9, 'feet round to whole feet');
  close(m.toDisplay(m.roundToUnit(m.fromDisplay(42.4, 'ftin'), 'ftin'), 'ft'), 42,
    1e-9, 'feet and inches shares the foot grid');
  close(m.roundToUnit(24.24, 'm'), 24, 1e-9, 'meters round to half meters');
  close(m.roundToUnit(17.63, 'm'), 17.5, 1e-9, 'and not to whole meters');
});

test('the display unit does not change the quality of what is offered', () => {
  // The two grids are 1 ft and 0.5 m, so a length can round to either of two
  // neighbouring minima.  Where those minima score the same to two decimals,
  // which one reaches the list is a coin toss and asserting on lengths would
  // be asserting on the toss.  What must not change is how good the offered
  // antennas are.
  const site = { geometry: 'flatTop', heightM: m.DEFAULT_HEIGHT_M,
    balunM: m.DEFAULT_BALUN_M, counterpoiseM: m.DEFAULT_COUNTERPOISE_M,
    counterpoiseZM: m.DEFAULT_COUNTERPOISE_Z_M, soil: m.DEFAULT_SOIL };
  const picks = (units) => m.solveImpedance('us', [40, 20, 15, 10], 'full', site,
    m.WIRE_RADIUS_M, 9, 60, units).suggestions;
  const feet = picks('ft');
  const meters = picks('m');

  assert.equal(feet.length, meters.length, 'the same number of lengths');
  for (let i = 0; i < feet.length; i++) {
    close(meters[i].swr, feet[i].swr, 0.05,
      `pick ${i + 1} is as good either way`);
  }
  // And the best pick really is the same antenna, not merely as good.
  assert.ok(Math.abs(feet[0].lenM - meters[0].lenM)
    <= 0.5 / 2 + m.fromDisplay(1, 'ft') / 2,
    `best pick ${feet[0].lenM.toFixed(2)} m against ${meters[0].lenM.toFixed(2)} m`);
});

test('a site is held to a geometry the model can describe', () => {
  // Counterpoise raised to the feedpoint leaves no drop, and a counterpoise of
  // no length then leaves no return conductor at all.
  const degenerate = { geometry: 'sloper', heightM: 20, balunM: 0.61,
    counterpoiseZM: 0.61, counterpoiseM: 0, soil: m.DEFAULT_SOIL };
  const held = m.withSiteInvariants(degenerate);
  close(m.returnConductorM(held), m.MIN_RETURN_M, 1e-12,
    'the return conductor keeps its floor');
  // Lowering the wire under a counterpoise already set pulls it down too.
  const stale = { geometry: 'flatTop', heightM: 2, balunM: 0.61,
    counterpoiseZM: 4.5, counterpoiseM: 7.62, soil: m.DEFAULT_SOIL };
  assert.equal(m.withSiteInvariants(stale).counterpoiseZM, 1,
    'the counterpoise follows the ceiling down');
});

test('a length the model cannot describe is declined, not scored as NaN', () => {
  const bands = m.bandsIn('us').filter(b => b.m === 20);
  // The counterpoise level with the balun leaves no drop, and no counterpoise
  // beyond it leaves no return conductor: the two slider drags that reach it.
  const site = { geometry: 'sloper', heightM: 20, balunM: 0.61,
    counterpoiseM: 0, counterpoiseZM: 0.61, soil: m.DEFAULT_SOIL };
  assert.equal(m.returnConductorM(site), 0, 'the corner this guards');
  assert.equal(m.scoreLength(21.336, bands, 'full', site, m.WIRE_RADIUS_M, 9),
    null, 'no return conductor, no score');
  const sane = { ...site, counterpoiseM: m.DEFAULT_COUNTERPOISE_M };
  assert.equal(m.scoreLength(1e5, bands, 'full', sane, m.WIRE_RADIUS_M, 9), null,
    'a wire long enough to overflow coth is declined too');
  assert.ok(m.scoreLength(21.336, bands, 'full', sane, m.WIRE_RADIUS_M, 9),
    'and an ordinary antenna still scores');
});

test('the quoted accuracy is the accuracy the shipped table measures', async () => {
  // The caveat text is a claim about coefficients2d.json's own error block.
  // Nothing else compares them, so a refit could move the error and leave the
  // page quoting the old one.  Per length rather than per group: the page
  // recommends lengths, and a group is an RMS over a couple of hundred of
  // them, which hides its own tail.
  const { readFile } = await import('node:fs/promises');
  const url = new URL('../../nec/coefficients2d.json', import.meta.url);
  const { flat_top: flatTop, sloper } = JSON.parse(await readFile(url, 'utf8'));

  close(m.MODEL_TYPICAL_FACTOR, flatTop.error.per_length.median, 5e-3,
    'typical is the median length');
  close(m.MODEL_BOUND_FACTOR, flatTop.error.per_length.p90, 5e-3,
    'the bound is the ninetieth length');
  assert.ok(flatTop.error.per_length.median >= sloper.error.per_length.median
    && flatTop.error.per_length.p90 >= sloper.error.per_length.p90,
    'the flat top is the weaker of the two, which is why it is quoted');
  assert.ok(flatTop.error.per_length.p90 > flatTop.error.p90,
    'the per-length ninetieth is worse than the per-group one, which is why '
    + 'the page quotes it');
  assert.ok(flatTop.error.phase_deg.p90 > 0, 'phase error is recorded');
});

test('the page refuses the near-vertical slopers the sweep refused to fit', () => {
  // nec/nec_model.py sloper_deck returns None at or below rise * the margin,
  // so answering inside that wedge would be answering without evidence.
  const site = { geometry: 'sloper', heightM: 20, balunM: 0.61,
    counterpoiseM: m.DEFAULT_COUNTERPOISE_M,
    counterpoiseZM: m.DEFAULT_COUNTERPOISE_Z_M, soil: m.DEFAULT_SOIL };
  const riseM = 20 - 0.61;
  assert.ok(m.SLOPER_REACH_MARGIN > 1, 'the margin is a margin');
  assert.notEqual(m.riseShortfallM(site, riseM * 1.01), null,
    'a wire inside the wedge is refused');
  assert.equal(m.riseShortfallM(site, riseM * 1.03), null,
    'and one clear of it is answered');
  close(m.riseShortfallM(site, riseM), riseM * m.SLOPER_REACH_MARGIN, 1e-9,
    'the shortfall reports the shortest wire the model will answer for');
});

// The fit's domain, and the page knowing where it ends.

test('the model carries the domain the fit was measured over', async () => {
  const { readFile } = await import('node:fs/promises');
  const url = new URL('../../nec/coefficients2d.json', import.meta.url);
  const { domain } = JSON.parse(await readFile(url, 'utf8'));
  close(m.MODEL_DOMAIN.minHOverLambda, domain.min_h_over_lambda, 1e-12,
    'the h/lambda floor is the fit floor');
  close(m.MODEL_DOMAIN.maxHOverLambda, m.MODEL_H_NODES[m.MODEL_H_NODES.length - 1],
    1e-12, 'the ceiling is the top node');
  close(m.MODEL_DOMAIN.minCounterpoiseZM, domain.min_counterpoise_z_m, 1e-12,
    'the counterpoise floor');
  close(m.MODEL_DOMAIN.maxCounterpoiseZM, domain.max_counterpoise_z_m, 1e-12,
    'and its ceiling');
  close(m.COUNTERPOISE_Z_RANGE_M.min, domain.min_counterpoise_z_m, 1e-12,
    'the control offers what the model defines');
  close(m.COUNTERPOISE_Z_RANGE_M.max, domain.max_counterpoise_z_m, 1e-12,
    'at both ends');
});

test('no setting the controls allow falls outside the fit', () => {
  // The sweeps were extended to cover the whole control space, so this is
  // the invariant that keeps them that way: widen a control or narrow the
  // fit and this fails rather than the page quietly extrapolating.
  const bands = m.bandsIn('us');
  for (let heightM = m.HEIGHT_RANGE_M.min; heightM <= m.HEIGHT_RANGE_M.max;
    heightM += 0.5) {
    const site = { geometry: 'flatTop', heightM, balunM: m.DEFAULT_BALUN_M,
      counterpoiseM: m.DEFAULT_COUNTERPOISE_M,
      counterpoiseZM: m.DEFAULT_COUNTERPOISE_Z_M, soil: m.DEFAULT_SOIL };
    for (const segment of ['full', 'cw']) {
      const outside = m.outOfDomainBands(bands, segment, site);
      assert.deepEqual(outside.map(o => `${o.band.label} ${o.edge}`), [],
        `${heightM} m, ${segment}`);
    }
  }
});

test('the guard still fires for a geometry the controls cannot reach', () => {
  // Below the height control's own floor, which only a hand-built site or a
  // future widening of the control can produce.
  const bands = m.bandsIn('us').filter(b => b.m === 160);
  const below = { geometry: 'flatTop', heightM: 0.5, balunM: m.DEFAULT_BALUN_M,
    counterpoiseM: m.DEFAULT_COUNTERPOISE_M,
    counterpoiseZM: m.DEFAULT_COUNTERPOISE_Z_M, soil: m.DEFAULT_SOIL };
  const out = m.outOfDomainBands(bands, 'full', below);
  assert.equal(out.length, 1, '0.5 m on 160 m is under the fitted floor');
  assert.equal(out[0].edge, 'below');
  // And above the top node, which needs a wire higher than the control goes.
  const above = { ...below, heightM: 40 };
  const high = m.outOfDomainBands(m.bandsIn('us').filter(b => b.m === 10),
    'full', above);
  assert.equal(high.length, 1, '40 m on 10 m is over the top node');
  assert.equal(high[0].edge, 'above');
});

test('the shipped tables are fitted from NEC-4.2 alone', async () => {
  // NEC-2 disagrees with NEC-4.2 over ground, which is the whole argument of
  // MODEL.md's Sommerfeld section, so a table fitted from a NEC-2 grid would
  // be a different model wearing the same numbers.  The generator records
  // what it read; this is what makes that record load bearing.
  const { readFile } = await import('node:fs/promises');
  const url = new URL('../../nec/coefficients2d.json', import.meta.url);
  const data = JSON.parse(await readFile(url, 'utf8'));
  for (const geometry of ['flat_top', 'sloper']) {
    const { sweeps } = data[geometry].provenance;
    assert.ok(sweeps.length > 0, `${geometry} names the sweeps it was fitted from`);
    for (const sweep of sweeps) {
      assert.match(sweep, /^nec4_/,
        `${geometry} is fitted from ${sweep}, which is not a NEC-4.2 sweep`);
    }
  }
});

// ------------------------------------------------------------
// In-page NEC check, the pure half
// ------------------------------------------------------------

const defaultSite = () => ({
  geometry: 'flatTop', balunM: m.DEFAULT_BALUN_M,
  counterpoiseZM: m.DEFAULT_COUNTERPOISE_Z_M, heightM: m.DEFAULT_HEIGHT_M,
  counterpoiseM: m.DEFAULT_COUNTERPOISE_M, soil: m.DEFAULT_SOIL,
});

test('the check samples the model curve at shared frequencies', () => {
  const bands = m.bandsIn('us').filter(b => [40, 20].includes(b.m));
  const freqs = m.necSampleFreqsHz(bands, 'full');
  assert.equal(freqs.length, bands.length * Math.ceil(m.SWR_SAMPLES_PER_BAND / 2),
    'every other point of the model grid, endpoints included');
  for (const band of bands) {
    const [loHz, hiHz] = m.bandEdgesHz(band, 'full');
    assert.ok(freqs.includes(loHz), `${band.m} m low edge sampled`);
    assert.ok(freqs.includes(hiHz), `${band.m} m high edge sampled`);
    // Each sample sits on the model curve's own grid, so the two curves are
    // compared at the same frequencies rather than near them.
    for (const freqHz of freqs.filter(f => f >= loHz && f <= hiHz)) {
      const grid = (freqHz - loHz) / (hiHz - loHz) * (m.SWR_SAMPLES_PER_BAND - 1);
      close(grid, Math.round(grid), 1e-6, `${freqHz} Hz on the model grid`);
    }
  }
});

test('a probe deck is the exported geometry at one frequency', () => {
  const site = defaultSite();
  const lenM = m.fromDisplay(71, 'ft');
  const freqHz = 14.175e6;
  const deck = m.buildProbeDeck(lenM, freqHz, site, m.WIRE_RADIUS_M);

  const [fr] = cardsOf(deck, 'FR');
  assert.equal(fr[2], '1', 'one frequency');
  close(Number(fr[5]), freqHz / 1e6, 1e-6, 'the frequency asked for');

  // Same wires as the export builds for a sweep ending at this frequency,
  // segmented for this frequency exactly as the fitting sweeps were.
  const wires = m.deckWires(lenM, site, m.WIRE_RADIUS_M, m.C_SPEED / freqHz);
  const gw = cardsOf(deck, 'GW');
  assert.equal(gw.length, wires.length, 'wire for wire');
  for (let i = 0; i < wires.length; i++) {
    assert.equal(Number(gw[i][2]), wires[i].segments,
      `wire ${i + 1} segmented for the probe frequency`);
  }
  assert.equal(cardsOf(deck, 'GN')[0][1], '2', 'Sommerfeld ground');
  assert.equal(cardsOf(deck, 'EX')[0][2], '1', 'fed at the feedpoint wire');
});

test('the parser reads the source impedance out of nec2c output', () => {
  // Verbatim from nec2c-wasm 0.1.3 over a probe deck, trimmed to the block
  // the parser hunts for.
  const output = [
    '                        --------- ANTENNA INPUT PARAMETERS ---------',
    '  TAG   SEG       VOLTAGE (VOLTS)         CURRENT (AMPS)         IMPEDANCE (OHMS)        ADMITTANCE (MHOS)     POWER',
    '  No:   No:     REAL      IMAGINARY     REAL      IMAGINARY     REAL      IMAGINARY    REAL       IMAGINARY   (WATTS)',
    '    1     1  1.0000E+00  0.0000E+00  3.0909E-04 -4.0143E-04  1.2042E+03  1.5639E+03  3.0909E-04 -4.0143E-04  1.5455E-04',
    '',
  ].join('\n');
  const z = m.parseNecZ(output);
  assert.ok(z !== null, 'found the source row');
  close(z.re, 1204.2, 1e-6, 'resistance');
  close(z.im, 1563.9, 1e-6, 'reactance');

  assert.equal(m.parseNecZ('RUN TIME = 0'), null, 'no parameters, no number');
  assert.equal(m.parseNecZ('ANTENNA INPUT PARAMETERS\nnothing here'), null,
    'a block with no data row');
});

test('the geometric mean SWR matches the model curve statistic', () => {
  const ratio = m.DEFAULT_UNUN_RATIO;
  const matched = { re: m.Z_SYSTEM_OHMS * ratio, im: 0 };
  close(m.geometricMeanSwr([matched], ratio), 1, 1e-9, 'a matched load');
  const z = { re: 1204.2, im: 1563.9 };
  close(m.geometricMeanSwr([z, matched], ratio),
    Math.sqrt(m.swrAtRadio(z, ratio)), 1e-9,
    'two samples multiply under the root');
  assert.equal(m.geometricMeanSwr([], ratio), null, 'nothing measured');
  assert.equal(m.geometricMeanSwr([{ re: NaN, im: 0 }], ratio), null,
    'a solve the model cannot score declines');
});

test('the overlay key moves with every input the check depends on', () => {
  const site = defaultSite();
  const bands = m.bandsIn('us').filter(b => [40, 20].includes(b.m));
  const key = () => m.necOverlayKey(bands, 'full', site, 9, 60);
  const base = key();
  assert.equal(key(), base, 'stable while nothing changes');

  assert.notEqual(m.necOverlayKey(bands, 'cw', site, 9, 60), base, 'segment');
  assert.notEqual(m.necOverlayKey(bands.slice(0, 1), 'full', site, 9, 60),
    base, 'bands');
  assert.notEqual(m.necOverlayKey(bands, 'full', site, 4, 60), base, 'unun');
  assert.notEqual(m.necOverlayKey(bands, 'full', site, 9, 45), base,
    'map range');
  for (const [field, value] of [['geometry', 'sloper'], ['heightM', 10],
    ['balunM', 1], ['counterpoiseM', 5], ['counterpoiseZM', 1],
    ['soil', 'poor']]) {
    assert.notEqual(
      m.necOverlayKey(bands, 'full', { ...site, [field]: value }, 9, 60),
      base, field);
  }
});

test('the check flags bands whose feedpoint is low in wavelengths', () => {
  // The threshold is nec/sommerfeld_report.html's: every NEC-2 descendant
  // is exact with the fed element at 0.05 wavelengths and +92 percent by
  // 0.02.  A default-height flat top on 160 m sits just above it; drop the
  // wire and 160 m goes suspect while 40 m stays clean.
  const bands = m.bandsIn('us').filter(b => [160, 40].includes(b.m));
  const high = defaultSite();
  assert.deepEqual(m.necSuspectBands(bands, 'full', high).map(b => b.m), [],
    `${high.heightM} m up is above the threshold on every band`);

  const low = { ...high, heightM: 5 };
  assert.deepEqual(m.necSuspectBands(bands, 'full', low).map(b => b.m), [160],
    'a 5 m wire is under 0.05 wavelengths on 160 m and fine on 40 m');

  // A sloper is fed at the balun, near the ground, so long bands go
  // suspect no matter how high the far end reaches.
  const sloper = { ...high, geometry: 'sloper', balunM: 1, heightM: 15 };
  assert.deepEqual(m.necSuspectBands(bands, 'full', sloper).map(b => b.m),
    [160, 40], 'a sloper fed 1 m up is suspect on both');
});

test('a sloper hatches everything shorter than its rise', () => {
  // The check already refused to solve unbuildable lengths; the map now
  // says why, by growing the too-short zone to the rise and labeling it.
  const site = { geometry: 'sloper', balunM: 0.85, heightM: 17,
    counterpoiseM: 7.62, counterpoiseZM: 0.25, soil: m.DEFAULT_SOIL };
  const out = m.solveImpedance('us', [20, 15, 10], 'full', site,
    m.WIRE_RADIUS_M, 9, 21.3, 'ft');
  const riseFloor = (17 - 0.85) * m.SLOPER_REACH_MARGIN;
  close(out.shortLimit, riseFloor, 1e-9, 'the rise governs on high bands');
  assert.ok(out.shortLabel.includes('rise'), 'and the legend says so');

  const flat = { ...site, geometry: 'flatTop' };
  const flatOut = m.solveImpedance('us', [20, 15, 10], 'full', flat,
    m.WIRE_RADIUS_M, 9, 21.3, 'ft');
  close(flatOut.shortLimit, m.tooShortM(flatOut.bands, 'full', m.MODEL_VF_A),
    1e-9, 'a flat top keeps the quarter-wave floor');
  assert.ok(!flatOut.shortLabel.includes('rise'), 'and the plain label');
});


test('the map always has room for every published length', () => {
  // With 40 m as the lowest band, one wavelength is about 137 ft and the
  // published table scores out to 203 ft; a scored row must have a place
  // on the map.
  const bands = m.bandsIn('us').filter(b => [40, 20].includes(b.m));
  const spanM = m.mapSpanM(bands, 'full', m.MODEL_VF_A);
  const longestM = m.fromDisplay(Math.max(...m.PUBLISHED_FT), 'ft');
  assert.ok(spanM > longestM, 'the longest published length fits');

  // On 160 m one wavelength alone is far past the table, and governs.
  const topBand = m.bandsIn('us').filter(b => b.m === 160);
  assert.ok(m.mapSpanM(topBand, 'full', m.MODEL_VF_A) > spanM,
    'a low band still stretches the map beyond the table');
});

test('refinement bisects rough spans and leaves smooth ones alone', () => {
  const flat = [{ lenM: 10, swr: 2.0 }, { lenM: 12, swr: 2.2 },
                { lenM: 14, swr: 2.0 }];
  assert.deepEqual(m.refineGapsM(flat, 0.1), [], 'smooth stays as sampled');

  const cliff = [{ lenM: 10, swr: 2.0 }, { lenM: 12, swr: 40.0 },
                 { lenM: 14, swr: 2.0 }];
  assert.deepEqual(m.refineGapsM(cliff, 0.1), [11, 13],
    'both flanks of a peak get midpoints');
  assert.deepEqual(m.refineGapsM(cliff, 1.5), [],
    'but never below the finest grid worth solving');
});

test('the coda samples exactly the grid scoreLength scores on', () => {
  const bands = m.bandsIn('us').filter(b => [40, 20].includes(b.m));
  const grid = m.necCheckFreqs(bands, 'full');
  assert.equal(grid.length, bands.length * m.SWR_SAMPLES_PER_BAND,
    'every sample of every band');
  for (const band of bands) {
    const [loHz, hiHz] = m.bandEdgesHz(band, 'full');
    const own = grid.filter(g => g.band === band);
    close(own[0].freqHz, loHz, 1e-6, `${band.m} m starts at the low edge`);
    close(own[own.length - 1].freqHz, hiHz, 1e-6, 'and ends at the high');
  }
});

test('a measured score matches the model statistic on the same grid', () => {
  const bands = m.bandsIn('us').filter(b => b.m === 20);
  const grid = m.necCheckFreqs(bands, 'full');
  const ratio = 9;
  // Synthetic impedances, one per grid point, with an obvious worst.
  const zs = grid.map((g, i) => ({ re: 450 + 60 * i, im: 40 * i }));
  const scored = m.measuredScore(zs, grid, ratio);
  assert.ok(scored !== null);
  const swrs = zs.map(z => m.swrAtRadio(z, ratio));
  close(scored.swr,
    Math.exp(swrs.reduce((s, x) => s + Math.log(x), 0) / swrs.length),
    1e-9, 'geometric mean, as scoreLength takes it');
  close(scored.worst.swr, Math.max(...swrs), 1e-9, 'the worst sample');
  assert.equal(scored.worst.band.m, 20, 'attributed to its band');

  assert.equal(m.measuredScore([], grid, ratio), null, 'nothing measured');
  assert.equal(m.measuredScore(zs.slice(1), grid, ratio), null,
    'a short answer does not silently misalign');
});

test('the overlay states its median offset from the model', () => {
  const curve = [{ lenM: 10, swr: 2.0 }, { lenM: 20, swr: 2.0 },
                 { lenM: 30, swr: 4.0 }];
  const nec = [{ lenM: 10, swr: 3.0 }, { lenM: 19.9, swr: 3.0 },
               { lenM: 30, swr: 4.0 }];
  close(m.medianOverlayRatio(nec, curve), 1.5, 1e-9,
    'median of per-length ratios against the nearest scored length');
  assert.equal(m.medianOverlayRatio([], curve), null, 'no run, no claim');
  assert.equal(m.medianOverlayRatio(nec, []), null, 'no curve either');
});

test('an insulated wire slows the model by the measured factor', () => {
  // The jacket factor was measured with NEC-4.2's IS card (MODEL.md,
  // "Insulation is a scalar"); the model applies it to both lines, so a
  // resonance peak moves to a shorter length by exactly that scale.
  const bare = defaultSite();
  const insulated = { ...bare, wire: 'insulated' };
  const freqHz = 7.15e6;
  const peakOf = (site) => {
    let best = { lenM: 0, mag: 0 };
    for (let lenM = 19; lenM <= 23; lenM += 0.01) {
      const z = m.endFedZin(lenM, freqHz, site, m.WIRE_RADIUS_M);
      const mag = Math.hypot(z.re, z.im);
      if (mag > best.mag) best = { lenM, mag };
    }
    return best.lenM;
  };
  close(peakOf(insulated) / peakOf(bare), m.WIRES.insulated.lengthScale, 0.002,
    'the peak moves by lengthScale');
  assert.equal(m.wireOf(bare).lengthScale, 1.0, 'bare is the fitted wire');
});

test('an insulated probe deck carries the K6OIK equivalent wire', () => {
  // Radius a(b/a)^(1-1/epsr) plus distributed inductance
  // (mu0/2pi)(1-1/epsr)ln(b/a): S. Stearns, K6OIK, "Modeling Insulated
  // Wire", validated against NEC-4.2's IS card in MODEL.md.
  const site = { ...defaultSite(), wire: 'insulated' };
  const lenM = m.fromDisplay(71, 'ft');
  const deck = m.buildProbeDeck(lenM, 14.175e6, site, m.WIRE_RADIUS_M);
  const spec = m.WIRES.insulated;
  const exponent = 1 - 1 / spec.epsR;
  const aPrime = m.WIRE_RADIUS_M
    * (spec.sheathRadiusM / m.WIRE_RADIUS_M) ** exponent;
  const gw = cardsOf(deck, 'GW');
  const lds = cardsOf(deck, 'LD');
  assert.equal(lds.length, gw.length, 'one loading card per wire');
  const henriesPerM = 2e-7 * exponent
    * Math.log(spec.sheathRadiusM / m.WIRE_RADIUS_M);
  for (let i = 0; i < gw.length; i++) {
    close(Number(gw[i][9]), aPrime, 5e-7, `wire ${i + 1} radius is a'`);
    const wireLenM = Math.hypot(
      Number(gw[i][6]) - Number(gw[i][3]),
      Number(gw[i][7]) - Number(gw[i][4]),
      Number(gw[i][8]) - Number(gw[i][5]));
    close(Number(lds[i][6]) * Number(gw[i][2]), henriesPerM * wireLenM,
      henriesPerM * wireLenM * 1e-4,
      `wire ${i + 1} carries the jacket's whole inductance`);
  }
  const bareDeck = m.buildProbeDeck(lenM, 14.175e6, defaultSite(),
    m.WIRE_RADIUS_M);
  assert.equal(cardsOf(bareDeck, 'LD').length, 0, 'bare decks stay bare');
});

test('the overlay key and the URL carry the wire type', () => {
  const site = defaultSite();
  const bands = m.bandsIn('us').filter(b => [40, 20].includes(b.m));
  assert.notEqual(
    m.necOverlayKey(bands, 'full', { ...site, wire: 'insulated' }, 9, 60),
    m.necOverlayKey(bands, 'full', site, 9, 60),
    'a different jacket is a different check');
  assert.equal(m.DEFAULTS.wire, 'bare', 'bare by default');
  assert.equal(m.URL_KEYS.wire, 'wire', 'and linkable');
});

test('a band sweep spans the band and agrees with the score samples', () => {
  const site = defaultSite();
  const band = m.bandsIn('us').find(b => b.m === 40);
  const lenM = m.fromDisplay(71, 'ft');
  const sweep = m.bandSweep(lenM, band, 'full', site, m.WIRE_RADIUS_M, 9);
  assert.equal(sweep.length, m.BAND_SWEEP_POINTS, 'every point scored');
  const [loHz, hiHz] = m.bandEdgesHz(band, 'full');
  close(sweep[0].freqHz, loHz, 1, 'starts at the low edge');
  close(sweep[sweep.length - 1].freqHz, hiHz, 1, 'ends at the high edge');
  // The same statistic scoreLength samples: at a shared frequency the two
  // must agree exactly.
  const swrAt = m.swrAtRadio(
    m.endFedZin(lenM, loHz, site, m.WIRE_RADIUS_M), 9);
  close(sweep[0].swr, swrAt, 1e-12, 'the same model, the same number');
});

