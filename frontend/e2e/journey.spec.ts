import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { expect, test } from '@playwright/test';

import { LEXICONS } from '../src/theme/lexicon';
import { MODES, enterStarterZone, openFirstExercise, register, GRADED } from './support';

const SOLUTION = readFileSync(
  resolve(
    import.meta.dirname,
    '../../content/branches/starter/exercises/first-completion/solution/ask.py',
  ),
  'utf8',
);
const WRONG = 'def ask(client, question):\n    return "no idea"\n';

for (const mode of MODES) {
  test(`a learner fails, takes a hint, passes and moves on (${mode})`, async ({ page }) => {
    const lexicon = LEXICONS[mode];
    await register(page, mode);
    await openFirstExercise(page);

    const editor = page.getByRole('textbox', { name: /code editor/i });
    const replaceCode = async (code: string) => {
      await editor.click();
      await page.keyboard.press('ControlOrMeta+A');
      await page.keyboard.insertText(code);
    };
    const results = page.getByRole('region', { name: 'Results' });

    await replaceCode(WRONG);
    await page.getByRole('button', { name: lexicon.attemptSubmit }).click();
    await expect(results.getByText(/Not yet: \d+ of \d+ checks passed/)).toBeVisible(GRADED);
    const failed = results.getByRole('listitem').filter({ hasText: 'Failed' }).first();
    await expect(failed).toBeVisible();
    await expect(failed.getByText(/\S/).last()).not.toHaveText(/^Failed$/);

    await page.getByRole('button', { name: new RegExp(lexicon.hintRevealAction, 'i') }).click();
    await expect(page.getByText(lexicon.hintConfirmCost)).toBeVisible();
    await page.getByRole('button', { name: 'Reveal anyway' }).click();
    await expect(page.getByRole('button', { name: 'Reveal anyway' })).toBeHidden();
    await expect(
      page.getByRole('button', { name: new RegExp(`${lexicon.hintRevealAction}\\s*1/2`, 'i') }),
    ).toBeVisible();

    await replaceCode(SOLUTION);
    await page.getByRole('button', { name: lexicon.attemptSubmit }).click();
    await expect(page.getByText(/\+[1-9]\d* XP/).first()).toBeVisible(GRADED);
    await expect(results.getByText(/Passed: \d+ of \d+ checks passed/)).toBeVisible(GRADED);

    await page.getByRole('link', { name: lexicon.backToMap }).click();
    // The atlas returns to the exercise's own zone, not the world.
    if (mode === 'rpg') await expect(page).toHaveURL(/[?&]zone=starter\b/);
    await enterStarterZone(page);
    await expect(
      page.getByRole('link', {
        name: new RegExp(`system prompts.*${lexicon.status.available}`, 'i'),
      }),
    ).toBeVisible();
  });
}
