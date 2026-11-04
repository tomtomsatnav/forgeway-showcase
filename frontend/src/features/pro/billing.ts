import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query';

import { api, unwrap } from '../../api/client';
import { meQuery, queryKeys, useMe, usePublicConfig } from '../../api/hooks';
import type { components } from '../../api/schema';
import type { BillingPeriod } from '../../theme/billingLexicon';

export type BillingConfig = components['schemas']['BillingConfig'];
export type BillingStatus = components['schemas']['BillingStatus'];
export type SubscriptionInfo = components['schemas']['SubscriptionInfo'];

const billingKey = ['billing'] as const;

/** The `billing` block of `/api/config` when billing is on; null shows today's waitlist. */
export function useBillingConfig(): BillingConfig | null {
  const billing = usePublicConfig().data?.billing;
  return billing?.enabled === true ? billing : null;
}

/**
 * Whether billing is on, read from the config already cached, without fetching it. For parts of
 * pages that load the config themselves (the profile does), so they add no request of their own.
 */
export function useBillingOnCached(): boolean {
  const config = useQueryClient().getQueryData<{ billing?: { enabled?: boolean } | null }>(
    queryKeys.config,
  );
  return config?.billing?.enabled === true;
}

/** The learner's subscription, the trial they would get and the consent wording. */
export function useBillingStatus(enabled = true) {
  const me = useMe();
  const on = useBillingConfig() !== null;
  return useQuery({
    queryKey: billingKey,
    queryFn: async () => unwrap(await api.GET('/api/billing')),
    enabled: enabled && on && me.data != null,
  });
}

/** Opens a URL the API handed out (Stripe Checkout or the Customer Portal). */
export function goTo(url: string): void {
  window.location.assign(url);
}

export function useStartCheckout() {
  return useMutation({
    mutationFn: async (body: {
      plan: BillingPeriod;
      consent: boolean;
      consent_version: string;
      marketing_opt_out: boolean;
    }) => unwrap(await api.POST('/api/billing/checkout', { body })),
    onSuccess: ({ url }) => {
      goTo(url);
    },
  });
}

export function useOpenPortal() {
  return useMutation({
    mutationFn: async () => unwrap(await api.POST('/api/billing/portal')),
    onSuccess: ({ url }) => {
      goTo(url);
    },
  });
}

/** Pause, resume and withdraw answer the new status; the plan may change with them. */
function useBillingChange<T>(call: (body: T) => Promise<BillingStatus>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: call,
    onSuccess: async (status) => {
      client.setQueryData(billingKey, status);
      await client.query({ ...meQuery, staleTime: 0 });
      void client.invalidateQueries({ queryKey: queryKeys.map });
    },
  });
}

export const usePause = () =>
  useBillingChange(async (months: number) =>
    unwrap(await api.POST('/api/billing/pause', { body: { months } })),
  );
export const useResume = () =>
  useBillingChange(async () => unwrap(await api.POST('/api/billing/resume')));
export const useWithdraw = () =>
  useBillingChange(async () => unwrap(await api.POST('/api/billing/withdraw')));

/** Refetch the learner and their subscription, as after returning from Checkout. */
export async function refreshBilling(client: QueryClient): Promise<void> {
  await client.query({ ...meQuery, staleTime: 0 });
  await client.invalidateQueries({ queryKey: billingKey });
  void client.invalidateQueries({ queryKey: queryKeys.map });
}

/** "£19", "£9.50": whole amounts without pence. Prices include VAT. */
export function formatPrice(minor: number, currency = 'GBP'): string {
  return new Intl.NumberFormat('en-GB', {
    style: 'currency',
    currency,
    minimumFractionDigits: minor % 100 === 0 ? 0 : 2,
  }).format(minor / 100);
}

/** "10 November 2026", in the learner's own time zone. */
export function formatDate(value: Date | string): string {
  return new Intl.DateTimeFormat('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(typeof value === 'string' ? new Date(value) : value);
}

/**
 * When the first payment is taken: Stripe ends a trial exactly `trialDays` × 24 hours after it
 * starts, so this is that instant (today, without a trial). Shown as a date in local time.
 */
export function firstChargeDate(now: Date, trialDays: number): Date {
  return new Date(now.getTime() + Math.max(trialDays, 0) * 24 * 60 * 60 * 1000);
}

export function priceFor(config: BillingConfig, period: BillingPeriod): number {
  return period === 'annual' ? config.annual_price_minor : config.monthly_price_minor;
}

/** How many months the annual price saves, when it is a whole number of them; else null. */
export function monthsFree(config: BillingConfig): number | null {
  const saved = config.monthly_price_minor * 12 - config.annual_price_minor;
  const months = saved / config.monthly_price_minor;
  return saved > 0 && Number.isInteger(months) ? months : null;
}
