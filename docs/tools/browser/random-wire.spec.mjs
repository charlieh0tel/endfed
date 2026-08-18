/**
 * Browser checks for random-wire.html.
 *
 * These exist because the type checker proves the page compiles and the
 * node tests prove the DOM-free half computes, and neither can see a
 * control that does not render, a button that activates the wrong thing,
 * or text that has become unreadable.  Every test here corresponds to an
 * item in BROWSER_CHECKS.md.
 *
 * Assertions are on behavior and invariants rather than on fixed values,
 * so that changing a coefficient or a default does not break the suite.
 */

import { expect, test } from '@playwright/test';

/** SWR the page promises to stay within, per tuner button. */
const TUNER_LIMITS = { '3:1': 3, '5:1': 5, '9:1': 9, '12:1': 12 };

/** Feet per meter, for the legacy URL parameter check. */
const FEET_PER_METER = 1 / 0.3048;

/**
 * A control group, addressed by its legend.  Scoping matters: "9:1" is an
 * option in both the Tuner and the Unun ratio groups.
 * @param {import('@playwright/test').Page} page
 * @param {string} legend
 */
const group = (page, legend) =>
  page.locator('fieldset', {
    has: page.locator('legend', { hasText: new RegExp(`^\\s*${legend}\\s*$`) }),
  });

/**
 * One option within a group, by its exact label.  These are buttons
 * carrying role="radio" and aria-checked, so getByRole('button') does not
 * find them.  Text is matched exactly because "1:1" is a substring of
 * "11:1".
 * @param {import('@playwright/test').Page} page
 * @param {string} legend
 * @param {string} label
 */
const option = (page, legend, label) =>
  group(page, legend).locator(`button:text-is("${label}")`);

/**
 * Open the page and wait for React to have rendered.
 * @param {import('@playwright/test').Page} page
 * @param {string} query
 * @returns {Promise<string[]>} console errors seen, which should stay empty
 */
async function open(page, query = '?mode=impedance') {
  /** @type {string[]} */
  const errors = [];
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  page.on('pageerror', (error) => errors.push(String(error)));
  await page.goto(`/random-wire.html${query}`);
  await page.getByRole('heading', { level: 1 }).waitFor();
  return errors;
}

/** The scored table of published lengths, as [length, average, worst, verdict]. */
async function publishedLengths(page) {
  return page.evaluate(() => {
    const table = [...document.querySelectorAll('table')].find((candidate) =>
      [...candidate.querySelectorAll('th')].some((th) =>
        th.textContent.includes('Verdict'),
      ),
    );
    return [...table.querySelectorAll('tbody tr')].map((row) =>
      [...row.cells].map((cell) => cell.textContent.trim()),
    );
  });
}

/** Which option in a group is selected, per its own ARIA state. */
const selected = (page, legend) =>
  group(page, legend).locator('button[aria-checked="true"]').first().textContent();

/** The wire length the page currently holds, in whatever unit is displayed. */
const lengthField = (page) => page.locator('input[type=number]');

