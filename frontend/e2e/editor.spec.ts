import { expect, test, type Page } from '@playwright/test';

import { openFirstExercise, register, setTheme } from './support';

const editorOf = (page: Page) => page.getByRole('textbox', { name: /code editor/i });
const completions = (page: Page) => page.getByRole('listbox');

async function clearEditor(page: Page) {
  await editorOf(page).click();
  await page.keyboard.press('ControlOrMeta+a');
  await page.keyboard.press('Backspace');
  await expect(editorOf(page)).toHaveText('');
}

/**
 * Enter as a learner presses it at the end of a line. A completion list may have opened on the
 * last word, and Enter would accept it, so it is dismissed first.
 */
async function newline(page: Page) {
  await page.waitForTimeout(250);
  if (await completions(page).isVisible()) await page.keyboard.press('Escape');
  await page.keyboard.press('Enter');
}

test('typing a function indents and dedents as VS Code does', async ({ page }) => {
  await register(page);
  await openFirstExercise(page);
  await clearEditor(page);

  const type = (text: string) => page.keyboard.type(text);
  await type('def total(items):');
  await newline(page);
  await type('count = 0');
  await newline(page);
  await type('for item in items:');
  await newline(page);
  await type('if item:');
  await newline(page);
  await type('count += 1');
  await newline(page);
  await type('else:'); // dedents as the colon is typed
  await newline(page);
  await type('continue');
  await newline(page); // dedents after continue
  await page.keyboard.press('Shift+Tab');
  await type('return count');
  await newline(page); // dedents after return, to the top level
  await type('print(total([1, 0])'); // the closing brackets were inserted with the opening ones

  const expected = [
    'def total(items):',
    '    count = 0',
    '    for item in items:',
    '        if item:',
    '            count += 1',
    '        else:',
    '            continue',
    '    return count',
    'print(total([1, 0]))',
  ];
  await expect(editorOf(page)).toHaveText(expected.join('\n'), { useInnerText: true });

  // Tab and Shift+Tab indent and dedent the line.
  await page.keyboard.press('Tab');
  await expect(editorOf(page)).toContainText('\n    print(total', { useInnerText: true });
  await page.keyboard.press('Shift+Tab');
  await expect(editorOf(page)).toHaveText(expected.join('\n'), { useInnerText: true });

  // The documented way out still works.
  await page.keyboard.press('Escape');
  await page.keyboard.press('Tab');
  await expect(editorOf(page)).not.toBeFocused();
});

/** The element's background is the token's colour, not CodeMirror's built-in grey. */
async function expectTokenBackground(page: Page, selector: string, token: string) {
  const [actual, wanted] = await page.evaluate(
    ([target, name]) => {
      const probe = document.body.appendChild(document.createElement('div'));
      probe.style.backgroundColor = `var(${name})`;
      const colours = [
        getComputedStyle(document.querySelector(target) ?? document.body).backgroundColor,
        getComputedStyle(probe).backgroundColor,
      ];
      probe.remove();
      return colours;
    },
    [selector, token] as const,
  );
  expect(actual, `${selector} uses ${token}`).toBe(wanted);
}

test('kit completion is keyboard operable and hovers explain the symbol', async ({ page }) => {
  await register(page);
  await setTheme(page, 'rpg', 'dark');
  await openFirstExercise(page);
  await clearEditor(page);

  await page.keyboard.type('n = count_tok');
  await expect(completions(page).getByRole('option', { name: /count_tokens/ })).toBeVisible();
  await expectTokenBackground(page, '.cm-tooltip-autocomplete', '--surface-raised');
  await expectTokenBackground(page, '.cm-tooltip-autocomplete li[aria-selected]', '--accent');
  // CodeMirror ignores Enter for 75 ms after the list opens (`interactionDelay`), so a key
  // pressed in passing does not pick a completion; wait it out as a person would.
  await page.waitForTimeout(150);
  await page.keyboard.press('Enter');
  await expect(editorOf(page)).toHaveText('n = count_tokens', { useInnerText: true });

  // Point at the word itself: the line box is far wider than its text.
  const word = await page.evaluate(() => {
    const walker = document.createTreeWalker(document.querySelector('.cm-content') ?? document);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const at = node.nodeType === Node.TEXT_NODE ? (node.textContent ?? '').indexOf('count') : -1;
      if (at < 0) continue;
      const range = document.createRange();
      range.setStart(node, at + 2);
      range.setEnd(node, at + 3);
      const { x, y, width, height } = range.getBoundingClientRect();
      return { x: x + width / 2, y: y + height / 2 };
    }
    return null;
  });
  expect(word, 'count_tokens is on screen').not.toBeNull();
  await page.mouse.move(word?.x ?? 0, word?.y ?? 0);
  const hover = page.locator('.cm-tooltip-hover');
  await expect(hover).toContainText('def count_tokens(text: str) -> int');
  await expect(hover).toContainText('Number of tokens in text.');
  expect(await hover.locator('[tabindex]').count(), 'the hover holds nothing focusable').toBe(0);
  await expectTokenBackground(page, '.cm-tooltip-hover', '--surface-raised');

  // Find and replace opens on the keyboard, themed, and Escape returns to the code.
  await editorOf(page).focus();
  await page.keyboard.press('ControlOrMeta+f');
  await expect(page.getByRole('textbox', { name: 'Find' })).toBeFocused();
  await expectTokenBackground(page, '.cm-panels', '--surface-sunken');
  await page.keyboard.press('Escape');
  await expect(editorOf(page)).toBeFocused();
});
