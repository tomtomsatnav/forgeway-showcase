import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { MAP, json, stubApi } from '../test/fixtures';
import { renderInRouter, withMode } from '../test/render';
import { AppShell } from './AppShell';

afterEach(() => {
  vi.unstubAllGlobals();
});

const signedIn = () =>
  stubApi({
    'GET /api/auth/me': () =>
      json({ email: 'a@example.com', plan: 'free', email_verified: true, csrf_token: 'x' }),
    'GET /api/map': () => json(MAP),
    'GET /api/releases': () => json({ last_seen: null, unread: false, releases: [] }),
  });

describe('header menu', () => {
  it('is a disclosure: the button says whether it is open and controls the menu', async () => {
    signedIn();
    await renderInRouter(withMode('rpg', <AppShell />));
    const button = await screen.findByRole('button', { name: 'Menu' });
    const menu = document.getElementById(button.getAttribute('aria-controls') ?? '');
    expect(menu).not.toBeNull();
    expect(button).toHaveAttribute('aria-expanded', 'false');
    // Closed below 640px: the menu is hidden, and the compact level stays in the header.
    expect(menu?.className).toMatch(/(^|\s)hidden(\s|$)/);
    expect(menu?.className).toMatch(/sm:contents/);
    expect(await screen.findByLabelText('Your level')).toBeInTheDocument();

    await userEvent.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'true');
    expect(menu?.className).not.toMatch(/(^|\s)hidden(\s|$)/);
  });

  it('moves focus into the menu, and Escape closes it and returns focus to the button', async () => {
    signedIn();
    await renderInRouter(withMode('rpg', <AppShell />));
    const button = await screen.findByRole('button', { name: 'Menu' });
    await screen.findByRole('link', { name: 'Character sheet' });

    await userEvent.click(button);
    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'Character sheet' })).toHaveFocus();
    });
    // Mode, colour scheme and sign out all live in the menu.
    const menu = document.getElementById(button.getAttribute('aria-controls') ?? '');
    expect(menu).toContainElement(screen.getByRole('group', { name: 'Mode' }));
    expect(menu).toContainElement(screen.getByRole('group', { name: 'Colour scheme' }));
    expect(menu).toContainElement(screen.getByRole('button', { name: 'Sign out' }));

    await userEvent.keyboard('{Escape}');
    expect(button).toHaveAttribute('aria-expanded', 'false');
    expect(button).toHaveFocus();
  });

  it('closes when a link in it is followed', async () => {
    signedIn();
    await renderInRouter(withMode('professional', <AppShell />));
    const button = await screen.findByRole('button', { name: 'Menu' });
    await userEvent.click(button);
    await userEvent.click(await screen.findByRole('link', { name: 'Profile' }));
    expect(button).toHaveAttribute('aria-expanded', 'false');
  });
});

describe('footer', () => {
  it.each(['professional', 'rpg'] as const)(
    'links the privacy policy and terms in %s mode, signed out too',
    async (mode) => {
      stubApi({ 'GET /api/auth/me': () => json({ code: 'unauthenticated' }, 401) });
      await renderInRouter(withMode(mode, <AppShell />));
      const footer = screen.getByRole('navigation', { name: 'Site' });
      expect(footer.closest('footer')).not.toBeNull();
      expect(screen.getByRole('link', { name: 'Privacy' })).toHaveAttribute('href', '/privacy');
      expect(screen.getByRole('link', { name: 'Terms' })).toHaveAttribute('href', '/terms');
    },
  );
});
