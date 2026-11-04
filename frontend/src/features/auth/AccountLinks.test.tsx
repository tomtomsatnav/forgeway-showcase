import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { json, stubApi } from '../../test/fixtures';
import { renderInRouter, withMode } from '../../test/render';
import { ForgotPasswordPage } from './ForgotPasswordPage';
import { ResetPasswordPage } from './ResetPasswordPage';
import { UnverifiedBanner } from './UnverifiedBanner';
import { VerifyEmailPage } from './VerifyEmailPage';

const ME = {
  id: 'u1',
  email: 'a@example.com',
  email_verified: false,
  pending_email: null,
  display_name: 'A',
  csrf_token: 'csrf',
  profile: { mode: 'professional', colour_scheme: 'system' },
};

const problem = (status: number, code: string, detail: string) =>
  new Response(JSON.stringify({ type: 'about:blank', title: 'x', status, detail, code }), {
    status,
    headers: { 'content-type': 'application/problem+json' },
  });

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('VerifyEmailPage', () => {
  it('sends the token once and confirms', async () => {
    const seen = stubApi({
      'POST /api/auth/verify-email': () => new Response(null, { status: 204 }),
      'GET /api/auth/me': () => json({ ...ME, email_verified: true }),
    });
    await renderInRouter(withMode('professional', <VerifyEmailPage token="tok" />));

    expect(await screen.findByRole('heading', { name: 'Email address verified' })).toBeVisible();
    const posts = seen.filter((request) => request.url.endsWith('/api/auth/verify-email'));
    expect(posts).toHaveLength(1);
    expect(await posts[0]?.json()).toEqual({ token: 'tok' });
  });

  it('takes the unverified banner away once verified', async () => {
    let verified = false;
    stubApi({
      'POST /api/auth/verify-email': () => {
        verified = true;
        return new Response(null, { status: 204 });
      },
      'GET /api/auth/me': () => json({ ...ME, email_verified: verified }),
    });
    await renderInRouter(
      withMode(
        'professional',
        <>
          <UnverifiedBanner />
          <VerifyEmailPage token="tok" />
        </>,
      ),
    );
    expect(await screen.findByRole('heading', { name: 'Email address verified' })).toBeVisible();
    await waitFor(() => {
      expect(screen.queryByRole('region', { name: 'Email verification' })).toBeNull();
    });
  });

  it('explains an expired link and offers a new one when signed in', async () => {
    stubApi({
      'POST /api/auth/verify-email': () =>
        problem(422, 'invalid-input', 'This link is invalid or has expired. Request a new one.'),
      'GET /api/auth/me': () => json(ME),
    });
    await renderInRouter(withMode('rpg', <VerifyEmailPage token="old" />));

    expect(await screen.findByRole('alert')).toHaveTextContent('invalid or has expired');
    expect(await screen.findByRole('button', { name: 'Send another letter' })).toBeVisible();
  });

  it('says so when the token is missing', async () => {
    stubApi({ 'GET /api/auth/me': () => json(ME) });
    await renderInRouter(withMode('professional', <VerifyEmailPage token={undefined} />));
    expect(await screen.findByRole('alert')).toHaveTextContent('incomplete');
  });
});

describe('ForgotPasswordPage', () => {
  it('always says the same once submitted', async () => {
    const seen = stubApi({
      'POST /api/auth/password-reset': () => new Response(null, { status: 202 }),
    });
    const user = userEvent.setup();
    await renderInRouter(withMode('professional', <ForgotPasswordPage />));

    await user.type(await screen.findByLabelText('Email'), 'nobody@example.com');
    await user.click(screen.getByRole('button', { name: 'Send reset link' }));

    expect(await screen.findByRole('status')).toHaveTextContent('If an account uses that address');
    expect(await seen[0]?.json()).toEqual({ email: 'nobody@example.com' });
  });

  it('shows a rate limit', async () => {
    stubApi({
      'POST /api/auth/password-reset': () =>
        problem(429, 'rate-limited', 'Too many reset requests. Try again later.'),
    });
    const user = userEvent.setup();
    await renderInRouter(withMode('professional', <ForgotPasswordPage />));
    await user.type(await screen.findByLabelText('Email'), 'a@example.com');
    await user.click(screen.getByRole('button', { name: 'Send reset link' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Too many reset requests');
  });
});

describe('ResetPasswordPage', () => {
  const ok = () => new Response(null, { status: 204 });
  const dead = () =>
    problem(422, 'invalid-input', 'This link is invalid or has expired. Request a new one.');

  it('sets the new password and sends the learner to sign in', async () => {
    const seen = stubApi({
      'POST /api/auth/password-reset/check': ok,
      'POST /api/auth/password-reset/confirm': ok,
    });
    const user = userEvent.setup();
    await renderInRouter(withMode('professional', <ResetPasswordPage token="tok" />));

    await user.type(await screen.findByLabelText('New password'), 'a much better passphrase');
    await user.click(screen.getByRole('button', { name: 'Set new password' }));

    expect(await screen.findByRole('status')).toHaveTextContent('every session signed out');
    const confirm = seen.find((request) => request.url.endsWith('/confirm'));
    expect(await confirm?.json()).toEqual({ token: 'tok', password: 'a much better passphrase' });
    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/sign-in');
  });

  it('says a dead link is dead as the page opens, in one sentence, with no form', async () => {
    const seen = stubApi({ 'POST /api/auth/password-reset/check': dead });
    await renderInRouter(withMode('professional', <ResetPasswordPage token="old" />));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'This link has expired or has already been used: ask for a new one.',
    );
    expect(screen.getByRole('link', { name: 'ask for a new one' })).toHaveAttribute(
      'href',
      '/forgot-password',
    );
    expect(screen.queryByLabelText('New password')).toBeNull();
    expect(await seen[0]?.json()).toEqual({ token: 'old' });
  });

  it('says so too when the link dies between opening and submitting', async () => {
    stubApi({
      'POST /api/auth/password-reset/check': ok,
      'POST /api/auth/password-reset/confirm': dead,
    });
    const user = userEvent.setup();
    await renderInRouter(withMode('professional', <ResetPasswordPage token="old" />));
    await user.type(await screen.findByLabelText('New password'), 'a much better passphrase');
    await user.click(screen.getByRole('button', { name: 'Set new password' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'has expired or has already been used',
    );
    expect(screen.queryByText(/Request a new one/)).toBeNull();
  });

  it('calls it a passphrase throughout in RPG mode', async () => {
    stubApi({ 'POST /api/auth/password-reset/check': ok });
    await renderInRouter(withMode('rpg', <ResetPasswordPage token="tok" />));
    expect(await screen.findByLabelText('New passphrase')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Set new passphrase' })).toBeVisible();
    expect(screen.queryByText(/password/i)).toBeNull();
  });
});

describe('UnverifiedBanner', () => {
  it('shows only while the email is unverified', async () => {
    stubApi({ 'GET /api/auth/me': () => json(ME) });
    await renderInRouter(withMode('professional', <UnverifiedBanner />));
    expect(await screen.findByRole('region', { name: 'Email verification' })).toHaveTextContent(
      'Verify your email address to run checks',
    );
  });

  it('is absent once verified', async () => {
    const seen = stubApi({ 'GET /api/auth/me': () => json({ ...ME, email_verified: true }) });
    await renderInRouter(withMode('rpg', <UnverifiedBanner />));
    await waitFor(() => {
      expect(seen.length).toBeGreaterThan(0);
    });
    expect(screen.queryByRole('region', { name: 'Email verification' })).toBeNull();
  });
});
