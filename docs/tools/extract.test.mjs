// The extraction pipeline, which everything else trusts: the type check reads
// the padded .jsx and reports line numbers against it, and the model tests
// import whatever the PURE region extractor writes.  Both make promises no
// other test was holding them to.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

import { extractScript } from './extract.mjs';
import { assertPure, pureRegion } from './extract-model.mjs';

const PAGE = new URL('../random-wire.html', import.meta.url);
const JSX = new URL('.check/random-wire.jsx', import.meta.url);

test('a diagnostic line in the extracted jsx is that line of the html', async () => {
  const html = (await readFile(PAGE, 'utf8')).split('\n');
  const jsx = (await readFile(JSX, 'utf8')).split('\n');
  // Every line with code in it, not a sample: an off-by-one sends each
  // diagnostic to its neighbour, which is plausible enough to chase.
  let compared = 0;
  for (let i = 0; i < jsx.length; i++) {
    if (jsx[i].trim() === '' || jsx[i].trim() === 'export {};') continue;
    assert.equal(jsx[i], html[i], `jsx line ${i + 1} is html line ${i + 1}`);
    compared++;
  }
  assert.ok(compared > 1000, 'the whole script body was compared');
});

test('importing the extractors does not run them', async () => {
  // extract-model.mjs imports extractScript; an unguarded CLI body would run
  // on that import, with extract-model's argv, and write the whole page over
  // the module about to be extracted.
  const run = promisify(execFile);
  const { stdout, stderr } = await run(process.execPath, [
    '--input-type=module', '-e',
    "import('./extract.mjs').then(() => import('./extract-model.mjs'))"
      + ".then(() => console.log('imported clean'))",
  ], { cwd: new URL('.', import.meta.url) });
  assert.match(stdout, /imported clean/);
  assert.equal(stderr, '', 'no usage message, no extraction');
});

test('the purity guard is not fooled by strings that look like comments', () => {
  const region = "const u = 'https://example.com'; document.title = u;\n";
  assert.throws(() => assertPure(region), /touches the DOM/,
    'a // inside a string does not blank the rest of the line');
  const swallowing = "const a = '/*'; document.title = a;\n/** doc */\n";
  assert.throws(() => assertPure(swallowing), /touches the DOM/,
    'a /* inside a string does not pair with the next close');
});

test('the purity guard covers the ways back to a global', () => {
  for (const line of ['globalThis.foo = 1;', 'const x = self.matchMedia;',
    'location.href;', 'fetch(url);', 'new XMLHttpRequest();']) {
    assert.throws(() => assertPure(`${line}\n`), /touches the DOM/, line);
  }
});

test('the guard still passes the prose and the code it should', () => {
  assert.doesNotThrow(() => assertPure(
    '// documentation mentions a window and a document\n'
    + 'const MAP = { top: 10 };\n'
    + '/* a line open at the far end */\n'));
});

test('the shipped page passes its own purity guard', async () => {
  const { body } = extractScript(await readFile(PAGE, 'utf8'));
  assert.doesNotThrow(() => assertPure(pureRegion(body)));
});
