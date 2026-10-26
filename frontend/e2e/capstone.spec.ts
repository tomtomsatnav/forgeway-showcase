import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

import { LEXICONS } from '../src/theme/lexicon';
import {
  MODES,
  SCHEMES,
  findCapstone,
  openTrack,
  registerPro,
  setTheme,
  type CapstoneRef,
} from './support';

const NO_CAPSTONE = 'The content has no capstone; every non-root branch should close with one.';

async function serious(page: Page) {
  const { violations } = await new AxeBuilder({ page }).analyze();
  return violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.map((n) => n.target.join(' ')) }));
}

test.describe('capstone', () => {
  /** Register a Pro learner (capstones are Pro), then find a capstone; undefined means skip. */
  async function arrive(
    page: Page,
    mode: (typeof MODES)[number],
  ): Promise<CapstoneRef | undefined> {
    await registerPro(page, mode);
    const capstone = await findCapstone(page);
    test.skip(capstone === undefined, NO_CAPSTONE);
    return capstone;
  }

  test('the lair is the last waypoint of its zone, with the real title (rpg)', async ({ page }) => {
    const capstone = await arrive(page, 'rpg');
    if (capstone === undefined) return;

    await page.goto(`/?zone=${capstone.branchId}`);
    const lair = page.locator(`[data-lair][href="/exercises/${capstone.exerciseId}"]`);
    await expect(lair).toBeVisible();
    await expect(lair).toContainText(capstone.title);
    await expect(lair).toContainText(LEXICONS.rpg.tier.capstone);
    // A Pro learner has everything open (ADR 0011), so the lair awaits from the start.
    await expect(lair).toContainText(LEXICONS.rpg.capstoneState.available);
    if (capstone.boss !== undefined) await expect(lair).toContainText(capstone.boss);
    // Last in route order, so last in the accessible list too.
    const links = page.getByRole('region').getByRole('link');
    await expect(links.last()).toHaveAttribute('href', `/exercises/${capstone.exerciseId}`);
  });

  test('the capstone row is framed as a capstone project (professional)', async ({ page }) => {
    const capstone = await arrive(page, 'professional');
    if (capstone === undefined) return;

    await page.goto('/');
    await openTrack(page, capstone.branchId);
    const track = page.locator(`#track-${capstone.branchId}`);
    await expect(
      track.getByText(LEXICONS.professional.capstoneLabel, { exact: true }).first(),
    ).toBeVisible();
    await expect(track.getByRole('link', { name: new RegExp(capstone.title) })).toContainText(
      LEXICONS.professional.tier.capstone,
    );
  });

  for (const mode of MODES) {
    test(`the workspace header frames the capstone (${mode})`, async ({ page }) => {
      const capstone = await arrive(page, mode);
      if (capstone === undefined) return;

      await page.goto(`/exercises/${capstone.exerciseId}`);
      const lexicon = LEXICONS[mode];
      await expect(page.getByText(lexicon.capstoneLabel, { exact: true })).toBeVisible();
      // The real title stays visible whatever leads.
      await expect(page.getByText(capstone.title, { exact: true }).first()).toBeVisible();
      if (mode === 'rpg' && capstone.boss !== undefined)
        await expect(page.getByRole('heading', { level: 1 })).toHaveText(capstone.boss);
    });
  }

  for (const mode of MODES) {
    for (const scheme of SCHEMES) {
      test(`a zone with a lair has no serious violations (${mode}, ${scheme})`, async ({
        page,
      }) => {
        const capstone = await arrive(page, mode);
        if (capstone === undefined) return;
        await setTheme(page, mode, scheme);

        await page.goto(`/?zone=${capstone.branchId}`);
        if (mode === 'professional') await openTrack(page, capstone.branchId);
        await expect(
          mode === 'rpg'
            ? page.locator(`[data-lair][href="/exercises/${capstone.exerciseId}"]`)
            : page
                .locator(`#track-${capstone.branchId}`)
                .getByText(LEXICONS.professional.capstoneLabel, { exact: true })
                .first(),
        ).toBeVisible();
        expect(await serious(page), 'zone').toEqual([]);

        await page.goto(`/exercises/${capstone.exerciseId}`);
        await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
        expect(await serious(page), 'capstone workspace').toEqual([]);
      });
    }
  }
});
