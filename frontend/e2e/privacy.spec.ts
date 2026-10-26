import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

import { MODES, PASSWORD, register, setTheme } from './support';

async function serious(page: Page) {
  const { violations } = await new AxeBuilder({ page }).analyze();
  return violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map((v) => ({ id: v.id, nodes: v.nodes.map((n) => n.target.join(' ')) }));
}

for (const mode of MODES) {
  test(`the privacy policy and terms are public, in ${mode} mode`, async ({ page }) => {
    await page.goto('/sign-in');
    await setTheme(page, mode, 'light');
    await page
      .getByRole('navigation', { name: 'Site' })
      .getByRole('link', { name: 'Privacy' })
      .click();
    await expect(page).toHaveURL(/\/privacy$/);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Privacy policy');
    expect(await serious(page), 'privacy policy').toEqual([]);

    await page
      .getByRole('navigation', { name: 'Site' })
      .getByRole('link', { name: 'Terms' })
      .click();
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Terms of use');
    expect(await serious(page), 'terms').toEqual([]);
  });
}

test('a learner downloads their data, then deletes their account', async ({ page }) => {
  await register(page);
  const { email } = (await (await page.request.get('/api/auth/me')).json()) as { email: string };
  await page.goto('/profile');

  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download your data' }).click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/^forgeway-data-\d{4}-\d{2}-\d{2}\.json$/);
  const path = await file.path();
  const { readFile } = await import('node:fs/promises');
  const data = JSON.parse(await readFile(path, 'utf-8')) as { account: { email: string } };
  expect(data.account.email).toBe(email);

  await page.getByRole('button', { name: 'Delete account…' }).click();
  expect(await serious(page), 'delete confirmation').toEqual([]);
  await page.getByLabel('Your password, to confirm').fill('not the password');
  await page.getByRole('button', { name: 'Delete my account for good' }).click();
  await expect(page.getByRole('alert')).toContainText('has not been deleted');

  await page.getByLabel('Your password, to confirm').fill(PASSWORD);
  await page.getByRole('button', { name: 'Delete my account for good' }).click();
  await expect(page).toHaveURL(/\/sign-in$/);

  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('alert')).toContainText('incorrect');
});
