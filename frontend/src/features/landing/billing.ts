import type { Lexicon } from '../../theme/lexicon';

/**
 * The `billing` object `/api/config` will gain once Stripe billing exists. Prices are in minor
 * units (pence) and include VAT.
 * shortcut: declared here, not generated, until the backend ships it and `gen:api` picks it up.
 */
export interface Billing {
  enabled: boolean;
  currency: string;
  monthly_price_minor: number;
  annual_price_minor: number;
  intro_offer: {
    kind: 'percent_off_first_month' | 'trial_days' | null;
    value: number;
  } | null;
}

/** The billing settings when billing is switched on; null shows the waitlist and no prices. */
export function activeBilling(config: object | undefined): Billing | null {
  const billing = (config as { billing?: Billing | null } | undefined)?.billing;
  return billing?.enabled === true ? billing : null;
}

/** "£19", "£9.50": whole amounts without pence. */
export function formatPrice(minor: number, currency: string): string {
  return new Intl.NumberFormat('en-GB', {
    style: 'currency',
    currency,
    minimumFractionDigits: minor % 100 === 0 ? 0 : 2,
  }).format(minor / 100);
}

export type Period = 'annual' | 'monthly';

export interface PriceLines {
  /** "£190/year" or "£19/month", for the chosen period. */
  price: string;
  /** Beside the annual price: "Two months free", or what it saves; null when it saves nothing. */
  saving: string | null;
  /** The trial, naming the chosen plan first; null without a trial. */
  trial: string | null;
}

/**
 * What the pricing block says for the chosen period. Only a trial is shown as an offer: a
 * percentage coupon is a promotion code, never applied automatically (docs/plans/billing.md).
 */
export function priceLines(billing: Billing, period: Period, copy: Lexicon['landing']): PriceLines {
  const price = (minor: number) => formatPrice(minor, billing.currency);
  const monthly = copy.plansPerMonth(price(billing.monthly_price_minor));
  const annual = copy.plansPerYear(price(billing.annual_price_minor));
  const saved = billing.monthly_price_minor * 12 - billing.annual_price_minor;
  const months = saved / billing.monthly_price_minor;
  const offer = billing.intro_offer;
  const [first, second] = period === 'annual' ? [annual, monthly] : [monthly, annual];
  return {
    price: first,
    saving:
      saved <= 0
        ? null
        : Number.isInteger(months)
          ? copy.plansMonthsFree(months)
          : copy.plansAnnualSaving(price(saved)),
    trial:
      offer?.kind === 'trial_days' && offer.value > 0
        ? copy.plansTrial(offer.value, first, second)
        : null,
  };
}
