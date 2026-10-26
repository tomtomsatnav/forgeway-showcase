import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { Mode } from '../../api/types';
import { renderInRouter, withMode } from '../../test/render';
import { PRIVACY_CONTACT, PrivacyPage, TermsPage } from './LegalPages';

const modes: Mode[] = ['professional', 'rpg'];

describe.each(modes)('legal pages in %s mode', (mode) => {
  it('the privacy policy names what is kept, who handles it and how to act on it', async () => {
    await renderInRouter(withMode(mode, <PrivacyPage />));

    expect(screen.getByRole('heading', { level: 1, name: 'Privacy policy' })).toBeVisible();
    for (const heading of [
      'What we keep',
      'What we do not do',
      'Cookies and local storage',
      'Who else handles it',
      'How long we keep it',
      'Your rights',
    ]) {
      expect(screen.getByRole('heading', { level: 2, name: heading })).toBeVisible();
    }
    expect(screen.getByText(/password as a one-way hash/)).toBeVisible();
    expect(screen.getByText(/Your IP address,/)).toBeVisible();
    expect(screen.getByText(/no adverts, no analytics or tracking scripts/)).toBeVisible();
    expect(screen.getByText('Resend,')).toBeVisible();
    const contacts = screen.getAllByRole('link', { name: PRIVACY_CONTACT });
    expect(contacts[0]).toHaveAttribute('href', `mailto:${PRIVACY_CONTACT}`);
    const rights = screen.getByRole('heading', { name: 'Your rights' }).closest('section');
    if (rights === null) throw new Error('the rights heading should sit in a section');
    expect(within(rights).getByRole('link', { name: 'your profile' })).toHaveAttribute(
      'href',
      '/profile',
    );
  });

  it('the terms link the privacy policy and say how to leave', async () => {
    await renderInRouter(withMode(mode, <TermsPage />));

    expect(screen.getByRole('heading', { level: 1, name: 'Terms of use' })).toBeVisible();
    expect(screen.getByRole('link', { name: 'privacy policy' })).toHaveAttribute(
      'href',
      '/privacy',
    );
    expect(screen.getByText(/delete your account at any time/)).toBeVisible();
    expect(screen.getByText(/not an\s+accredited qualification/)).toBeVisible();
  });
});
