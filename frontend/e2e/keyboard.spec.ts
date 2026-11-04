import { expect, test, type Page } from '@playwright/test';

import { register } from './support';

const outlineWidth = (page: Page) =>
  page.evaluate(() =>
    document.activeElement ? parseFloat(getComputedStyle(document.activeElement).outlineWidth) : 0,
  );

test('a learner reaches and opens an exercise with the keyboard alone', async ({ page }) => {
  await register(page);
  await page.locator('body').click({ position: { x: 1, y: 1 } });

  let reached = false;
  for (let presses = 0; presses < 60 && !reached; presses++) {
    await page.keyboard.press('Tab');
    expect(
      await outlineWidth(page),
      `focus visible after ${presses + 1} Tab presses`,
    ).toBeGreaterThan(0);
    reached = await page.evaluate(() =>
      /your first completion/i.test(document.activeElement?.textContent ?? ''),
    );
  }
  expect(reached, 'the first exercise link receives focus').toBe(true);

  await page.keyboard.press('Enter');
  const editor = page.getByRole('textbox', { name: /code editor/i });
  await expect(editor).toBeVisible();

  await editor.focus();
  await expect(editor).toBeFocused();
  // Tab indents inside the editor...
  await page.keyboard.press('Tab');
  await expect(editor).toBeFocused();
  // ...and Escape, then Tab, leaves it, even with the completion list open.
  await page.keyboard.type('pri');
  await expect(page.getByRole('listbox')).toBeVisible();
  await page.keyboard.press('Escape');
  await page.keyboard.press('Tab');
  await expect(editor).not.toBeFocused();
  expect(await outlineWidth(page), 'focus visible after leaving the editor').toBeGreaterThan(0);
});
