import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { json, stubApi } from '../../test/fixtures';
import { renderInRouter, withMode } from '../../test/render';
import { BillingSection } from '../profile/BillingSection';
import { firstChargeDate, formatDate, type BillingStatus, type SubscriptionInfo } from './billing';
import { PastDueBanner } from './PastDueBanner';
import { ProCallToAction } from './ProCallToAction';
import { ProOffer } from './ProOffer';
import { ProPage } from './ProPage';

const ON = {
  enabled: true,
  currency: 'GBP',
  monthly_price_minor: 1900,
  annual_price_minor: 19000,
  intro_offer: { kind: 'trial_days', value: 7 },
} as const;
const OFF = { ...ON, enabled: false };
const config = (billing: typeof ON | typeof OFF) => ({
  turnstile_site_key: null,
  free_exercises_per_branch: 3,
  kit_wheel_url: null,
  billing,
});
const CONSENT = {
  version: '2026-11-03',
  express: 'I want my Forgeway Pro access to start straight away, including during the free trial.',
  acknowledgement:
    'I understand that once my access starts I lose my 14-day right to cancel and get a refund.',
};
const status = (overrides: Partial<BillingStatus> = {}): BillingStatus => ({
  enabled: true,
  plan: 'free',
  trial_days: 7,
  subscription: null,
  consent: CONSENT,
  ...overrides,
});
const sub = (overrides: Partial<SubscriptionInfo> = {}): SubscriptionInfo => ({
  status: 'active',
  interval: 'annual',
  paused: false,
  resumes_at: null,
  trial_end: null,
  current_period_end: '2027-11-10T09:00:00Z',
  cancelling: false,
  ends_at: null,
  withdrawal_until: null,
  ...overrides,
});
// A Tuesday morning, so the first charge falls on Tuesday 10 November.
const NOW = new Date('2026-11-03T09:00:00');

let assign: ReturnType<typeof vi.fn>;
beforeEach(() => {
  assign = vi.fn();
  const { origin, href } = window.location;
  vi.stubGlobal('location', { origin, href, assign });
});
afterEach(() => {
  vi.unstubAllGlobals();
});

function onApi(billing: BillingStatus, more: Record<string, (r: Request) => Response> = {}) {
  return stubApi({
    'GET /api/auth/me': () => json({ plan: billing.plan, csrf_token: 'x', email_verified: true }),
    'GET /api/config': () => json(config(ON)),
    'GET /api/billing': () => json(billing),
    ...more,
  });
}

describe('the first charge date', () => {
  it('is the trial length after now, shown as a date', () => {
    expect(formatDate(firstChargeDate(NOW, 7))).toBe('10 November 2026');
    expect(formatDate(firstChargeDate(new Date('2026-12-28T12:00:00'), 7))).toBe('4 January 2027');
    expect(formatDate(firstChargeDate(new Date('2027-02-25T12:00:00'), 7))).toBe('4 March 2027');
    expect(formatDate(firstChargeDate(NOW, 0))).toBe('3 November 2026');
  });

  it('is exactly the trial in hours, the instant Stripe ends it', () => {
    expect(firstChargeDate(NOW, 7).getTime() - NOW.getTime()).toBe(7 * 24 * 60 * 60 * 1000);
  });
});

describe('the Pro page with billing off', () => {
  it('keeps today’s waitlist and shows no price', async () => {
    stubApi({
      'GET /api/auth/me': () => json({ plan: 'free', csrf_token: 'x' }),
      'GET /api/config': () => json(config(OFF)),
      'GET /api/pro/waitlist': () => json({ joined: false, plan_interest: null, joined_at: null }),
    });
    await renderInRouter(withMode('professional', <ProPage />));

    expect(await screen.findByRole('button', { name: 'Join the waitlist' })).toBeVisible();
    expect(document.body.textContent).not.toMatch(/£|free trial/i);
    expect(screen.queryByRole('checkbox')).toBeNull();
  });
});

