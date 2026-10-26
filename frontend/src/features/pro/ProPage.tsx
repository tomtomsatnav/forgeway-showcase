import { Check } from 'lucide-react';

import { useMe, usePublicConfig } from '../../api/hooks';
import { ProMark } from '../../components/ProMark';
import { PageHeader } from '../../theme/slots';
import { useLexicon } from '../../theme/useTheme';
import { JoinWaitlist } from './JoinWaitlist';

const DEFAULT_FREE_PER_TRACK = 3;

/** What Forgeway Pro includes, what stays free, and the waitlist. No prices: nothing is on sale. */
export function ProPage() {
  const lexicon = useLexicon();
  const me = useMe();
  const config = usePublicConfig();
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
        aria-label={lexicon.proJoin}
        className="max-w-measure space-y-3 border-t border-line-subtle pt-6"
      >
        {hasPro ? (
          <p className="m-0 font-medium">{lexicon.proHasPlan}</p>
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
