import { expect, test, type Page } from '@playwright/test';

import { register } from './support';

interface MapBranch {
  id: string;
  requires: string[];
}

const branchesOf = async (page: Page): Promise<MapBranch[]> =>
  ((await (await page.request.get('/api/map')).json()) as { branches: MapBranch[] }).branches;

/** A road leaves each zone a branch requires, or the hub when it requires nothing else. */
async function expectRoadsFromTheHub(page: Page) {
  const branches = await branchesOf(page);
  const hub = branches.find((branch) => branch.requires.length === 0);
  if (hub === undefined) throw new Error('No branch without requirements');
  const map = page.getByRole('img', { name: 'The known world' });
  await expect(map).toBeVisible();
  const others = branches.filter((branch) => branch.id !== hub.id);
  expect(others.length).toBeGreaterThan(0);
  let roads = 0;
  for (const branch of others) {
    // A zone beyond another is reached from that zone; a project from every zone it requires.
    const sources = branch.requires.length > 0 ? branch.requires : [hub.id];
    for (const from of sources)
      await expect(
        map.locator(`[data-route-from="${from}"][data-route-to="${branch.id}"]`),
        `road from ${from} to ${branch.id}`,
      ).toHaveCount(1);
    roads += sources.length;
  }
  await expect(map.locator('[data-route]')).toHaveCount(roads);
}

test('the world atlas draws a road from the hub to every other zone', async ({ page }) => {
  await register(page, 'rpg');
  await expectRoadsFromTheHub(page);
});

test('the world atlas keeps its roads, and fits the screen, at 375px', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await register(page, 'rpg');
  await expectRoadsFromTheHub(page);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});
