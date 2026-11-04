import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

import { LEXICONS } from '../src/theme/lexicon';
import { MODES, SCHEMES, openFirstExercise, register, setTheme, GRADED } from './support';

async function serious(page: Page) {
  const { violations } = await new AxeBuilder({ page }).analyze();
  return violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.map((n) => n.target.join(' ')) }));
}

for (const mode of MODES) {
  for (const scheme of SCHEMES) {
    test(`map and workspace have no serious violations (${mode}, ${scheme})`, async ({ page }) => {
      await register(page, mode);
      await setTheme(page, mode, scheme);
      expect(await serious(page), 'map').toEqual([]);

      await openFirstExercise(page);
      expect(await serious(page), 'workspace').toEqual([]);

      // Graded results are their own state: scan them too (the untouched starter code fails).
      await page.getByRole('button', { name: LEXICONS[mode].attemptSubmit }).click();
      const results = page.getByRole('region', { name: 'Results' });
      await expect(results.getByText(/\d+ of \d+ checks passed/)).toBeVisible(GRADED);
      // Let the staggered entrance finish: axe measures contrast at the current opacity.
      for (const item of await results.getByRole('listitem').all()) {
        await expect(item).toHaveCSS('opacity', '1');
      }
      expect(await serious(page), 'workspace with results').toEqual([]);
    });
  }
}
