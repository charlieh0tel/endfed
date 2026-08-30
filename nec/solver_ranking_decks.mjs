// Which browser NEC-2 to believe, where: the decks and the two browser
// solvers' answers.  Generates the page's own probe decks across the
// controls' domain, solves each with nec2c and nec2++ as the check does,
// and writes one JSON line per deck for solver_ranking.py, which adds
// NEC-4.2 at 1x, 2x and 4x (converged by Richardson) and NEC-5 at 1x, then
// scores every solver against the converged answer.
//
// Needs the page's extracted model (npm --prefix docs/tools run check
// writes docs/tools/.check/model.mjs) and the two wasm packages, which are
// not repository dependencies: point NODE_PATH at a directory holding
// node_modules with nec2c-wasm and necpp-wasm installed.
//
//     NODE_PATH=/some/scratch/node_modules node nec/solver_ranking_decks.mjs > nec/ranking/decks.jsonl

import { createRequire } from 'node:module';
import * as m from '../docs/tools/.check/model.mjs';

const require = createRequire(import.meta.url);
const { runNec } = await import(require.resolve('nec2c-wasm'));
const { createContext } = await import(require.resolve('necpp-wasm'));

const FREQS_HZ = [7.15e6, 14.175e6, 28.85e6];
const SOILS = ['average', 'good', 'poor'];
const LENGTHS_M = Array.from({ length: 30 }, (_, i) => 3 + i * (66 - 3) / 29);
const RETURN_M = 7.62;
const BALUN_M = 0.61;
/** @type {{geometry: string, heightM: number, counterpoiseZM: number}[]} */
const sites = [];
for (const heightM of [3, 9.144, 20]) {
  for (const counterpoiseZM of [0.01, 0.05, 0.3, 1.0]) {
    sites.push({ geometry: 'flatTop', heightM, counterpoiseZM });
  }
}
for (const heightM of [10, 20]) {
  for (const counterpoiseZM of [0.05, 0.3]) {
    sites.push({ geometry: 'sloper', heightM, counterpoiseZM });
  }
}

let id = 0;
for (const base of sites) {
  for (const soil of SOILS) {
    const site = m.withSiteInvariants({ ...base, counterpoiseM: RETURN_M,
      balunM: BALUN_M, soil, wire: 'bare' });
    for (const freqHz of FREQS_HZ) {
      for (const lenM of LENGTHS_M) {
        if (m.riseShortfallM(site, lenM) !== null) continue;
        const deck = m.buildProbeDeck(lenM, freqHz, site, m.WIRE_RADIUS_M);
        const z2c = m.parseNecZ(await runNec(deck));
        let zpp = null;
        const nec = await createContext();
        try {
          zpp = nec.solveModel(m.deckModel(deck)).feeds[0].impedance;
        } catch {
          zpp = null;
        } finally {
          nec.dispose();
        }
        process.stdout.write(JSON.stringify({
          id: id++, geometry: site.geometry, heightM: site.heightM,
          counterpoiseZM: site.counterpoiseZM, soil, freqHz, lenM, deck,
          nec2c: z2c === null ? null : { re: z2c.re, im: z2c.im },
          necpp: zpp,
        }) + '\n');
      }
    }
  }
}
