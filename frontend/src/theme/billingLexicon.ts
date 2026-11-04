import type { Mode } from '../api/types';

export type BillingPeriod = 'annual' | 'monthly';

/**
 * Billing words for both modes (the `billing` key of the lexicon). What the law needs said
 * before a learner pays (prices, renewal, trial, cancellation) reads the same in both modes; only
 * headings, buttons and the account section take the mode's flavour.
 */
export interface BillingCopy {
  // The /pro page with billing on.
  offerHeading: string;
  periodLegend: string;
  annualLabel: string;
  monthlyLabel: string;
  perPeriod: (price: string, period: BillingPeriod) => string;
  /** Beside the annual option: "Two months free"; null when it saves nothing. */
  annualSaving: (monthsFree: number) => string;
  preContractHeading: string;
  includesLabel: string;
  priceLine: (price: string, period: BillingPeriod) => string;
  renewalLine: (period: BillingPeriod) => string;
  trialLine: (days: number, price: string, date: string) => string;
  noTrialLine: (price: string) => string;
  todayLine: (price: string) => string;
  documentsLabel: string;
  termsLink: string;
  privacyLink: string;
  cancellationPolicyLink: string;
  cancellationFormLink: string;
  consentLegend: string;
  consentNeeded: string;
  noOffersLabel: string;
  start: (trialDays: number) => string;
  startNote: string;
  hasPro: string;
  manageInProfile: string;
  // After Checkout.
  successTitle: string;
  successBody: string;
  successPending: string;
  cancelledTitle: string;
  cancelledBody: string;
  backToPro: string;
  toMap: string;
  // The account section.
  sectionTitle: string;
  planLabel: string;
  planName: (plan: string) => string;
  statusLabel: string;
  status: (status: string, paused: boolean, cancelling: boolean) => string;
  trialEnds: (date: string) => string;
  renews: (date: string) => string;
  ends: (date: string) => string;
  pausedUntil: (date: string) => string;
  noSubscription: string;
  seePlans: string;
  manage: string;
  pauseAction: string;
  resumeAction: string;
  cancelAction: string;
  pauseHeading: string;
  pauseBody: string;
  pauseMonthsLegend: string;
  pauseFor: (months: number) => string;
  pauseConfirm: string;
  continueToCancel: string;
  keepAsItIs: string;
  withdrawHeading: string;
  withdrawBody: (date: string) => string;
  withdrawStart: string;
  withdrawConfirmBody: string;
  withdrawConfirm: string;
  withdrawKeep: string;
  withdrawn: string;
  // Across the app.
  pastDueBanner: string;
  pastDueAction: string;
  ctaTitle: string;
  ctaBody: string;
  ctaAction: string;
  planRequired: string;
  certificatePublishPro: string;
  certificatePublishAction: string;
}

const PERIOD = { annual: 'year', monthly: 'month' } as const;
const WORDS = ['no', 'one', 'two', 'three', 'four', 'five', 'six'];

// The pre-contract information (CCRs 2013, Schedule 2): the same words in both modes.
const SHARED = {
  periodLegend: 'Billing period',
  annualLabel: 'Annual',
  monthlyLabel: 'Monthly',
  perPeriod: (price: string, period: BillingPeriod) => `${price}/${PERIOD[period]}`,
  annualSaving: (months: number) => {
    const words = `${WORDS[months] ?? String(months)} ${months === 1 ? 'month' : 'months'}`;
    return `${words.charAt(0).toUpperCase()}${words.slice(1)} free`;
  },
  preContractHeading: 'Before you start',
  includesLabel: 'What Pro includes',
  priceLine: (price: string, period: BillingPeriod) =>
    `Forgeway Pro costs ${price} a ${PERIOD[period]}, including VAT.`,
  renewalLine: (period: BillingPeriod) =>
    `It renews automatically every ${PERIOD[period]} until you cancel. You can cancel at any time from your profile (Manage billing); you keep Pro until the end of the period you have paid for.`,
  trialLine: (days: number, price: string, date: string) =>
    `Your ${days}-day free trial starts today. Your first payment of ${price} will be taken on ${date} unless you cancel before then.`,
  noTrialLine: (price: string) => `Your first payment of ${price} is taken today.`,
  todayLine: (price: string) => `You pay ${price} today.`,
  documentsLabel: 'The documents that apply',
  termsLink: 'Terms of use',
  privacyLink: 'Privacy policy',
  cancellationPolicyLink: 'Cancellation policy',
  cancellationFormLink: 'Model cancellation form',
  consentLegend: 'Your consent',
  consentNeeded: 'Tick the box to agree that Pro starts straight away, then start again.',
  // PECR reg 22: an opt-out where details are collected, worded as the ICO suggests.
  noOffersLabel:
    'Tick this box if you do not want emails about Forgeway offers. You can change this at any time in your profile.',
  startNote: 'You will enter your card on Stripe’s secure checkout page.',
  planLabel: 'Plan',
  statusLabel: 'Status',
  trialEnds: (date: string) => `Your free trial ends on ${date}.`,
  renews: (date: string) => `Renews on ${date}.`,
  ends: (date: string) => `Cancelled: Pro ends on ${date}, and you will not be charged again.`,
  pausedUntil: (date: string) => `Paused until ${date}. Nothing is charged while paused.`,
  manage: 'Manage billing',
  pauseAction: 'Pause',
  resumeAction: 'Resume now',
  cancelAction: 'Cancel subscription',
  pauseMonthsLegend: 'Pause for',
  pauseFor: (months: number) => `${months} ${months === 1 ? 'month' : 'months'}`,
  continueToCancel: 'Continue to cancel',
  keepAsItIs: 'Keep my subscription',
  withdrawHeading: 'Withdraw from contract',
  withdrawBody: (date: string) =>
    `You can withdraw from your contract until ${date}. It ends at once, your account returns to the free plan, and your latest payment is refunded.`,
  withdrawStart: 'Withdraw from contract',
  withdrawConfirmBody: 'Withdraw now? Your contract ends straight away. This cannot be undone.',
  withdrawConfirm: 'Confirm withdrawal',
  withdrawKeep: 'Keep my contract',
  withdrawn: 'You have withdrawn from your contract. We have emailed you a confirmation.',
  pastDueAction: 'Update payment details',
};

