import { screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { Mode } from '../../api/types';
import { json, stubApi } from '../../test/fixtures';
import { renderInRouter, withMode } from '../../test/render';
import {
  AccessibilityPage,
  HELLO_CONTACT,
  ICO_NUMBER,
  PRIVACY_CONTACT,
  PrivacyPage,
  TermsPage,
  TRADER_ADDRESS,
} from './LegalPages';

const modes: Mode[] = ['professional', 'rpg'];

afterEach(() => {
  vi.unstubAllGlobals();
});

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
    expect(screen.getByRole('rowheader', { name: 'Resend' })).toBeVisible();
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

describe('subscription terms', () => {
  it('cover renewal, the trial, cancellation, the regulation-37 waiver and the model form', async () => {
    await renderInRouter(withMode('professional', <TermsPage />));

    expect(screen.getByRole('heading', { name: 'Forgeway Pro subscriptions' })).toBeVisible();
    expect(screen.getByText(/renews automatically at the end of each/)).toBeVisible();
    expect(screen.getByText(/nothing is charged during it/)).toBeVisible();
    const policy = screen.getByRole('heading', { name: 'Cancellation policy' }).closest('section');
    expect(policy).toHaveAttribute('id', 'cancellation');
    expect(policy).toHaveTextContent('lose that 14-day right');
    expect(policy).toHaveTextContent('Withdraw from contract');
    expect(policy).toHaveTextContent('confirmation within 24 hours');
    const form = screen
      .getByRole('heading', { name: 'Model cancellation form' })
      .closest('section');
    expect(form).toHaveAttribute('id', 'cancellation-form');
    expect(form).toHaveTextContent('hereby give notice that I/We [*] cancel');
  });

  it('name Stripe as a processor in the privacy policy', async () => {
    await renderInRouter(withMode('professional', <PrivacyPage />));
    expect(screen.getByRole('rowheader', { name: 'Stripe' })).toBeVisible();
    expect(screen.getByText(/we never see or store them/)).toBeVisible();
  });
});

const section = (name: string) => {
  const found = screen.getByRole('heading', { level: 2, name }).closest('section');
  if (found === null) throw new Error(`no section for ${name}`);
  return found;
};

describe('the trader address comes from the API', () => {
  it.each([
    ['set', { trader_address: '1 Example St, London' }, '1 Example St, London'],
    ['unset', { trader_address: null }, TRADER_ADDRESS],
  ])('while it is %s, every legal page shows the right one', async (_name, config, shown) => {
    stubApi({ 'GET /api/config': () => json(config) });
    await renderInRouter(withMode('professional', <TermsPage />));
    await waitFor(() => {
      expect(section('Who we are')).toHaveTextContent(shown);
    });
    expect(section('Forgeway Pro subscriptions')).toHaveTextContent(shown);
    expect(section('Model cancellation form')).toHaveTextContent(shown);
  });
});

describe('the privacy notice covers UK GDPR Article 13', () => {
  it('says Stripe keeps billing records under its own retention', async () => {
    await renderInRouter(withMode('professional', <PrivacyPage />));
    expect(section('How long we keep it')).toHaveTextContent(
      /keeps its own billing records under its own retention policy/,
    );
  });

  it('names the trader, the address placeholder and the ICO number', async () => {
    await renderInRouter(withMode('professional', <PrivacyPage />));
    const trader = section('Who we are');
    expect(trader).toHaveTextContent('[TRADER NAME], trading as Forgeway');
    expect(trader).toHaveTextContent(TRADER_ADDRESS);
    expect(trader).toHaveTextContent(ICO_NUMBER);
    expect(within(trader).getByRole('link', { name: HELLO_CONTACT })).toBeVisible();
    expect(within(trader).getByRole('link', { name: PRIVACY_CONTACT })).toBeVisible();
  });

  it('gives a lawful basis for each purpose, including the marketing soft opt-in', async () => {
    await renderInRouter(withMode('professional', <PrivacyPage />));
    const region = screen.getByRole('region', { name: 'Purposes and lawful bases' });
    expect(within(region).getAllByRole('row').length).toBeGreaterThan(5);
    const purposes = section('Why we use it, and the lawful basis');
    expect(purposes).toHaveTextContent('Contract');
    expect(purposes).toHaveTextContent('Legal obligation');
    expect(purposes).toHaveTextContent('soft opt-in');
  });

  it('explains live runs, Anthropic as processor, payments and transfers', async () => {
    await renderInRouter(withMode('professional', <PrivacyPage />));
    const ai = section('Live runs and AI');
    expect(ai).toHaveTextContent('Anthropic');
    expect(ai).toHaveTextContent('does not train');
    expect(ai).toHaveTextContent('within 30 days');
    expect(ai).toHaveTextContent('usage records (tokens and cost) for 13 months');
    expect(section('Payments')).toHaveTextContent('independent controller');
    const recipients = section('Who else handles it');
    expect(within(recipients).getByRole('rowheader', { name: 'Anthropic, PBC' })).toBeVisible();
    expect(recipients).toHaveTextContent('UK Addendum');
    expect(recipients).toHaveTextContent('UK Extension to the EU-US Data Privacy Framework');
    expect(recipients).toHaveTextContent('does not contact Google');
  });

  it('gives retention for each category, rights, complaints and automated decisions', async () => {
    await renderInRouter(withMode('professional', <PrivacyPage />));
    const retention = section('How long we keep it');
    expect(retention).toHaveTextContent('six years after the end of the tax year');
    expect(retention).toHaveTextContent('even if you delete your account');
    expect(retention).toHaveTextContent('12 months from joining');
    expect(section('Your rights')).toHaveTextContent('Access and portability');
    const complaints = section('Complaints');
    expect(complaints).toHaveTextContent('acknowledge your complaint within 30 days');
    expect(complaints).toHaveTextContent('keep a record');
    expect(complaints).toHaveTextContent("Information Commissioner's Office");
    expect(section('What we do not do')).toHaveTextContent(
      'No decision with legal or similarly significant effects',
    );
  });

  it('lists the cookies and storage the code actually uses', async () => {
    await renderInRouter(withMode('professional', <PrivacyPage />));
    const cookies = section('Cookies and local storage');
    for (const name of [
      'lattice_session',
      '__cf_bm',
      'lattice.theme',
      'lattice.workspace-columns',
    ]) {
      expect(within(cookies).getByText(name)).toBeVisible();
    }
    expect(cookies).toHaveTextContent('Turnstile');
  });
});

describe('the terms', () => {
  it('cover age, renewal cooling-off, consumer rights, changes, fair use and disputes', async () => {
    await renderInRouter(withMode('professional', <TermsPage />));
    expect(section('Who can use Forgeway')).toHaveTextContent('You must be 18 or over');
    expect(section('Cancellation policy')).toHaveTextContent('This right cannot be given up');
    expect(section('Your rights under consumer law')).toHaveTextContent('Consumer Rights Act 2015');
    expect(section('Changes to the service or these terms')).toHaveTextContent(
      'at least 30 days before',
    );
    expect(section('Suspending or closing an account')).toHaveTextContent('tell you why');
    expect(
      within(section('Fair use, and live runs')).getByRole('link', {
        name: 'Acceptable Use Policy',
      }),
    ).toHaveAttribute('href', 'https://www.anthropic.com/legal/aup');
    expect(section('Law and disputes')).toHaveTextContent('England and Wales');
    expect(section('Model cancellation form')).toHaveTextContent(TRADER_ADDRESS);
  });

  it('the accessibility statement says how to report a problem', async () => {
    await renderInRouter(withMode('professional', <AccessibilityPage />));
    expect(
      screen.getByRole('heading', { level: 1, name: 'Accessibility statement' }),
    ).toBeVisible();
    expect(section('Our aim')).toHaveTextContent('WCAG) 2.2 at level AA');
    expect(within(section('Tell us')).getByRole('link', { name: HELLO_CONTACT })).toBeVisible();
  });
});
