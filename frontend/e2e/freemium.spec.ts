import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

import { LEXICONS } from '../src/theme/lexicon';
import { MODES, SCHEMES, findCapstone, register, setTheme } from './support';

async function serious(page: Page) {
  const { violations } = await new AxeBuilder({ page }).analyze();
  return violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.map((n) => n.target.join(' ')) }));
}

for (const mode of MODES) {
  const lexicon = LEXICONS[mode];

  test(`a free learner sees the Pro call to action on a capstone and joins the waitlist (${mode})`, async ({
    page,
  }) => {
    await register(page, mode);
    const capstone = await findCapstone(page);
    test.skip(capstone === undefined, 'The content has no capstone.');
    if (capstone === undefined) return;

    // The map marks it as Pro.
    await page.goto(mode === 'rpg' ? `/?zone=${capstone.branchId}` : '/');
    await expect(page.locator(`a[href="/exercises/${capstone.exerciseId}"]`).first()).toContainText(
      lexicon.proMark,
    );

    await page.goto(`/exercises/${capstone.exerciseId}`);
    const cta = page.getByRole('complementary', { name: lexicon.proCtaTitle });
    await expect(cta).toBeVisible();
    // The brief is there to read; there is nothing to run.
    await expect(page.getByRole('region', { name: 'Brief' })).not.toBeEmpty();
    await expect(page.getByRole('button', { name: lexicon.attemptSubmit })).toHaveCount(0);

    await cta.getByRole('button', { name: lexicon.proJoin }).click();
    await expect(cta.getByRole('status')).toHaveText(lexicon.proJoined);
    const waitlist = (await (await page.request.get('/api/pro/waitlist')).json()) as {
      joined: boolean;
    };
    expect(waitlist.joined).toBe(true);

    // The server refuses an attempt too, whatever the page shows.
    const me = (await (await page.request.get('/api/auth/me')).json()) as { csrf_token: string };
    const refused = await page.request.post(`/api/exercises/${capstone.exerciseId}/attempts`, {
      headers: { 'X-CSRF-Token': me.csrf_token },
      data: { files: {} },
    });
    expect(refused.status()).toBe(403);
    expect(((await refused.json()) as { code: string }).code).toBe('plan-required');

    // The Pro page remembers.
    await cta.getByRole('link', { name: lexicon.proLearnMore }).click();
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(lexicon.proPageTitle);
    await expect(page.getByRole('status')).toHaveText(lexicon.proJoined);
  });

  test(`the unread dot shows until What's new is opened (${mode})`, async ({ page }) => {
    await register(page, mode);
    const link = page.getByRole('banner').getByRole('link', { name: new RegExp(lexicon.whatsNew) });
    await expect(link).toHaveAttribute('data-unread', '');
    await expect(link).toHaveAccessibleName(
      new RegExp(`^${lexicon.whatsNew}\\s*, ${lexicon.whatsNewUnread}$`),
    );

    await link.click();
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(lexicon.whatsNew);
    await expect(page.getByRole('heading', { level: 2 }).first()).toBeVisible();
    await expect(link).not.toHaveAttribute('data-unread');

    await page.reload();
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(lexicon.whatsNew);
    await expect(
      page.getByRole('banner').getByRole('link', { name: lexicon.whatsNew, exact: true }),
    ).not.toHaveAttribute('data-unread');
  });

  for (const scheme of SCHEMES) {
    test(`/pro and What's new have no serious violations (${mode}, ${scheme})`, async ({
      page,
    }) => {
      await register(page, mode);
      await setTheme(page, mode, scheme);
      // The pages below are full loads, so wait for the server to have the new theme.
      await expect
        .poll(async () => {
          const me = (await (await page.request.get('/api/auth/me')).json()) as {
            profile: { mode: string; colour_scheme: string };
          };
          return `${me.profile.mode} ${me.profile.colour_scheme}`;
        })
        .toBe(`${mode} ${scheme}`);

      await page.goto('/pro');
      await expect(page.getByRole('heading', { level: 1 })).toHaveText(lexicon.proPageTitle);
      await expect(page.getByRole('button', { name: lexicon.proJoin })).toBeVisible();
      expect(await serious(page), '/pro').toEqual([]);

      await page.goto('/whats-new');
      await expect(page.getByRole('heading', { level: 2 }).first()).toBeVisible();
      expect(await serious(page), "what's new").toEqual([]);
    });
  }
}
