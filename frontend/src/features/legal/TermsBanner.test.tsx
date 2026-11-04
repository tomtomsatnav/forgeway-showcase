import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { useMe } from '../../api/hooks';
import type { Mode } from '../../api/types';
import { json, stubApi } from '../../test/fixtures';
import { renderInRouter, withMode } from '../../test/render';
import { LEGAL_UPDATED, TERMS_VERSION } from './LegalPages';
import { TermsBanner } from './TermsBanner';

const ME = { email: 'a@example.com', email_verified: true, csrf_token: 'csrf' };
const STALE = { ...ME, terms_current: false };
const CURRENT = { ...ME, terms_current: true };
const LEGAL =
  'By selecting “I accept”, you agree to the updated terms of use and confirm you have read the privacy policy.';

/** Appears once `me` has answered, so that "not shown" is not just "not loaded yet". */
function Settled() {
  return useMe().isSuccess ? <p>settled</p> : null;
}

const renderBanner = (mode: Mode = 'professional') =>
  renderInRouter(
    withMode(
      mode,
      <>
        <TermsBanner />
        <Settled />
        <main id="main" tabIndex={-1} />
      </>,
    ),
  );

const region = () => screen.findByRole('region', { name: 'Updated terms' });

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('TermsBanner', () => {
  it.each([
    ['professional', 'Our terms have changed.'],
    ['rpg', 'The terms of the realm have changed.'],
  ] as const)('in %s mode says what changed, with the same legal sentence', async (mode, lead) => {
    stubApi({ 'GET /api/auth/me': () => json(STALE) });
    await renderBanner(mode);

    const banner = await region();
    expect(banner).toHaveTextContent(`${lead} ${LEGAL}`);
    expect(within(banner).getByRole('link', { name: 'terms of use' })).toHaveAttribute(
      'href',
      '/terms',
    );
    expect(within(banner).getByRole('link', { name: 'privacy policy' })).toHaveAttribute(
      'href',
      '/privacy',
    );
    expect(within(banner).getByRole('button', { name: 'I accept' })).toBeEnabled();
  });

  it('is hidden once the terms are current', async () => {
    stubApi({ 'GET /api/auth/me': () => json(CURRENT) });
    await renderBanner();
    await screen.findByText('settled');
    expect(screen.queryByRole('region', { name: 'Updated terms' })).toBeNull();
  });

  it('is hidden when signed out, and fetches nothing beyond /me', async () => {
    const seen = stubApi({ 'GET /api/auth/me': () => new Response(null, { status: 401 }) });
    await renderBanner();
    await screen.findByText('settled');
    expect(screen.queryByRole('region', { name: 'Updated terms' })).toBeNull();
    expect(seen.map((request) => new URL(request.url).pathname)).toEqual(['/api/auth/me']);
  });

  it('records the acceptance with the CSRF header, then goes away', async () => {
    const seen = stubApi({
      'GET /api/auth/me': () => json(STALE),
      'POST /api/auth/terms': () => json(CURRENT),
    });
    await renderBanner();
    await userEvent.click(within(await region()).getByRole('button', { name: 'I accept' }));

    await waitFor(() => {
      expect(screen.queryByRole('region', { name: 'Updated terms' })).toBeNull();
    });
    const posts = seen.filter((request) => request.method === 'POST');
    expect(posts).toHaveLength(1);
    expect(posts[0]?.headers.get('X-CSRF-Token')).toBe('csrf');
    expect(await posts[0]?.json()).toEqual({ version: TERMS_VERSION });
    // The answer updates the cached learner: no second fetch, and focus is not lost.
    expect(seen.filter((request) => request.method === 'GET')).toHaveLength(1);
    await waitFor(() => {
      expect(screen.getByRole('main')).toHaveFocus();
    });
  });

  it('shows the error and stays when accepting fails', async () => {
    const detail = 'These terms have changed. Reload the page and read them again.';
    stubApi({
      'GET /api/auth/me': () => json(STALE),
      'POST /api/auth/terms': () =>
        new Response(JSON.stringify({ status: 422, detail, code: 'invalid-input' }), {
          status: 422,
          headers: { 'content-type': 'application/problem+json' },
        }),
    });
    await renderBanner();
    const banner = await region();
    await userEvent.click(within(banner).getByRole('button', { name: 'I accept' }));

    expect(await within(banner).findByRole('alert')).toHaveTextContent(detail);
    expect(within(banner).getByRole('button', { name: 'I accept' })).toBeEnabled();
  });
});

describe('the accepted version', () => {
  // If these drift, the API refuses every acceptance and no learner can clear the banner.
  it('is the API’s TERMS_VERSION, and the date the legal pages show', () => {
    const accounts = readFileSync(
      join(process.cwd(), '../backend/src/lattice/application/accounts.py'),
      'utf8',
    );
    expect(/^TERMS_VERSION = "(.+)"$/m.exec(accounts)?.[1]).toBe(TERMS_VERSION);
    const shown = new Date(TERMS_VERSION).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
      timeZone: 'UTC',
    });
    expect(shown).toBe(LEGAL_UPDATED);
  });
});
