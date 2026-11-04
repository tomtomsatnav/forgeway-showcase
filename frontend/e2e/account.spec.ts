import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

import { LEXICONS } from '../src/theme/lexicon';
import {
  PASSWORD,
  emailedToken,
  register,
  registerUnverified,
  setTheme,
  verifyEmail,
} from './support';

const pro = LEXICONS.professional;

async function serious(page: Page) {
  const { violations } = await new AxeBuilder({ page }).analyze();
  return violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map((v) => ({ id: v.id, nodes: v.nodes.map((n) => n.target.join(' ')) }));
}

test('a new learner checks their inbox, sees the banner until verified, then it goes', async ({
  page,
}) => {
  const email = await registerUnverified(page);
  expect(await serious(page), 'check your inbox').toEqual([]);
  await page.getByRole('link', { name: pro.checkInboxContinue }).click();
  const banner = page.getByRole('region', { name: 'Email verification' });
  await expect(banner).toContainText(pro.unverifiedBanner);
  expect(await serious(page), 'map with the banner').toEqual([]);

  await banner.getByRole('button', { name: pro.resendVerification }).click();
  await expect(banner).toContainText(pro.verificationResent(email));

  // Unverified learners cannot run checks; the API says why.
  const me = (await (await page.request.get('/api/auth/me')).json()) as { csrf_token: string };
  const refused = await page.request.post('/api/exercises/starter.first-completion/attempts', {
    headers: { 'X-CSRF-Token': me.csrf_token },
    data: { files: { 'ask.py': '' } },
  });
  expect(refused.status()).toBe(403);
  expect(((await refused.json()) as { code: string }).code).toBe('email-unverified');

  await verifyEmail(page, email);
  await page.getByRole('link', { name: pro.checkInboxContinue }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(pro.mapTitle);
  await expect(banner).toHaveCount(0);
});

test('a forgotten password is reset by email and every session ends', async ({ page }) => {
  await register(page);
  await setTheme(page, 'professional', 'dark');
  const { email } = (await (await page.request.get('/api/auth/me')).json()) as { email: string };
  await page.getByRole('button', { name: 'Sign out' }).click();

  await page.getByRole('link', { name: pro.forgotPassword }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(pro.forgotPasswordTitle);
  expect(await serious(page), 'forgot password').toEqual([]);
  await page.getByLabel('Email').fill(email);
  await page.getByRole('button', { name: 'Send reset link' }).click();
  await expect(page.getByRole('status')).toHaveText(pro.forgotPasswordSent);

  await page.goto(`/reset-password?token=${await emailedToken(page, email)}`);
  expect(await serious(page), 'reset password').toEqual([]);
  const fresh = 'a brand new passphrase';
  await page.getByLabel('New password').fill(fresh);
  await page.getByRole('button', { name: 'Set new password' }).click();
  await expect(page.getByRole('status')).toHaveText(pro.resetPasswordDone);

  await page.getByRole('link', { name: pro.signIn }).click();
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(PASSWORD);
  await page.getByRole('button', { name: pro.signIn }).click();
  await expect(page.getByRole('alert')).toContainText('incorrect');
  await page.getByLabel('Password').fill(fresh);
  await page.getByRole('button', { name: pro.signIn }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(pro.mapTitle);
});
