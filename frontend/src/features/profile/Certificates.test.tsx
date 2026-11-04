import { useQuery } from '@tanstack/react-query';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { Certificate, Mode } from '../../api/types';
import { queryKeys } from '../../api/hooks';
import { CERTIFICATE, json, problem, stubApi } from '../../test/fixtures';
import { newQueryClient, QueryWrapper, renderInRouter, withMode } from '../../test/render';
import { Certificates } from './Certificates';

const PUBLIC: Certificate = {
  ...CERTIFICATE,
  is_public: true,
  published_at: '2026-10-25T10:00:00Z',
};

/** Renders the list from the query cache, so a PATCH answer visibly replaces its certificate. */
function mount(certificates: Certificate[], mode: Mode = 'professional') {
  const client = newQueryClient();
  client.setQueryData(queryKeys.certificates, { certificates });
  // A learner with Pro, who may publish; the free plan is covered with a router further down.
  client.setQueryData(queryKeys.me, { plan: 'pro', csrf_token: 'x' });
  function Harness() {
    const { data } = useQuery<{ certificates: Certificate[] }>({
      queryKey: queryKeys.certificates,
      queryFn: () => Promise.reject(new Error('seeded')),
      staleTime: Infinity,
    });
    return <Certificates certificates={data?.certificates ?? []} />;
  }
  return render(<QueryWrapper client={client}>{withMode(mode, <Harness />)}</QueryWrapper>);
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe('certificates', () => {
  it.each([
    ['professional', 'No certificates yet. Complete a track to earn its certificate.'],
    ['rpg', 'No seals yet. Complete a zone to earn its certificate.'],
  ] as const)('says what earns the first one (%s)', (mode, text) => {
    mount([], mode);

    expect(screen.getByText(text)).toBeVisible();
  });

  it.each(['professional', 'rpg'] as const)(
    'says a certificate included its capstone project, and only then (%s)',
    (mode) => {
      mount([{ ...CERTIFICATE, includes_capstone: true }], mode);
      expect(screen.getByText('10, including its capstone project')).toBeVisible();
      cleanup();

      mount([CERTIFICATE], mode);
      expect(screen.queryByText(/capstone/)).not.toBeInTheDocument();
    },
  );

  it('shows a private certificate with its facts and no sharing actions', () => {
    mount([CERTIFICATE]);

    expect(screen.getByRole('heading', { level: 3, name: 'Foundations' })).toBeVisible();
    expect(screen.getByText('25 October 2026')).toBeVisible();
    expect(screen.getByText('10')).toBeVisible();
    expect(screen.getByText('cert_abc-123')).toBeVisible();
    expect(screen.getByLabelText('Name on the certificate')).toHaveValue('Ada Lovelace');
    expect(screen.getByRole('radio', { name: 'Private' })).toBeChecked();
    expect(screen.getByText(/Sharing it makes a verification page public/)).toBeVisible();
    expect(screen.getByText(/Make this certificate public to view it/)).toBeVisible();
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Copy link' })).not.toBeInTheDocument();
  });

  it('offers the public page, LinkedIn links and a thumbnail once public', () => {
    mount([PUBLIC]);

    const view = screen.getByRole('link', { name: /View certificate/ });
    expect(view).toHaveAttribute('href', '/c/cert_abc-123');
    expect(view).toHaveAttribute('target', '_blank');
    expect(view).toHaveAttribute('rel', expect.stringContaining('noopener'));

    const add = screen.getByRole('link', { name: /Add to LinkedIn profile/ });
    const href = new URL(add.getAttribute('href') ?? '');
    expect(href.origin + href.pathname).toBe('https://www.linkedin.com/profile/add');
    expect(href.searchParams.get('certId')).toBe('cert_abc-123');
    expect(href.searchParams.get('issueMonth')).toBe('10');
    const share = screen.getByRole('link', { name: /Share on LinkedIn/ });
    expect(share).toHaveAttribute(
      'href',
      'https://www.linkedin.com/sharing/share-offsite/?url=https%3A%2F%2Fforgeway.example%2Fc%2Fcert_abc-123',
    );
    for (const link of [add, share]) {
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    }

    const image = screen.getByRole('img', {
      name: 'Certificate of completion for the Foundations track, awarded to Ada Lovelace',
    });
    expect(image).toHaveAttribute('src', '/c/cert_abc-123.png');
    expect(screen.getByText(/Anyone with the link can see/)).toBeVisible();
  });

  it('publishes through the switch and then shows the actions', async () => {
    const seen = stubApi({
      'PATCH /api/certificates/cert_abc-123': () => json(PUBLIC),
    });
    mount([CERTIFICATE]);

    await userEvent.setup().click(screen.getByRole('radio', { name: 'Public' }));

    expect(await screen.findByRole('link', { name: /Share on LinkedIn/ })).toBeVisible();
    expect(screen.getByRole('radio', { name: 'Public' })).toBeChecked();
    expect(await seen[0]?.json()).toEqual({ is_public: true });
  });

  it('shows a failed publish as an alert and stays private', async () => {
    stubApi({
      'PATCH /api/certificates/cert_abc-123': () => problem(500, 'The store is down.', 'server'),
    });
    mount([CERTIFICATE]);

    await userEvent.setup().click(screen.getByRole('radio', { name: 'Public' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('The store is down.');
    expect(screen.getByRole('radio', { name: 'Private' })).toBeChecked();
  });

  describe('renaming', () => {
    it('saves a trimmed name with PATCH and confirms it', async () => {
      const seen = stubApi({
        'PATCH /api/certificates/cert_abc-123': () =>
          json({ ...CERTIFICATE, recipient_name: 'Grace Hopper' }),
      });
      const user = userEvent.setup();
      mount([CERTIFICATE]);

      const field = screen.getByLabelText('Name on the certificate');
      const save = screen.getByRole('button', { name: 'Save name' });
      expect(save).toBeDisabled();
      await user.clear(field);
      await user.type(field, '  Grace Hopper ');
      await user.click(save);

      expect(await screen.findByText('Name saved.')).toBeVisible();
      expect(await seen[0]?.json()).toEqual({ recipient_name: 'Grace Hopper' });
    });

    it('refuses an empty name and one over 60 characters, saying why', async () => {
      const seen = stubApi({});
      const user = userEvent.setup();
      mount([CERTIFICATE]);
      const field = screen.getByLabelText('Name on the certificate');
      const save = screen.getByRole('button', { name: 'Save name' });

      await user.clear(field);
      expect(field).toBeInvalid();
      expect(field).toHaveAccessibleDescription('Enter the name to show on the certificate.');
      expect(save).toBeDisabled();

      await user.clear(field);
      await user.type(field, 'x'.repeat(61));
      expect(field).toHaveAccessibleDescription('Use 60 characters or fewer.');
      expect(save).toBeDisabled();

      await user.clear(field);
      await user.type(field, 'x'.repeat(60));
      expect(field).toBeValid();
      expect(save).toBeEnabled();
      expect(seen).toHaveLength(0);
    });

    it('shows a server refusal as an alert', async () => {
      stubApi({
        'PATCH /api/certificates/cert_abc-123': () =>
          problem(422, 'recipient_name: not allowed', 'invalid-input'),
      });
      const user = userEvent.setup();
      mount([CERTIFICATE]);

      const field = screen.getByLabelText('Name on the certificate');
      await user.type(field, 'x');
      await user.click(screen.getByRole('button', { name: 'Save name' }));

      expect(await screen.findByRole('alert')).toHaveTextContent('recipient_name: not allowed');
    });
  });

  describe('copying the link', () => {
    it('copies the public URL and confirms in a polite live region', async () => {
      const user = userEvent.setup();
      mount([PUBLIC]);
      const writeText = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue();

      await user.click(screen.getByRole('button', { name: 'Copy link' }));

      expect(writeText).toHaveBeenCalledWith('https://forgeway.example/c/cert_abc-123');
      const live = await screen.findByText('Link copied.');
      expect(live).toHaveAttribute('role', 'status');
    });

    it('selects the link for copying by hand when the browser refuses', async () => {
      const user = userEvent.setup();
      mount([PUBLIC]);
      vi.spyOn(navigator.clipboard, 'writeText').mockRejectedValue(new Error('denied'));

      await user.click(screen.getByRole('button', { name: 'Copy link' }));

      const field = await screen.findByRole('textbox', { name: 'Certificate link' });
      expect(field).toHaveValue('https://forgeway.example/c/cert_abc-123');
      await waitFor(() => {
        expect(field).toHaveFocus();
      });
      expect(screen.getByText(/Your browser blocked copying/)).toHaveAttribute('role', 'status');
    });

    it('falls back the same way when there is no clipboard API', async () => {
      const user = userEvent.setup();
      mount([PUBLIC]);
      Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true });

      await user.click(screen.getByRole('button', { name: 'Copy link' }));

      expect(await screen.findByRole('textbox', { name: 'Certificate link' })).toBeVisible();
    });
  });

  describe('on the free plan', () => {
    it.each([
      ['professional', /part of Forgeway Pro/, /With Forgeway Pro, a public certificate/],
      ['rpg', /for guild members/, /guild member’s public seal/],
    ] as const)(
      'marks publishing as Pro with a waitlist link, before the learner tries (%s)',
      async (mode, publish, actions) => {
        stubApi({
          'GET /api/auth/me': () => json({ plan: 'free', csrf_token: 'x' }),
        });
        await renderInRouter(withMode(mode, <Certificates certificates={[CERTIFICATE]} />));

        expect(await screen.findByText(publish)).toBeVisible();
        expect(document.querySelector('[data-pro-mark]')).not.toBeNull();
        expect(screen.getByRole('link', { name: 'Join the waitlist' })).toHaveAttribute(
          'href',
          '/pro',
        );
        expect(screen.getByText(actions)).toBeVisible();
        expect(screen.queryByText(/Make this certificate public to view it/)).toBeNull();
      },
    );

    it('disables the Public choice with the reason attached, but keeps Private open', async () => {
      stubApi({
        'GET /api/auth/me': () => json({ plan: 'free', email_verified: false, csrf_token: 'x' }),
      });
      await renderInRouter(withMode('professional', <Certificates certificates={[CERTIFICATE]} />));

      const publicChoice = await screen.findByRole('radio', { name: 'Public' });
      await waitFor(() => {
        expect(publicChoice).toBeDisabled();
      });
      expect(publicChoice).toHaveAccessibleDescription(
        /Verify your email address before you make a certificate public\..*part of Forgeway Pro/,
      );
      expect(screen.getByRole('radio', { name: 'Private' })).toBeEnabled();
    });

    it('names only the verification for an unverified learner who already has Pro', async () => {
      stubApi({
        'GET /api/auth/me': () => json({ plan: 'pro', email_verified: false, csrf_token: 'x' }),
      });
      await renderInRouter(withMode('rpg', <Certificates certificates={[CERTIFICATE]} />));

      const publicChoice = await screen.findByRole('radio', { name: 'Public' });
      await waitFor(() => {
        expect(publicChoice).toBeDisabled();
      });
      expect(publicChoice).toHaveAccessibleDescription(
        'Confirm your messenger address before you show a seal to the world.',
      );
    });

    it('leaves Public open for a verified learner on Pro, and for a public certificate', async () => {
      stubApi({
        'GET /api/auth/me': () => json({ plan: 'pro', email_verified: true, csrf_token: 'x' }),
      });
      await renderInRouter(withMode('professional', <Certificates certificates={[CERTIFICATE]} />));
      expect(await screen.findByRole('radio', { name: 'Public' })).toBeEnabled();
    });

    it('says nothing about Pro once the certificate is public', async () => {
      stubApi({
        'GET /api/auth/me': () => json({ plan: 'free', csrf_token: 'x' }),
      });
      await renderInRouter(withMode('professional', <Certificates certificates={[PUBLIC]} />));
      expect(await screen.findByRole('link', { name: /View certificate/ })).toBeVisible();
      expect(screen.queryByText(/part of Forgeway Pro/)).toBeNull();
    });
  });
});
