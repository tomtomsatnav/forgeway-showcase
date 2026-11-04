import { Link } from '@tanstack/react-router';
import { Check } from 'lucide-react';

import { useMe, usePublicConfig } from '../../api/hooks';
import { ProMark } from '../../components/ProMark';
import { PageHeader } from '../../theme/slots';
import { useLexicon } from '../../theme/useTheme';
import { LINK } from '../auth/fields';
import { useBillingConfig } from './billing';
import { JoinWaitlist } from './JoinWaitlist';
import { ProOffer } from './ProOffer';

const DEFAULT_FREE_PER_TRACK = 3;

/**
 * What Forgeway Pro includes, what stays free, and the waitlist. With billing on, the waitlist
 * gives way to the plans, the pre-contract information and Checkout.
 */
export function ProPage() {
  const lexicon = useLexicon();
  const me = useMe();
  const config = usePublicConfig();
  const billing = useBillingConfig();
  const perTrack = config.data?.free_exercises_per_branch ?? DEFAULT_FREE_PER_TRACK;
  const hasPro = me.data != null && me.data.plan !== 'free';

  return (
    <div className="mx-auto max-w-page space-y-8 px-4 py-8 sm:px-6">
      <PageHeader title={lexicon.proPageTitle} summary={lexicon.proPageSummary} />

      <section aria-labelledby="pro-includes" className="max-w-measure space-y-3">
        <h2 id="pro-includes" className="m-0 flex items-center gap-3 text-xl">
          {lexicon.proIncludesHeading}
          <ProMark />
        </h2>
        <ul className="m-0 list-none space-y-2 p-0">
          {lexicon.proIncludes.map((item) => (
            <li key={item} className="flex items-start gap-2">
              <Check aria-hidden="true" className="mt-1 h-4 w-4 shrink-0 text-accent-strong" />
              {item}
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="pro-free" className="max-w-measure space-y-3">
        <h2 id="pro-free" className="m-0 text-xl">
          {lexicon.proFreeHeading}
        </h2>
        <p className="m-0">{lexicon.proFree(perTrack)}</p>
      </section>

      <section
        aria-label={billing === null ? lexicon.proJoin : lexicon.billing.offerHeading}
        className="max-w-measure space-y-3 border-t border-line-subtle pt-6"
      >
        {hasPro && billing !== null ? (
          <p className="m-0 font-medium">
            {lexicon.billing.hasPro}{' '}
            <Link to="/profile" hash="billing" className={LINK}>
              {lexicon.billing.manageInProfile}
            </Link>
          </p>
        ) : hasPro ? (
          <p className="m-0 font-medium">{lexicon.proHasPlan}</p>
        ) : billing !== null ? (
          <ProOffer config={billing} />
        ) : (
          <>
            <p className="m-0 text-ink-secondary">{lexicon.proNoBilling}</p>
            <JoinWaitlist />
          </>
        )}
      </section>
    </div>
  );
}
