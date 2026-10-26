import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { json, problem, stubApi } from '../../test/fixtures';
import { renderInRouter, withMode } from '../../test/render';
import { AuthPage } from './AuthPage';

const ME = {
  id: 'u1',
  email: 'a@example.com',
  email_verified: false,
  pending_email: null,
  display_name: 'A',
  csrf_token: 'csrf',
  profile: { mode: 'professional', colour_scheme: 'system' },
};

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('AuthPage', () => {
  it("registers with the browser's time zone", async () => {
    vi.spyOn(Intl, 'DateTimeFormat').mockImplementation(
      () => ({ resolvedOptions: () => ({ timeZone: 'Pacific/Auckland' }) }) as Intl.DateTimeFormat,
    );
    const seen = stubApi({
      'POST /api/auth/register': () => json(ME, 201),
      'GET /api/map': () => json({}),
      'GET /api/config': () => json({ turnstile_site_key: null }),
    });
    const user = userEvent.setup();
    await renderInRouter(withMode('professional', <AuthPage kind="register" />));

    await user.type(await screen.findByLabelText('Display name'), 'A');
    await user.type(screen.getByLabelText('Email'), 'a@example.com');
    await user.type(screen.getByLabelText('Password'), 'correct horse battery');
    await user.click(screen.getByRole('button', { name: 'Create account' }));

    await waitFor(() => {
      expect(seen.some((request) => request.url.endsWith('/api/auth/register'))).toBe(true);
    });
    const register = seen.find((request) => request.url.endsWith('/api/auth/register'));
    expect(await register?.json()).toEqual({
      email: 'a@example.com',
      password: 'correct horse battery',
      display_name: 'A',
      time_zone: 'Pacific/Auckland',
      mode: 'professional',
      colour_scheme: 'light',
    });
  });

  it('carries the mode and scheme chosen as a guest into the new account', async () => {
    const seen = stubApi({
      'POST /api/auth/register': () =>
        json({ ...ME, profile: { mode: 'rpg', colour_scheme: 'light' } }, 201),
      'GET /api/map': () => json({}),
      'GET /api/config': () => json({ turnstile_site_key: null }),
    });
    const user = userEvent.setup();
    await renderInRouter(withMode('rpg', <AuthPage kind="register" />));

    await user.type(await screen.findByLabelText('Display name'), 'A');
    await user.type(screen.getByLabelText('Email'), 'a@example.com');
    await user.type(screen.getByLabelText('Passphrase'), 'correct horse battery');
    await user.click(screen.getByRole('button', { name: 'Begin your journey' }));

    await waitFor(() => {
      expect(seen.some((request) => request.url.endsWith('/api/auth/register'))).toBe(true);
    });
    const register = seen.find((request) => request.url.endsWith('/api/auth/register'));
    expect(await register?.json()).toMatchObject({ mode: 'rpg', colour_scheme: 'light' });
  });

  it('shows the check-your-inbox state after registering, leaving the resend to the banner', async () => {
    stubApi({
      'POST /api/auth/register': () => json(ME, 201),
      'GET /api/map': () => json({}),
      'GET /api/config': () => json({ turnstile_site_key: null }),
    });
    const user = userEvent.setup();
    await renderInRouter(withMode('professional', <AuthPage kind="register" />));

    await user.type(await screen.findByLabelText('Display name'), 'A');
    await user.type(screen.getByLabelText('Email'), 'a@example.com');
    await user.type(screen.getByLabelText('Password'), 'correct horse battery');
    await user.click(screen.getByRole('button', { name: 'Create account' }));

    expect(await screen.findByRole('heading', { name: 'Check your inbox' })).toBeInTheDocument();
    expect(screen.getByText(/sent a link to a@example.com/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Continue to the syllabus' })).toHaveAttribute(
      'href',
      '/',
    );
    expect(screen.queryByRole('button', { name: 'Send a new link' })).toBeNull();
  });

  it('renders Turnstile when a site key is configured and sends its token', async () => {
    const render = vi.fn(
      (_element: HTMLElement, options: { sitekey: string; callback: (token: string) => void }) => {
        options.callback('turnstile-token');
        return 'widget-1';
      },
    );
    vi.stubGlobal('turnstile', { render, remove: vi.fn() });
    const seen = stubApi({
      'POST /api/auth/register': () => json(ME, 201),
      'GET /api/map': () => json({}),
      'GET /api/config': () => json({ turnstile_site_key: '1x00000000000000000000AA' }),
    });
    const user = userEvent.setup();
    await renderInRouter(withMode('rpg', <AuthPage kind="register" />));

    expect(await screen.findByRole('group', { name: 'Trial of the gate' })).toBeInTheDocument();
    await waitFor(() => {
      expect(render).toHaveBeenCalled();
    });
    expect(render.mock.calls[0]?.[1].sitekey).toBe('1x00000000000000000000AA');
    await user.type(screen.getByLabelText('Display name'), 'A');
    await user.type(screen.getByLabelText('Email'), 'a@example.com');
    await user.type(screen.getByLabelText('Passphrase'), 'correct horse battery');
    await user.click(screen.getByRole('button', { name: 'Begin your journey' }));

    await waitFor(() => {
      expect(seen.some((request) => request.url.endsWith('/api/auth/register'))).toBe(true);
    });
    const register = seen.find((request) => request.url.endsWith('/api/auth/register'));
    expect(await register?.json()).toMatchObject({ turnstile_token: 'turnstile-token' });
    expect(await screen.findByRole('heading', { name: 'A messenger rides to you' })).toBeVisible();
  });

  it('holds the submit until a Turnstile token arrives, and again after a failed register', async () => {
    const tokens: ((token: string) => void)[] = [];
    const render = vi.fn(
      (_element: HTMLElement, options: { callback: (token: string) => void }) => {
        tokens.push(options.callback);
        return `widget-${tokens.length}`;
      },
    );
    const remove = vi.fn();
    vi.stubGlobal('turnstile', { render, remove });
    const seen = stubApi({
      'POST /api/auth/register': () => problem(403, 'The human check failed.', 'challenge-failed'),
      'GET /api/config': () => json({ turnstile_site_key: '1x00000000000000000000AA' }),
    });
    const user = userEvent.setup();
    await renderInRouter(withMode('professional', <AuthPage kind="register" />));

    const submit = await screen.findByRole('button', { name: 'Create account' });
    await waitFor(() => {
      expect(render).toHaveBeenCalledTimes(1);
    });
    expect(submit).toBeDisabled();
    expect(submit).toHaveAccessibleDescription('Complete the human check to continue.');

    act(() => {
      tokens[0]?.('token-1');
    });
    await waitFor(() => {
      expect(submit).toBeEnabled();
    });
    await user.type(screen.getByLabelText('Display name'), 'A');
    await user.type(screen.getByLabelText('Email'), 'a@example.com');
    await user.type(screen.getByLabelText('Password'), 'correct horse battery');
    await user.click(submit);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The human check did not pass. Complete it again, then retry.',
    );
    // The spent token is gone and the widget is a fresh one, which must supply the next.
    await waitFor(() => {
      expect(render).toHaveBeenCalledTimes(2);
    });
    expect(remove).toHaveBeenCalledWith('widget-1');
    expect(screen.getByRole('button', { name: 'Create account' })).toBeDisabled();

    act(() => {
      tokens[1]?.('token-2');
    });
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Create account' })).toBeEnabled();
    });
    await user.click(screen.getByRole('button', { name: 'Create account' }));
    await waitFor(() => {
      expect(seen.filter((request) => request.url.endsWith('/api/auth/register'))).toHaveLength(2);
    });
    const second = seen.filter((request) => request.url.endsWith('/api/auth/register'))[1];
    expect(await second?.json()).toMatchObject({ turnstile_token: 'token-2' });
  });

  it('has no human check without a site key, and sign-in links to password reset', async () => {
    stubApi({ 'GET /api/config': () => json({ turnstile_site_key: null }) });
    await renderInRouter(withMode('professional', <AuthPage kind="sign-in" />));
    expect(await screen.findByRole('link', { name: 'Forgot your password?' })).toHaveAttribute(
      'href',
      '/forgot-password',
    );
    expect(screen.queryByRole('group', { name: 'Human check' })).toBeNull();
  });
});
