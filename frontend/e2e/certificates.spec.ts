import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

import { LEXICONS } from '../src/theme/lexicon';
import { MODES, SCHEMES, passStarterZone, register, registerPro, setTheme } from './support';

interface CertificateJson {
  id: string;
  public_url: string;
  branch_title: string;
}

async function certificates(page: Page): Promise<CertificateJson[]> {
  const body = (await (await page.request.get('/api/certificates')).json()) as {
    certificates: CertificateJson[];
  };
  return body.certificates;
}

async function openCertificates(page: Page, mode: 'professional' | 'rpg') {
  await page.getByRole('link', { name: LEXICONS[mode].profile }).click();
  const section = page.getByRole('region', { name: LEXICONS[mode].certificatesHeading });
  await expect(section).toBeVisible();
  return section;
}

for (const mode of MODES) {
  const lexicon = LEXICONS[mode];

  test(`a learner publishes the Foundations certificate and shares it (${mode})`, async ({
    page,
    context,
  }) => {
    test.setTimeout(240_000);
    await registerPro(page, mode); // publishing a certificate is Pro
    await passStarterZone(page);
    const section = await openCertificates(page, mode);

    const card = section.getByRole('listitem').filter({ hasText: 'Foundations' });
    await expect(card.getByRole('radio', { name: 'Private' })).toBeChecked();
    await expect(card.getByText(/makes a verification page public/)).toBeVisible();
    await expect(card.getByRole('link')).toHaveCount(0);

    // Rename inline, then publish.
    const name = 'Zoë Müller & Co <b>';
    await card.getByLabel('Name on the certificate').fill(name);
    await card.getByRole('button', { name: 'Save name' }).click();
    await expect(card.getByText('Name saved.')).toBeVisible();
    await card.getByRole('radio', { name: 'Public' }).check();
    await expect(card.getByRole('link', { name: /View certificate/ })).toBeVisible();

    const [certificate] = await certificates(page);
    if (certificate === undefined) throw new Error('No certificate was issued');

    // LinkedIn: both links open in a new tab and carry the API's public URL.
    const add = card.getByRole('link', { name: /Add to LinkedIn profile/ });
    const addUrl = new URL((await add.getAttribute('href')) ?? '');
    expect(`${addUrl.origin}${addUrl.pathname}`).toBe('https://www.linkedin.com/profile/add');
    expect(Object.fromEntries(addUrl.searchParams)).toMatchObject({
      startTask: 'CERTIFICATION_NAME',
      organizationName: 'Forgeway',
      certUrl: certificate.public_url,
      certId: certificate.id,
    });
    expect(addUrl.searchParams.get('name')).toContain('Foundations');
    const share = card.getByRole('link', { name: /Share on LinkedIn/ });
    expect(await share.getAttribute('href')).toBe(
      `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(certificate.public_url)}`,
    );
    for (const link of [add, share]) {
      await expect(link).toHaveAttribute('target', '_blank');
      await expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    }

    // The thumbnail is the real PNG.
    const thumbnail = card.getByRole('img', { name: new RegExp(`awarded to ${name}`) });
    await expect(thumbnail).toHaveAttribute('src', `/c/${certificate.id}.png`);
    await expect
      .poll(() => thumbnail.evaluate((img: HTMLImageElement) => img.naturalWidth))
      .toBeGreaterThan(0);

    // The verification page shows the recipient (escaped) and carries OpenGraph tags.
    const [popup] = await Promise.all([
      context.waitForEvent('page'),
      card.getByRole('link', { name: /View certificate/ }).click(),
    ]);
    await popup.waitForLoadState();
    expect(new URL(popup.url()).pathname).toBe(`/c/${certificate.id}`);
    await expect(popup.getByRole('heading', { level: 1 })).toHaveText(name);
    await expect(popup.locator('meta[property="og:title"]')).toHaveAttribute(
      'content',
      expect.stringContaining(name),
    );
    await expect(popup.locator('meta[property="og:image"]')).toHaveAttribute(
      'content',
      expect.stringContaining(`/c/${certificate.id}.png`),
    );
    await popup.close();

    // Unpublishing takes the actions away again and the page goes private.
    await card.getByRole('radio', { name: 'Private' }).check();
    await expect(card.getByRole('link')).toHaveCount(0);
    expect((await page.request.get(`/c/${certificate.id}`)).status()).toBe(404);
  });

  test(`the certificates anchor on the profile scrolls into view (${mode})`, async ({ page }) => {
    // The announcements link here (unit-tested); the target must exist and be scrolled to.
    test.setTimeout(240_000);
    await register(page, mode);
    await passStarterZone(page);
    await page.goto('/profile#certificates');
    await expect(page.getByRole('region', { name: lexicon.certificatesHeading })).toBeInViewport();
  });

  test(`the certificates section has no serious accessibility violations in light and dark (${mode})`, async ({
    page,
  }) => {
    test.setTimeout(240_000);
    await registerPro(page, mode); // publishing a certificate is Pro
    await passStarterZone(page);
    const section = await openCertificates(page, mode);
    const card = section.getByRole('listitem').filter({ hasText: 'Foundations' });
    await card.getByRole('radio', { name: 'Public' }).check();
    await expect(card.getByRole('link', { name: /View certificate/ })).toBeVisible();
    await card.getByRole('button', { name: 'Copy link' }).click();

    for (const scheme of SCHEMES) {
      await setTheme(page, mode, scheme);
      // Controls fade between palettes, so retry until the colours have settled.
      await expect
        .poll(
          async () => {
            const { violations } = await new AxeBuilder({ page })
              .include('#certificates')
              .analyze();
            return violations
              .filter((v) => v.impact === 'serious' || v.impact === 'critical')
              .map((v) => ({ id: v.id, nodes: v.nodes.map((n) => n.target.join(' ')) }));
          },
          { message: `certificates (${mode}, ${scheme})`, timeout: 5_000 },
        )
        .toEqual([]);
    }
  });
}
