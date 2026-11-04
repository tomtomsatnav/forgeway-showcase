import { Link } from '@tanstack/react-router';
import { useId, useState, type FormEvent } from 'react';

import { useProblemMessage } from '../../api/useProblemMessage';
import { Button } from '../../components/Button';
import { Toggle } from '../../components/Toggle';
import type { BillingPeriod } from '../../theme/billingLexicon';
import { useLexicon } from '../../theme/useTheme';
import { LINK } from '../auth/fields';
import {
  firstChargeDate,
  formatDate,
  formatPrice,
  monthsFree,
  priceFor,
  useBillingStatus,
  useStartCheckout,
  type BillingConfig,
} from './billing';

/**
 * The plan toggle (annual first), the pre-contract information the law asks for immediately
 * before the order (CCRs 2013, Schedule 2), the regulation-37 consent and the start button,
 * which opens Stripe Checkout. `now` is for tests.
 */
export function ProOffer({ config, now }: { config: BillingConfig; now?: Date }) {
  const lexicon = useLexicon();
  const copy = lexicon.billing;
  const status = useBillingStatus();
  const checkout = useStartCheckout();
  const problemMessage = useProblemMessage();
  const [period, setPeriod] = useState<BillingPeriod>('annual');
  const [consented, setConsented] = useState(false);
  const [missingConsent, setMissingConsent] = useState(false);
  const [noOffers, setNoOffers] = useState(false);
  const consentId = useId();
  const noOffersId = useId();

  // The trial this learner gets: none after a first subscription. The config's offer until known.
  const trialDays =
    status.data?.trial_days ??
    (config.intro_offer?.kind === 'trial_days' ? config.intro_offer.value : 0);
  const amount = formatPrice(priceFor(config, period), config.currency);
  const firstCharge = formatDate(firstChargeDate(now ?? new Date(), trialDays));
  const saving = monthsFree(config);
  const consent = status.data?.consent;

  const live = status.data?.subscription?.status;
  if (live === 'trialing' || live === 'active' || live === 'past_due') {
    // A paused subscription is still a contract: manage it rather than start another.
    return (
      <p className="m-0 font-medium">
        <Link to="/profile" hash="billing" className={LINK}>
          {copy.manageInProfile}
        </Link>
      </p>
    );
  }

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!consented || consent === undefined) {
      setMissingConsent(true);
      return;
    }
    checkout.mutate({
      plan: period,
      consent: true,
      consent_version: consent.version,
      marketing_opt_out: noOffers,
    });
  };

  return (
    <form onSubmit={submit} className="space-y-6" aria-labelledby="offer-heading" noValidate>
      <h2 id="offer-heading" className="m-0 text-xl">
        {copy.offerHeading}
      </h2>
      <div className="space-y-2">
        <Toggle
          legend={copy.periodLegend}
          value={period}
          options={[
            { value: 'annual', label: copy.annualLabel },
            { value: 'monthly', label: copy.monthlyLabel },
          ]}
          onChange={setPeriod}
        />
        <p className="tabular m-0 text-2xl font-semibold">
          {copy.perPeriod(amount, period)}
          {period === 'annual' && saving !== null && (
            <span className="ml-3 text-base font-medium text-accent-strong">
              {copy.annualSaving(saving)}
            </span>
          )}
        </p>
      </div>

      <section
        aria-labelledby="pre-contract-heading"
        className="space-y-3 rounded-panel border border-line-strong bg-raised p-4"
      >
        <h3 id="pre-contract-heading" className="m-0 text-lg">
          {copy.preContractHeading}
        </h3>
        <div>
          <p className="m-0 font-medium">{copy.includesLabel}</p>
          <ul className="m-0 mt-1 pl-6">
            {lexicon.proIncludes.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <p className="m-0">
          {copy.priceLine(amount, period)} {copy.renewalLine(period)}
        </p>
        <p className="m-0">
          {trialDays > 0
            ? copy.trialLine(trialDays, amount, firstCharge)
            : copy.noTrialLine(amount)}
        </p>
        <p className="m-0 font-semibold">
          {copy.todayLine(trialDays > 0 ? formatPrice(0, config.currency) : amount)}
        </p>
        <nav aria-label={copy.documentsLabel}>
          <ul className="m-0 flex list-none flex-wrap gap-x-4 gap-y-1 p-0 text-sm">
            <li>
              <Link to="/terms" className={LINK}>
                {copy.termsLink}
              </Link>
            </li>
            <li>
              <Link to="/privacy" className={LINK}>
                {copy.privacyLink}
              </Link>
            </li>
            <li>
              <Link to="/terms" hash="cancellation" className={LINK}>
                {copy.cancellationPolicyLink}
              </Link>
            </li>
            <li>
              <Link to="/terms" hash="cancellation-form" className={LINK}>
                {copy.cancellationFormLink}
              </Link>
            </li>
          </ul>
        </nav>
      </section>

      <fieldset className="m-0 space-y-2 border-0 p-0">
        <legend className="sr-only">{copy.consentLegend}</legend>
        <div className="flex items-start gap-3">
          <input
            id={consentId}
            type="checkbox"
            className="mt-1 h-5 w-5 shrink-0 accent-[var(--accent)]"
            checked={consented}
            disabled={consent === undefined}
            aria-invalid={missingConsent && !consented ? true : undefined}
            aria-describedby={missingConsent && !consented ? `${consentId}-error` : undefined}
            onChange={(event) => {
              setConsented(event.target.checked);
              if (event.target.checked) setMissingConsent(false);
            }}
          />
          <label htmlFor={consentId} className="max-w-measure">
            {consent ? `${consent.express} ${consent.acknowledgement}` : '…'}
          </label>
        </div>
        {missingConsent && !consented && (
          <p id={`${consentId}-error`} role="alert" className="m-0 text-sm text-danger">
            {copy.consentNeeded}
          </p>
        )}
      </fieldset>

      <div className="flex items-start gap-3">
        <input
          id={noOffersId}
          type="checkbox"
          className="mt-1 h-5 w-5 shrink-0 accent-[var(--accent)]"
          checked={noOffers}
          onChange={(event) => {
            setNoOffers(event.target.checked);
          }}
        />
        <label htmlFor={noOffersId} className="max-w-measure text-sm">
          {copy.noOffersLabel}
        </label>
      </div>

      <div className="space-y-2">
        <Button type="submit" loading={checkout.isPending || checkout.isSuccess}>
          {copy.start(trialDays)}
        </Button>
        <p className="m-0 text-sm text-ink-secondary">{copy.startNote}</p>
        {checkout.isError && (
          <p role="alert" className="m-0 text-sm text-danger">
            {problemMessage(checkout.error)}
          </p>
        )}
      </div>
    </form>
  );
}
