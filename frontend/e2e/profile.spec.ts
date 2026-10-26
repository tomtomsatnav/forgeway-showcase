import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

import { LEXICONS } from '../src/theme/lexicon';
import {
  MODES,
  SCHEMES,
  openFirstExercise,
  passStarterZone,
  register,
  setTheme,
  starterSolution,
  GRADED,
} from './support';

/** The class a learner who finishes the foundations can take, as each mode names it. */
const CLASS_NAME = { professional: 'Retrieval specialist', rpg: 'Loremaster' } as const;

async function openProfile(page: Page, mode: 'professional' | 'rpg') {
  await page.getByRole('link', { name: LEXICONS[mode].profile }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(LEXICONS[mode].profile);
}

async function serious(page: Page) {
  const { violations } = await new AxeBuilder({ page }).analyze();
  return violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.map((n) => n.target.join(' ')) }));
}

for (const mode of MODES) {
  const lexicon = LEXICONS[mode];

  test(`a learner sees a badge after passing the first exercise (${mode})`, async ({ page }) => {
    await register(page, mode);
    await openFirstExercise(page);

    const editor = page.getByRole('textbox', { name: /code editor/i });
    await editor.click();
    await page.keyboard.press('ControlOrMeta+A');
    await page.keyboard.insertText(starterSolution('starter.first-completion')['ask.py'] ?? '');
    await page.getByRole('button', { name: lexicon.attemptSubmit }).click();

    await expect(page.getByText(lexicon.badgeAwarded('First steps'))).toBeVisible(GRADED);
    await expect(page.getByText(lexicon.streakCurrent(1)).first()).toBeVisible();

    await page.keyboard.press('Escape');
    await openProfile(page, mode);
    const badges = page.getByRole('region', { name: lexicon.badgePlural });
    const earned = badges.getByRole('listitem').filter({ hasText: 'First steps' });
    await expect(earned).toContainText(/(Earned|Won) \d/);
    await expect(page.getByText(lexicon.streakCurrent(1)).first()).toBeVisible();
  });

  test(`a learner chooses a class and takes a talent with the keyboard (${mode})`, async ({
    page,
  }) => {
    test.setTimeout(240_000);
    await register(page, mode);
    await passStarterZone(page);
    await openProfile(page, mode);

    const name = CLASS_NAME[mode];
    await page.getByRole('button', { name: `${lexicon.pathChoose}: ${name}` }).click();
    const options = page.getByRole('region', { name: lexicon.specialisation });
    await expect(options.getByText(lexicon.pathCurrent)).toBeVisible();
    await expect(options.getByRole('heading', { name })).toBeVisible();

    // Reach the first talent's button by tabbing through the table, then take it with Enter.
    const allocate = `${lexicon.talentAllocate} Steady hands`;
    await page.getByRole('region', { name: `${lexicon.talentTree} table` }).focus();
    for (let presses = 0; presses < 12; presses++) {
      await page.keyboard.press('Tab');
      if (
        (await page.evaluate(() => document.activeElement?.getAttribute('aria-label'))) === allocate
      )
        break;
    }
    await expect(page.getByRole('button', { name: allocate })).toBeFocused();
    await page.keyboard.press('Enter');

    await expect(
      page.getByRole('button', { name: `${lexicon.talentDeallocate} Steady hands` }),
    ).toBeVisible();
    await expect(page.getByRole('status').filter({ hasText: /\d of \d/ })).not.toContainText(
      /^0 of/,
    );

    // The build survives a reload.
    await page.reload();
    await expect(
      page.getByRole('button', { name: `${lexicon.talentDeallocate} Steady hands` }),
    ).toBeVisible();
  });

  for (const scheme of SCHEMES) {
    test(`the profile has no serious accessibility violations (${mode}, ${scheme})`, async ({
      page,
    }) => {
      await register(page, mode);
      await setTheme(page, mode, scheme);
      await openProfile(page, mode);
      await expect(page.getByRole('region', { name: `${lexicon.talentTree} table` })).toBeVisible();
      expect(await serious(page), 'profile').toEqual([]);
    });
  }
}