/** Relative luminance of an "rgb(r, g, b)" string, per WCAG 2.1. */
function luminance(color) {
  const [r, g, b] = color.match(/\d+(\.\d+)?/g).slice(0, 3).map(Number);
  const channel = (value) => {
    const v = value / 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

/** WCAG contrast ratio between two "rgb(...)" strings. */
function contrast(foreground, background) {
  const a = luminance(foreground);
  const b = luminance(background);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

test.describe('loading', () => {
  for (const mode of ['impedance', 'classical']) {
    test(`${mode} mode loads with a clean console`, async ({ page }) => {
      const errors = await open(page, `?mode=${mode}`);
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
      expect(errors).toEqual([]);
    });
  }
});

test.describe('control groups', () => {
  // A <label> wrapping a group of buttons activates the first of them, so
  // these are fieldsets with legends instead.  A legend activates nothing.
  for (const legend of ['Ground', 'Tuner', 'Unun ratio']) {
    test(`clicking the ${legend} legend selects nothing`, async ({ page }) => {
      await open(page);
      const before = await selected(page, legend);
      await group(page, legend).locator('legend').click();
      expect(await selected(page, legend)).toBe(before);
    });
  }

  test('each group has exactly one selection', async ({ page }) => {
    await open(page);
    for (const legend of ['Units', 'Ground', 'Tuner', 'Unun ratio']) {
      await expect(
        group(page, legend).locator('button[aria-checked="true"]'),
      ).toHaveCount(1);
    }
  });
});

test.describe('the tuner decides the verdicts', () => {
  test('a length is ok exactly when its worst band is within the limit', async ({
    page,
  }) => {
    await open(page);
    for (const [button, limit] of Object.entries(TUNER_LIMITS)) {
      await option(page, 'Tuner', button).click();
      await expect(option(page, 'Tuner', button)).toHaveAttribute(
        'aria-checked',
        'true',
      );
      const rows = await publishedLengths(page);
      expect(rows.length).toBeGreaterThan(0);
      for (const [length, , worst, verdict] of rows) {
        const swr = Number.parseFloat(worst);
        // The cell is rounded to a tenth, so a worst of 5.04 reads as 5.0
        // against a 5:1 limit and the verdict cannot be predicted from the
        // display.  Skip only that sliver; everything else is decidable.
        if (Math.abs(swr - limit) <= 0.05) continue;
        expect(
          verdict,
          `${length} worst ${worst} against a ${button} tuner`,
        ).toBe(swr < limit ? 'ok' : 'poor');
      }
    }
  });

  test('a stricter tuner accepts a subset, never different lengths', async ({
    page,
  }) => {
    await open(page);
    /** @type {string[][]} */
    const accepted = [];
    for (const button of Object.keys(TUNER_LIMITS)) {
      await option(page, 'Tuner', button).click();
      await expect(option(page, 'Tuner', button)).toHaveAttribute(
        'aria-checked',
        'true',
      );
      const rows = await publishedLengths(page);
      accepted.push(rows.filter((row) => row[3] === 'ok').map((row) => row[0]));
    }
    for (let i = 1; i < accepted.length; i += 1) {
      for (const length of accepted[i - 1]) {
        expect(accepted[i], `${length} accepted by a stricter tuner`).toContain(
          length,
        );
      }
    }
  });
});

test.describe('the installation panel', () => {
  /** A labeled slider's readout, in feet. */
  const readout = async (page, label) =>
    Number.parseFloat(
      (await page.locator('label', { hasText: label }).first().textContent()).match(
        new RegExp(`${label}:\\s*([\\d.]+)\\s*ft`),
      )[1],
    );

  /** How much of the return lies on the ground, from the hint. */
  const onTheGround = async (page) =>
    Number.parseFloat(
      (await page.locator('label', { hasText: 'Counterpoise / return' }).first()
        .textContent()).match(/([\d.]+)\s*ft\s*of it lies on the ground/)[1],
    );

  const slider = (page, label) =>
    page.locator('label', { hasText: label }).first().locator('input');

  test('the preset sets the whole conductor it names', async ({ page }) => {
    await open(page);
    await page.locator('button', { hasText: /λ\/4 on/ }).first().click();
    // A quarter wave on 40 m is about 35 ft, and the control reads the whole
    // return, so the number the button names is the number that moves.
    const whole = await readout(page, 'Counterpoise / return');
    expect(whole).toBeGreaterThan(32);
    expect(whole).toBeLessThan(38);
  });

  test('every part of the return slider changes it', async ({ page }) => {
    await open(page);
    const control = slider(page, 'Counterpoise / return');
    const min = Number(await control.getAttribute('min'));
    const max = Number(await control.getAttribute('max'));
    const step = Number(await control.getAttribute('step'));
    // A range input steps from its own min, so only those values are legal,
    // and max need not land on that grid -- rounding up would overshoot it.
    const snap = (value) =>
      min + Math.floor((Math.min(value, max) - min) / step) * step;

    const seen = new Set();
    for (const fraction of [0, 0.25, 0.5, 0.75, 1]) {
      await control.fill(String(snap(min + (max - min) * fraction)));
      seen.add(await readout(page, 'Counterpoise / return'));
    }
    expect(seen.size).toBe(5);
  });

  test('the return cannot be shorter than the drop it starts with', async ({
    page,
  }) => {
    await open(page);
    const control = slider(page, 'Counterpoise / return');
    await control.fill(await control.getAttribute('min'));
    // At the floor the whole conductor is the drop and nothing is on the
    // ground, which is the coax reaching the feedpoint and going no further.
    expect(await onTheGround(page)).toBeCloseTo(0, 1);
    expect(await readout(page, 'Counterpoise / return')).toBeCloseTo(
      await readout(page, 'Wire height'),
      0,
    );
  });

  test('raising the wire lengthens the drop, not the run', async ({ page }) => {
    await open(page);
    const before = await onTheGround(page);
    await slider(page, 'Wire height').fill('25');
    expect(await onTheGround(page)).toBeCloseTo(before, 1);
  });

  test('the counterpoise cannot be raised above the feedpoint', async ({ page }) => {
    await open(page);
    const height = await readout(page, 'Wire height');
    const ceiling = Number(
      await slider(page, 'Counterpoise height').getAttribute('max'));
    // It hangs from the feedpoint, and the fit reaches half the wire height.
    expect(ceiling).toBeLessThanOrEqual(height * 0.3048 / 2 + 1e-6);
  });
});

test.describe('geometry', () => {
  const pick = (page, name) =>
    page.locator('.geometry-btn', { hasText: name });

  test('both arrangements are offered, with a picture each', async ({ page }) => {
    await open(page);
    await expect(page.locator('.geometry-btn')).toHaveCount(2);
    await expect(page.locator('.geometry-btn svg')).toHaveCount(2);
    await expect(pick(page, 'Flat top')).toHaveAttribute('aria-checked', 'true');
  });

  test('choosing a sloper swaps in its own controls', async ({ page }) => {
    await open(page);
    await expect(page.locator('label', { hasText: 'Balun height' })).toHaveCount(0);
    await pick(page, 'Sloper').click();
    await expect(pick(page, 'Sloper')).toHaveAttribute('aria-checked', 'true');
    await expect(page.locator('label', { hasText: 'Balun height' })).toHaveCount(1);
    await expect(page.locator('label', { hasText: 'Free end' })).toHaveCount(1);
  });

  test('a sloper whose wire cannot reach its support says so', async ({ page }) => {
    await open(page);
    await pick(page, 'Sloper').click();
    // The free end well above the balun, with a wire far too short to climb.
    await page.locator('label', { hasText: 'Free end' }).first().locator('input')
      .fill('25');
    await page.locator('input[type=number]').fill('10');
    await expect(page.locator('.verdict')).toContainText('does not reach');
    await expect(page.locator('.verdict')).toHaveClass(/bad/);
  });
});

test.describe('the fit\'s domain', () => {
  // The sweeps cover the whole control space, so the caveat should never
  // appear through the UI.  It is still wired up, and unit tested, for a
  // control widened past the fit or a fit narrowed under the controls.
  for (const [what, query] of [
    ['the lowest wire on the lowest band', '?mode=impedance&bands=160&h_m=1'],
    ['the highest wire on the highest band', '?mode=impedance&bands=10&h_m=30'],
    ['every band at once', '?mode=impedance&bands=160,80,40,30,20,17,15,12,10&h_m=1'],
  ]) {
    test(`${what} stays inside the fit`, async ({ page }) => {
      await open(page, `${query}&len_m=21.336`);
      await expect(page.locator('.verdict-domain')).toHaveCount(0);
    });
  }

  test('a band inside the fit says nothing', async ({ page }) => {
    await open(page, '?mode=impedance&bands=20,15&h_m=9.144&len_m=21.336');
    await expect(page.locator('.verdict-domain')).toHaveCount(0);
  });

  test('the classical rule has no domain to be outside of', async ({ page }) => {
    await open(page, '?mode=classical&bands=160&h_m=3&len_m=21.336');
    await expect(page.locator('.verdict-domain')).toHaveCount(0);
  });
});

test.describe('keyboard, in the control groups', () => {
  test('arrow keys move the selection, and wrap', async ({ page }) => {
    await open(page);
    const tuner = group(page, 'Tuner');
    const first = tuner.locator('button[role="radio"]').first();
    await first.click();
    const before = await selected(page, 'Tuner');

    await page.keyboard.press('ArrowRight');
    const after = await selected(page, 'Tuner');
    expect(after, 'right moves on').not.toBe(before);

    await page.keyboard.press('ArrowLeft');
    expect(await selected(page, 'Tuner'), 'left comes back').toBe(before);

    // The ends are not walls: the pattern wraps.
    await page.keyboard.press('ArrowLeft');
    const wrapped = await selected(page, 'Tuner');
    expect(wrapped, 'left from the first wraps to the last').not.toBe(before);
    await page.keyboard.press('End');
    expect(await selected(page, 'Tuner'), 'End is the last').toBe(wrapped);
    await page.keyboard.press('Home');
    expect(await selected(page, 'Tuner'), 'Home is the first').toBe(before);
  });

  test('a group is one tab stop, not one per option', async ({ page }) => {
    await open(page);
    const stops = await group(page, 'Tuner')
      .locator('button[role="radio"][tabindex="0"]').count();
    expect(stops, 'only the selected option is tabbable').toBe(1);
  });

  test('the length field shows a focus ring', async ({ page }) => {
    await open(page);
    await lengthField(page).focus();
    const outline = await lengthField(page).evaluate((el) => {
      const style = getComputedStyle(el);
      return `${style.outlineStyle} ${style.outlineWidth}`;
    });
    expect(outline, 'focus is visible on the input, as on the buttons')
      .not.toMatch(/none|0px/);
  });
});

test.describe('the length field', () => {
  test('a typed length survives a change of display units', async ({ page }) => {
    await open(page);
    await lengthField(page).fill('71');
    await lengthField(page).blur();
    await option(page, 'Units', 'meters').click();
    await option(page, 'Units', 'feet').click();
    expect(Number.parseFloat(await lengthField(page).inputValue())).toBeCloseTo(71, 1);
  });

  test('a partial entry does not blank the field', async ({ page }) => {
    await open(page);
    await lengthField(page).fill('5.');
    expect(await lengthField(page).inputValue()).not.toBe('');
  });
});

test.describe('URLs', () => {
  test('the page comes back the same from its own URL', async ({ page }) => {
    await open(page);
    await option(page, 'Tuner', '9:1').click();
    await option(page, 'Ground', 'Damp').click();
    await lengthField(page).fill('84');
    await lengthField(page).blur();
    await page.waitForFunction(() => window.location.search.length > 1);

    const url = page.url();
    const before = await publishedLengths(page);
    await page.goto(url);
    await page.getByRole('heading', { level: 1 }).waitFor();

    expect(await selected(page, 'Tuner')).toBe('9:1');
    expect(await selected(page, 'Ground')).toBe('Damp');
    expect(await publishedLengths(page)).toEqual(before);
  });

  test('the legacy ?len= is still read as feet', async ({ page }) => {
    await open(page, '?mode=impedance&len=70');
    const legacy = await lengthField(page).inputValue();
    await open(page, `?mode=impedance&len_m=${(70 / FEET_PER_METER).toFixed(4)}`);
    expect(Number.parseFloat(await lengthField(page).inputValue())).toBeCloseTo(
      Number.parseFloat(legacy),
      1,
    );
  });
});

test.describe('layout and legibility', () => {
  test('the experimental ribbon scrolls away with the page', async ({ page }) => {
    await open(page);
    const ribbon = page.getByText('EXPERIMENTAL').first();
    const position = await ribbon.evaluate((node) => getComputedStyle(node).position);
    expect(['fixed', 'sticky']).not.toContain(position);
  });

  test('nothing scrolls sideways at phone width', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 800 });
    await open(page);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);
  });

  test('an unselected option is still readable', async ({ page }) => {
    // The existing sweep above walks text nodes, so it never saw a button's
    // label; these were 4.22:1 against #111, under the 4.5 AA wants, and
    // being dim is what marks them unselected, so it is the state most
    // likely to be left that way.
    await open(page);
    for (const [legend, selector] of [
      ['Tuner', 'button[role="radio"][aria-checked="false"]'],
      ['Unun ratio', 'button[role="radio"][aria-checked="false"]'],
    ]) {
      const option = group(page, legend).locator(selector).first();
      const [color, background] = await option.evaluate((el) => {
        const style = getComputedStyle(el);
        return [style.color, style.backgroundColor];
      });
      expect(
        contrast(color, background),
        `${legend}, unselected: ${color} on ${background}`,
      ).toBeGreaterThanOrEqual(4.5);
    }
  });

  test('the map\'s own lines are visible against it', async ({ page }) => {
    // A graphical object rather than text, so the bar is 3.0.  The SWR
    // reference lines are the only quantitative scale on the score curve,
    // and they are drawn *over* the usable band's fill, which is lighter
    // than the panel -- so that is the background they have to clear, not
    // the one behind the map.  The geometry diagrams are not included: they
    // carry aria-hidden and the controls they sit above name themselves.
    await open(page);
    const worst = await page.locator('svg.map-svg').evaluate((svg) => {
      const rgb = (value) => value.match(/\d+(\.\d+)?/g).slice(0, 3).map(Number);
      const luminance = (value) => {
        const channel = (v) => {
          const s = v / 255;
          return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
        };
        const [r, g, b] = rgb(value);
        return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
      };
      const ratio = (a, b) => {
        const [x, y] = [luminance(a), luminance(b)];
        return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
      };
      // Every filled rectangle the lines can cross, plus the panel itself.
      // A hatched fill reads as url(#pattern) rather than a colour, and a
      // rect inside <defs> is a swatch of one rather than a surface.
      const isColour = (value) => /^rgba?\(/.test(value || '');
      const surfaces = [...svg.querySelectorAll('rect')]
        .filter((rect) => !rect.closest('defs'))
        .map((rect) => getComputedStyle(rect).fill)
        .filter(isColour);
      surfaces.push(getComputedStyle(svg.parentElement).backgroundColor);
      let lowest = Infinity;
      // Only the SWR rules: they span the plot and cross every band fill,
      // where a marker or a curve sits inside one region and comparing it
      // against the others would measure nothing.
      for (const line of svg.querySelectorAll('line.map-rule')) {
        const stroke = getComputedStyle(line).stroke;
        if (!isColour(stroke)) continue;
        for (const surface of surfaces) {
          lowest = Math.min(lowest, ratio(stroke, surface));
        }
      }
      return lowest === Infinity ? 0 : lowest;
    });
    expect(worst, 'the dimmest map line against the lightest thing it crosses')
      .toBeGreaterThanOrEqual(3.0);
  });

  test('small print stays readable against its background', async ({ page }) => {
    await open(page);
    const failures = await page.evaluate(() => {
      /** Walk up for the first ancestor that actually paints a background. */
      const backgroundOf = (node) => {
        for (let el = node; el; el = el.parentElement) {
          const color = getComputedStyle(el).backgroundColor;
          if (color && color !== 'rgba(0, 0, 0, 0)' && color !== 'transparent') {
            return color;
          }
        }
        return 'rgb(0, 0, 0)';
      };
      const out = [];
      for (const el of document.querySelectorAll('p, span, div, small, label')) {
        const style = getComputedStyle(el);
        const size = Number.parseFloat(style.fontSize);
        const text = [...el.childNodes]
          .filter((n) => n.nodeType === Node.TEXT_NODE)
          .map((n) => n.textContent.trim())
          .join('');
        if (!text || size > 13.5 || el.offsetParent === null) continue;
        out.push({ text: text.slice(0, 40), size, fg: style.color, bg: backgroundOf(el) });
      }
      return out;
    });

    expect(failures.length).toBeGreaterThan(0);
    for (const item of failures) {
      expect(
        contrast(item.fg, item.bg),
        `${item.size}px text "${item.text}"`,
      ).toBeGreaterThanOrEqual(4.5);
    }
  });
});

