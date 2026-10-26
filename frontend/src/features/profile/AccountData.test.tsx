import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { json, problem, stubApi } from '../../test/fixtures';
import { renderInRouter, withMode } from '../../test/render';
import { AccountData } from './AccountData';

const EXPORT = {
  format: 'forgeway-account-export',
  version: 1,
  exported_at: '2026-10-26T09:30:00+00:00',
  account: { email: 'ada@example.com' },
  profile: null,
  sessions: [],
  emailed_links: [],
  attempts: [],
  drafts: [],
  exercise_progress: [],
  xp_events: [],
  talents: [],
  badges: [],
  certificates: [],
  waitlist: null,
  rate_limit_records: [],
};

const mount = () =>
  renderInRouter(withMode('professional', <AccountData />), undefined, '/profile');

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('your data', () => {
  it('downloads the export as a dated JSON file', async () => {
    stubApi({ 'GET /api/account/export': () => json(EXPORT) });
    const created = vi.fn(() => 'blob:export');
    URL.createObjectURL = created;
    URL.revokeObjectURL = vi.fn();
    const saved: { download: string; href: string }[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      saved.push({ download: this.download, href: this.href });
    });
    await mount();

    await userEvent.click(screen.getByRole('button', { name: 'Download your data' }));

    await waitFor(() => {
      expect(saved).toEqual([{ download: 'forgeway-data-2026-10-26.json', href: 'blob:export' }]);
    });
    expect(created).toHaveBeenCalledOnce();
    expect(screen.getByRole('link', { name: 'privacy policy' })).toHaveAttribute(
      'href',
      '/privacy',
    );
  });

  it('shows why an export was refused', async () => {
    stubApi({
      'GET /api/account/export': () =>
        problem(429, 'You have downloaded your data several times this hour.', 'rate-limited'),
    });
    await mount();

    await userEvent.click(screen.getByRole('button', { name: 'Download your data' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('several times this hour');
  });
});

describe('deleting the account', () => {
  it('asks for the password in a second step, and can be called off', async () => {
    stubApi({});
    await mount();

    await userEvent.click(screen.getByRole('button', { name: 'Delete account…' }));
    expect(screen.getByLabelText('Your password, to confirm')).toHaveFocus();
    expect(screen.getByRole('button', { name: 'Delete my account for good' })).toBeDisabled();

    await userEvent.click(screen.getByRole('button', { name: 'Keep my account' }));
    expect(screen.queryByLabelText('Your password, to confirm')).not.toBeInTheDocument();
  });

  it('sends the password and leaves for the sign-in page', async () => {
    const seen = stubApi({
      'POST /api/account/delete': () => new Response(null, { status: 204 }),
    });
    const { router } = await mount();

    await userEvent.click(screen.getByRole('button', { name: 'Delete account…' }));
    await userEvent.type(screen.getByLabelText('Your password, to confirm'), 'correct horse');
    await userEvent.click(screen.getByRole('button', { name: 'Delete my account for good' }));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/sign-in');
    });
    const sent = seen.find((request) => request.url.endsWith('/api/account/delete'));
    expect(await sent?.json()).toEqual({ password: 'correct horse' });
  });

  it('says so when the password is wrong, and keeps the account', async () => {
    stubApi({
      'POST /api/account/delete': () =>
        problem(
          422,
          'That password is incorrect, so your account has not been deleted.',
          'invalid-input',
        ),
    });
    const { router } = await mount();

    await userEvent.click(screen.getByRole('button', { name: 'Delete account…' }));
    await userEvent.type(screen.getByLabelText('Your password, to confirm'), 'wrong');
    await userEvent.click(screen.getByRole('button', { name: 'Delete my account for good' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('has not been deleted');
    expect(router.state.location.pathname).toBe('/profile');
  });
});