const STATUS: Record<string, string> = {
  trialing: 'Free trial',
  active: 'Active',
  past_due: 'Payment overdue',
  canceled: 'Ended',
  unpaid: 'Unpaid',
  paused: 'Paused',
  incomplete: 'Waiting for payment',
  incomplete_expired: 'Ended',
};

const status = (value: string, paused: boolean, cancelling: boolean) =>
  paused ? 'Paused' : cancelling ? 'Cancelled' : (STATUS[value] ?? value);

export const BILLING_COPY: Record<Mode, BillingCopy> = {
  professional: {
    ...SHARED,
    offerHeading: 'Choose your plan',
    start: (days) => (days > 0 ? `Start my ${days}-day free trial` : 'Subscribe to Pro'),
    hasPro: 'Your account has Pro. Everything is open to you.',
    manageInProfile: 'Manage your subscription',
    successTitle: 'Welcome to Forgeway Pro',
    successBody:
      'Your subscription has started and everything is open to you. We have emailed you a confirmation.',
    successPending: 'Confirming your subscription with Stripe. This takes a few seconds.',
    cancelledTitle: 'Checkout cancelled',
    cancelledBody: 'Nothing was charged and nothing has changed. You can start again at any time.',
    backToPro: 'Back to Forgeway Pro',
    toMap: 'Go to your tracks',
    sectionTitle: 'Plan and billing',
    planName: (plan) => (plan === 'free' ? 'Free' : plan === 'team' ? 'Team' : 'Pro'),
    status,
    noSubscription: 'You are on the free plan.',
    seePlans: 'See Forgeway Pro',
    pauseHeading: 'Pause instead?',
    pauseBody:
      'You can pause for up to three months: nothing is charged, Pro is off while paused, and your progress stays as it is. Or carry on and cancel.',
    pauseConfirm: 'Pause my subscription',
    pastDueBanner:
      'Your last Forgeway Pro payment did not go through. You keep Pro while we retry; update your card to keep it.',
    ctaTitle: 'Part of Forgeway Pro',
    ctaBody: 'This exercise is part of Forgeway Pro. Start a free trial to attempt it.',
    ctaAction: 'See plans and the free trial',
    planRequired: 'This is part of Forgeway Pro. Start a free trial from the Pro page to open it.',
    certificatePublishPro: 'Publishing a certificate is part of Forgeway Pro.',
    certificatePublishAction: 'See Forgeway Pro',
  },
  rpg: {
    ...SHARED,
    offerHeading: 'Join the guild',
    start: (days) => (days > 0 ? `Start my ${days}-day free trial` : 'Join the guild'),
    hasPro: 'You are a guild member. Every road is open to you.',
    manageInProfile: 'Manage your membership',
    successTitle: 'Welcome to the guild',
    successBody:
      'Your Forgeway Pro membership has begun and every road is open. A confirmation is on its way to your inbox.',
    successPending:
      'The guild is confirming your membership with Stripe. This takes a few seconds.',
    cancelledTitle: 'You turned back at the gate',
    cancelledBody: 'Nothing was charged and nothing has changed. The guild’s door stays open.',
    backToPro: 'Back to the guild',
    toMap: 'Back to the world',
    sectionTitle: 'Guild membership',
    planName: (plan) =>
      plan === 'free' ? 'Free' : plan === 'team' ? 'Team (guild)' : 'Pro (guild member)',
    status,
    noSubscription: 'You travel on the free plan.',
    seePlans: 'Visit the guild',
    pauseHeading: 'Rest instead?',
    pauseBody:
      'You can pause for up to three months: nothing is charged, guild roads close while paused, and everything you have conquered stays yours. Or carry on and cancel.',
    pauseConfirm: 'Pause my membership',
    pastDueBanner:
      'Your last guild payment did not go through. You keep your membership while we retry; update your card to keep it.',
    ctaTitle: 'A road for guild members',
    ctaBody: 'This quest is part of Forgeway Pro. Start a free trial to take it on.',
    ctaAction: 'Visit the guild and the free trial',
    planRequired:
      'That road is for guild members, in Forgeway Pro. Start a free trial from the guild page to open it.',
    certificatePublishPro: 'Publishing a seal is for guild members, in Forgeway Pro.',
    certificatePublishAction: 'Visit the guild',
  },
};