test.describe('keyboard', () => {
  test('a suggested length can be taken with the keyboard alone', async ({ page }) => {
    await open(page);
    // A RegExp rather than a :text-matches() string: Playwright unescapes the
    // quoted pattern in that selector, so "\d" would arrive as a literal "d".
    const suggestion = page
      .getByRole('button', { name: /^\d+(\.\d+)? ft$/ })
      .first();
    await suggestion.focus();
    await expect(suggestion).toBeFocused();
    const wanted = Number.parseFloat(await suggestion.textContent());
    await page.keyboard.press('Enter');
    expect(Number.parseFloat(await lengthField(page).inputValue())).toBeCloseTo(
      wanted,
      1,
    );
  });

  test('focus is visible on the control that has it', async ({ page }) => {
    await open(page);
    const button = option(page, 'Tuner', '9:1');
    await button.focus();
    const ring = await button.evaluate((node) => {
      const style = getComputedStyle(node);
      return {
        outlineWidth: style.outlineWidth,
        outlineStyle: style.outlineStyle,
        boxShadow: style.boxShadow,
      };
    });
    const hasRing =
      (ring.outlineStyle !== 'none' && Number.parseFloat(ring.outlineWidth) > 0) ||
      (ring.boxShadow && ring.boxShadow !== 'none');
    expect(hasRing, JSON.stringify(ring)).toBe(true);
  });
});