describe('the Pro page with billing on', () => {
  it('shows the plans, annual first, with prices from the config', async () => {
    onApi(status());
    await renderInRouter(withMode('professional', <ProPage />));

    const annual = await screen.findByRole('radio', { name: 'Annual' });
    expect(annual).toBeChecked();
    expect(screen.getByText('£190/year')).toBeVisible();
    expect(screen.getByText('Two months free')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Join the waitlist' })).toBeNull();

    await userEvent.click(screen.getByRole('radio', { name: 'Monthly' }));
    expect(screen.getByText('£19/month')).toBeVisible();
    expect(screen.queryByText('Two months free')).toBeNull();
  });

  it('puts every piece of pre-contract information right before the order', async () => {
    onApi(status());
    await renderInRouter(withMode('professional', <ProOffer config={ON} now={NOW} />));

    const box = await screen.findByRole('region', { name: 'Before you start' });
    // What Pro includes.
    expect(within(box).getByText(/capstone project that closes every track/)).toBeVisible();
    // The price per period, including VAT, and automatic renewal, how often and how to cancel.
    expect(box).toHaveTextContent('Forgeway Pro costs £190 a year, including VAT.');
    expect(box).toHaveTextContent('renews automatically every year until you cancel');
    expect(box).toHaveTextContent('cancel at any time from your profile (Manage billing)');
    // The trial length and the exact date of the first charge, and £0 today.
    expect(box).toHaveTextContent(
      'Your 7-day free trial starts today. Your first payment of £190 will be taken on 10 November 2026',
    );
    expect(box).toHaveTextContent('You pay £0 today.');
    // The documents.
    const docs = within(box).getByRole('navigation', { name: 'The documents that apply' });
    expect(within(docs).getByRole('link', { name: 'Terms of use' })).toHaveAttribute(
      'href',
      '/terms',
    );
    expect(within(docs).getByRole('link', { name: 'Privacy policy' })).toHaveAttribute(
      'href',
      '/privacy',
    );
    expect(within(docs).getByRole('link', { name: 'Cancellation policy' })).toHaveAttribute(
      'href',
      '/terms#cancellation',
    );
    expect(within(docs).getByRole('link', { name: 'Model cancellation form' })).toHaveAttribute(
      'href',
      '/terms#cancellation-form',
    );

    await userEvent.click(screen.getByRole('radio', { name: 'Monthly' }));
    expect(box).toHaveTextContent('£19 a month, including VAT');
    expect(box).toHaveTextContent('every month');
  });

  it('needs the consent before Checkout, then sends it and goes to Stripe', async () => {
    const seen = onApi(status(), {
      'POST /api/billing/checkout': () => json({ url: 'https://checkout.stripe.com/c/cs_1' }),
    });
    await renderInRouter(withMode('professional', <ProOffer config={ON} now={NOW} />));
    const start = await screen.findByRole('button', { name: 'Start my 7-day free trial' });
    const consent = await screen.findByRole('checkbox', {
      name: /start straight away.*lose my 14-day right to cancel/,
    });
    await waitFor(() => {
      expect(consent).toBeEnabled();
    });

    await userEvent.click(start);
    expect(await screen.findByRole('alert')).toHaveTextContent('Tick the box');
    expect(consent).toHaveAttribute('aria-invalid', 'true');
    expect(seen.some((r) => r.method === 'POST')).toBe(false);

    await userEvent.click(consent);
    await userEvent.click(start);
    await waitFor(() => {
      expect(assign).toHaveBeenCalledWith('https://checkout.stripe.com/c/cs_1');
    });
    const post = seen.find((r) => r.method === 'POST');
    expect(await post?.json()).toEqual({
      plan: 'annual',
      consent: true,
      consent_version: '2026-11-03',
      marketing_opt_out: false,
    });
  });

  it('sends the unticked offers opt-out once it is ticked', async () => {
    const seen = onApi(status(), {
      'POST /api/billing/checkout': () => json({ url: 'https://checkout.stripe.com/c/cs_1' }),
    });
    await renderInRouter(withMode('professional', <ProOffer config={ON} now={NOW} />));
    const consent = await screen.findByRole('checkbox', { name: /start straight away/ });
    await waitFor(() => {
      expect(consent).toBeEnabled();
    });
    const noOffers = screen.getByRole('checkbox', {
      name: /do not want emails about Forgeway offers/,
    });
    expect(noOffers).not.toBeChecked();
    await userEvent.click(consent);
    await userEvent.click(noOffers);
    await userEvent.click(screen.getByRole('button', { name: 'Start my 7-day free trial' }));
    await waitFor(() => {
      expect(assign).toHaveBeenCalled();
    });
    const post = seen.find((r) => r.method === 'POST');
    expect(await post?.json()).toMatchObject({ marketing_opt_out: true });
  });

  it('offers no second trial to a returning learner', async () => {
    onApi(status({ trial_days: 0 }));
    await renderInRouter(withMode('professional', <ProOffer config={ON} now={NOW} />));

    expect(await screen.findByRole('button', { name: 'Subscribe to Pro' })).toBeVisible();
    const box = screen.getByRole('region', { name: 'Before you start' });
    expect(box).toHaveTextContent('Your first payment of £190 is taken today.');
    expect(box).toHaveTextContent('You pay £190 today.');
    expect(box).not.toHaveTextContent('free trial');
  });

  it('speaks the RPG lexicon, keeping the legal information word for word', async () => {
    onApi(status());
    await renderInRouter(withMode('rpg', <ProOffer config={ON} now={NOW} />));

    expect(await screen.findByRole('heading', { name: 'Join the guild' })).toBeVisible();
    expect(screen.getByRole('region', { name: 'Before you start' })).toHaveTextContent(
      'You pay £0 today.',
    );
  });

  it('points a learner with Pro to their subscription', async () => {
    onApi(status({ plan: 'pro', subscription: sub() }));
    await renderInRouter(withMode('professional', <ProPage />));

    expect(await screen.findByRole('link', { name: 'Manage your subscription' })).toHaveAttribute(
      'href',
      '/profile#billing',
    );
    expect(screen.queryByRole('checkbox')).toBeNull();
  });

  it('links Pro content to the plans, not the waitlist', async () => {
    onApi(status());
    await renderInRouter(withMode('professional', <ProCallToAction />));

    expect(
      await screen.findByRole('link', { name: 'See plans and the free trial' }),
    ).toHaveAttribute('href', '/pro');
    expect(screen.queryByRole('button', { name: 'Join the waitlist' })).toBeNull();
  });
});

describe('the account’s billing section', () => {
  it('shows the plan, the status and the trial’s end, and opens the portal', async () => {
    const seen = onApi(
      status({
        plan: 'pro',
        subscription: sub({ status: 'trialing', trial_end: '2026-11-10T09:00:00Z' }),
      }),
      { 'POST /api/billing/portal': () => json({ url: 'https://billing.stripe.com/p/1' }) },
    );
    await renderInRouter(withMode('professional', <BillingSection />), undefined, '/profile');

    expect(await screen.findByText('Free trial')).toBeVisible();
    expect(screen.getByText('Pro')).toBeVisible();
    expect(screen.getByText('Your free trial ends on 10 November 2026.')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Pause' })).toBeNull(); // not during a trial

    // Cancelling a trial goes straight to the portal.
    await userEvent.click(screen.getByRole('button', { name: 'Cancel subscription' }));
    await waitFor(() => {
      expect(assign).toHaveBeenCalledWith('https://billing.stripe.com/p/1');
    });
    expect(seen.filter((r) => r.method === 'POST')).toHaveLength(1);
  });

  it('offers a pause before cancelling, and lets the learner carry on to cancel', async () => {
    const seen = onApi(status({ plan: 'pro', subscription: sub() }), {
      'POST /api/billing/portal': () => json({ url: 'https://billing.stripe.com/p/1' }),
      'POST /api/billing/pause': () =>
        json(status({ subscription: sub({ paused: true, resumes_at: '2027-01-02T09:00:00Z' }) })),
    });
    await renderInRouter(withMode('professional', <BillingSection />), undefined, '/profile');

    expect(await screen.findByText('Renews on 10 November 2027.')).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Cancel subscription' }));
    const screenPanel = screen.getByRole('group', { name: 'Pause instead?' });
    expect(screenPanel).toHaveFocus();
    const carryOn = within(screenPanel).getByRole('button', { name: 'Continue to cancel' });
    expect(carryOn).toBeVisible();

    await userEvent.click(within(screenPanel).getByRole('radio', { name: '2 months' }));
    await userEvent.click(
      within(screenPanel).getByRole('button', { name: 'Pause my subscription' }),
    );
    expect(await screen.findByText(/Paused until 2 January 2027/)).toBeVisible();
    const pause = seen.find((r) => new URL(r.url).pathname === '/api/billing/pause');
    expect(await pause?.json()).toEqual({ months: 2 });
  });

  it('goes on to the portal from the pause screen', async () => {
    onApi(status({ plan: 'pro', subscription: sub() }), {
      'POST /api/billing/portal': () => json({ url: 'https://billing.stripe.com/p/1' }),
    });
    await renderInRouter(withMode('professional', <BillingSection />), undefined, '/profile');
    await userEvent.click(await screen.findByRole('button', { name: 'Cancel subscription' }));
    await userEvent.click(screen.getByRole('button', { name: 'Continue to cancel' }));
    await waitFor(() => {
      expect(assign).toHaveBeenCalledWith('https://billing.stripe.com/p/1');
    });
  });

  it('gives an EU customer a clearly labelled withdrawal control, behind a confirmation', async () => {
    const seen = onApi(
      status({ plan: 'pro', subscription: sub({ withdrawal_until: '2026-11-17T09:00:00Z' }) }),
      {
        'POST /api/billing/withdraw': () =>
          json(status({ subscription: sub({ status: 'canceled' }) })),
      },
    );
    await renderInRouter(withMode('professional', <BillingSection />), undefined, '/profile');

    expect(await screen.findByRole('heading', { name: 'Withdraw from contract' })).toBeVisible();
    expect(screen.getByText(/until 17 November 2026/)).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Withdraw from contract' }));
    expect(seen.some((r) => r.method === 'POST')).toBe(false);
    await userEvent.click(screen.getByRole('button', { name: 'Confirm withdrawal' }));
    expect(await screen.findByRole('status')).toHaveTextContent('You have withdrawn');
  });

  it('shows no withdrawal control outside the EU or the 14 days', async () => {
    onApi(status({ plan: 'pro', subscription: sub() }));
    await renderInRouter(withMode('professional', <BillingSection />), undefined, '/profile');
    expect(await screen.findByText('Active')).toBeVisible();
    expect(screen.queryByText('Withdraw from contract')).toBeNull();
  });

  it('says how a cancelled subscription ends, in RPG words too', async () => {
    onApi(
      status({
        plan: 'pro',
        subscription: sub({ cancelling: true, ends_at: '2027-11-10T09:00:00Z' }),
      }),
    );
    await renderInRouter(withMode('rpg', <BillingSection />), undefined, '/profile');
    expect(await screen.findByText('Pro (guild member)')).toBeVisible();
    expect(screen.getByText('Cancelled')).toBeVisible();
    expect(screen.getByText(/Pro ends on 10 November 2027/)).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Cancel subscription' })).toBeNull();
  });

  it('points a free learner to the plans', async () => {
    onApi(status());
    await renderInRouter(withMode('professional', <BillingSection />), undefined, '/profile');
    expect(await screen.findByText('You are on the free plan.')).toBeVisible();
    expect(screen.getByRole('link', { name: 'See Forgeway Pro' })).toHaveAttribute('href', '/pro');
  });
});

describe('the past-due banner', () => {
  it('asks a learner whose payment failed to update their card', async () => {
    onApi(status({ plan: 'pro', subscription: sub({ status: 'past_due' }) }), {
      'POST /api/billing/portal': () => json({ url: 'https://billing.stripe.com/p/1' }),
    });
    await renderInRouter(withMode('professional', <PastDueBanner />));

    const banner = await screen.findByRole('region', { name: 'Payment overdue' });
    expect(banner).toHaveTextContent('did not go through');
    await userEvent.click(within(banner).getByRole('button', { name: 'Update payment details' }));
    await waitFor(() => {
      expect(assign).toHaveBeenCalledWith('https://billing.stripe.com/p/1');
    });
  });

  it('is not shown for a subscription in good standing', async () => {
    const seen = onApi(status({ plan: 'pro', subscription: sub() }));
    await renderInRouter(withMode('professional', <PastDueBanner />));
    await waitFor(() => {
      expect(seen.some((r) => new URL(r.url).pathname === '/api/billing')).toBe(true);
    });
    expect(screen.queryByRole('region', { name: 'Payment overdue' })).toBeNull();
  });

  it('asks nothing of the server while billing is off', async () => {
    const seen = stubApi({
      'GET /api/auth/me': () => json({ plan: 'free', csrf_token: 'x' }),
      'GET /api/config': () => json(config(OFF)),
    });
    await renderInRouter(withMode('professional', <PastDueBanner />));
    await waitFor(() => {
      expect(seen.some((r) => new URL(r.url).pathname === '/api/config')).toBe(true);
    });
    expect(seen.some((r) => new URL(r.url).pathname === '/api/billing')).toBe(false);
  });
});
