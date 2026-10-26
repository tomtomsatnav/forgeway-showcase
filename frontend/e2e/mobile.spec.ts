import { expect, test, type Page } from '@playwright/test';

import { LEXICONS } from '../src/theme/lexicon';
import { MODES, enterStarterZone, openFirstExercise, register } from './support';

test.use({ viewport: { width: 375, height: 812 } });

/** Below 640px the profile link lives in the header menu. */
async function openProfile(page: Page, profile: string) {
  await page.getByRole('banner').getByRole('button', { name: 'Menu' }).click();
  await page.getByRole('banner').getByRole('link', { name: profile }).click();
}

const overflow = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);

for (const mode of MODES) {
  test(`nothing overflows horizontally at 375px (${mode})`, async ({ page }) => {
    await register(page, mode);
    await expect(page.getByRole('main')).toBeVisible();
    expect(await overflow(page), 'map').toBeLessThanOrEqual(0);
    await enterStarterZone(page);
    await expect(page.getByRole('link', { name: /your first completion/i })).toBeVisible();
    expect(await overflow(page), 'zone').toBeLessThanOrEqual(0);

    await openFirstExercise(page);
    expect(await overflow(page), 'workspace').toBeLessThanOrEqual(0);

    await openProfile(page, LEXICONS[mode].profile);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(LEXICONS[mode].profile);
    expect(await overflow(page), 'profile').toBeLessThanOrEqual(0);
  });

  test(`talents are stacked cards that fit the screen at 375px (${mode})`, async ({ page }) => {
    const lexicon = LEXICONS[mode];
    await register(page, mode);
    await openProfile(page, lexicon.profile);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(lexicon.profile);

    await expect(page.getByRole('table')).toHaveCount(0);
    const list = page.getByRole('region', { name: `${lexicon.talentTree} list` });
    await expect(list).toBeVisible();
    const cards = list.getByRole('listitem').filter({ has: page.locator('p') });
    const first = cards.first();
    await expect(first).toBeVisible();

    const states = Object.values(lexicon.talentState).join('|');
    for (const card of await cards.all()) {
      const box = await card.boundingBox();
      expect(box === null || box.x + box.width <= 375).toBe(true);
      // The state is in words on every card, on screen, with nothing scrolled sideways.
      await expect(card.getByText(new RegExp(`^(${states})$`))).toBeVisible();
    }
    // A locked talent has no button; an available or taken one has exactly one.
    for (const card of await cards.all()) {
      const locked = await card.getByText(lexicon.talentState.locked, { exact: true }).count();
      await expect(card.getByRole('button')).toHaveCount(locked > 0 ? 0 : 1);
    }
    expect(await overflow(page), 'profile cards').toBeLessThanOrEqual(0);
  });

  for (const width of [375, 390]) {
    test(`the header is one compact row with a menu at ${width}px (${mode})`, async ({ page }) => {
      await page.setViewportSize({ width, height: 812 });
      await register(page, mode);
      const header = page.getByRole('banner');
      await expect(header.locator('[aria-label="Your level"]')).toBeVisible();
      const menu = header.getByRole('button', { name: 'Menu' });
      await expect(menu).toHaveAttribute('aria-expanded', 'false');
      // Brand, compact level and the menu button: no taller than about 96px.
      const closed = await header.boundingBox();
      expect(closed?.height ?? Infinity).toBeLessThanOrEqual(96);
      await expect(header.getByRole('link', { name: LEXICONS[mode].profile })).toBeHidden();
      await expect(header.getByRole('button', { name: 'Sign out' })).toBeHidden();

      await menu.click();
      await expect(menu).toHaveAttribute('aria-expanded', 'true');
      const profile = header.getByRole('link', { name: LEXICONS[mode].profile });
      await expect(profile).toBeFocused();
      await expect(header.getByRole('group', { name: 'Mode' })).toBeVisible();
      await expect(header.getByRole('group', { name: 'Colour scheme' })).toBeVisible();
      await expect(header.getByRole('button', { name: 'Sign out' })).toBeVisible();
      const box = await profile.boundingBox();
      expect(box?.height ?? 0).toBeGreaterThanOrEqual(24);
      expect(await overflow(page), 'open menu').toBeLessThanOrEqual(0);

      await page.keyboard.press('Escape');
      await expect(menu).toHaveAttribute('aria-expanded', 'false');
      await expect(menu).toBeFocused();
      await expect(profile).toBeHidden();
    });
  }
}
