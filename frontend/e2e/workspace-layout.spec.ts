import { expect, test, type Page } from '@playwright/test';

import { openFirstExercise, register } from './support';

test.use({ viewport: { width: 1440, height: 900 } });

const pageScroll = (page: Page) =>
  page.evaluate(() => ({
    overflow: document.documentElement.scrollHeight - window.innerHeight,
    scrollY: window.scrollY,
  }));

test('at 1440×900 the workspace fills the viewport and its columns scroll on their own', async ({
  page,
}) => {
  await register(page);
  await openFirstExercise(page);

  // The page itself does not scroll, so the header stays in view.
  expect((await pageScroll(page)).overflow, 'page overflow').toBeLessThanOrEqual(0);
  const header = page.getByRole('banner').first();
  await expect(header).toBeInViewport({ ratio: 1 });

  // The header's content lines up with the workspace's gutters instead of a 1200px column.
  const logo = await page.getByRole('link', { name: 'Forgeway' }).boundingBox();
  const back = await page.getByRole('link', { name: /back to/i }).boundingBox();
  expect(Math.abs((logo?.x ?? 0) - (back?.x ?? 0)), 'header and workspace align').toBeLessThan(2);

  const columns = {
    brief: page.locator('#brief'),
    editor: page.locator('#editor .cm-scroller'),
    results: page.locator('#results'),
  };
  for (const [name, column] of Object.entries(columns)) {
    const box = await column.boundingBox();
    expect(box, name).not.toBeNull();
    expect(
      (box?.y ?? 0) + (box?.height ?? 0),
      `${name} ends inside the viewport`,
    ).toBeLessThanOrEqual(900);
    expect(
      await column.evaluate((element) => getComputedStyle(element).overflowY),
      `${name} scrolls internally`,
    ).toBe('auto');
  }

  // Scrolling the brief moves the brief, not the page.
  const brief = columns.brief;
  expect(
    await brief.evaluate((element) => element.scrollHeight > element.clientHeight),
    'the brief is taller than its column',
  ).toBe(true);
  await brief.hover();
  await page.mouse.wheel(0, 600);
  await expect.poll(() => brief.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
  expect((await pageScroll(page)).scrollY, 'the page stays put').toBe(0);
  await expect(header).toBeInViewport({ ratio: 1 });
});