test.describe('the NEC check', () => {
  test('draws a measured curve and clears it when anything changes',
    async ({ page }) => {
      // CI runners solve at a fraction of a desktop's rate: the pool is
      // sized to their two cores, so give the solver real time.
      test.setTimeout(240_000);
      // Loads the solver from the CDN, so this is the one test with the
      // network in the loop beyond the page's own script tags.
      await open(page);
      await page.getByRole('button', { name: /check this map against nec-2/i })
        .click();
      const overlay = page.locator('svg.map-svg .nec-curve');
      // Drawn as soon as two lengths have solved, well before the run ends.
      await expect(overlay).toBeVisible({ timeout: 60000 });
      // Any input the numbers depend on drops the overlay -- soil is one.
      await group(page, 'Ground').locator('button[aria-checked="false"]')
        .first().click();
      await expect(overlay).toHaveCount(0);
    });
});

test.describe('the NEC check refines', () => {
  test('a run keeps its midpoints when a round offers fewer than the pool',
    async ({ page }) => {
      // A full run to completion: minutes on a two-core CI runner.
      test.setTimeout(480_000);
      // This configuration's first refinement round offers 7 midpoints
      // against a pool of up to 8 workers, which once dispatched a length
      // past the end of the queue and tore the run down mid-flight.
      await open(page, '?region=us&bands=40%2C20%2C15%2C10&seg=full'
        + '&mode=impedance&unun=9&h_m=9.144&geom=flatTop&cp_m=7.62'
        + '&cpz_m=0.01&soil=average&u=ft&len_m=24.079');
      await page.getByRole('button', { name: /check this map against nec-2/i })
        .click();
      await page.locator('.nec-check span', { hasText: 'same geometry' })
        .waitFor({ timeout: 300000 });
      const points = await page.evaluate(() => {
        const path = document.querySelector('svg.map-svg .nec-curve path');
        return path ? path.getAttribute('d').split('L').length : 0;
      });
      expect(points, 'refined midpoints survive to the drawn curve')
        .toBeGreaterThan(97);
      // The coda measured the offered lengths: the table grew a NEC-2
      // column and the verdict speaks in measured terms.
      await expect(page.locator('th', { hasText: 'NEC-2' })).toHaveCount(1);
      await expect(page.locator('.verdict-detail'))
        .toContainText('NEC-2 measures');
    });
});
