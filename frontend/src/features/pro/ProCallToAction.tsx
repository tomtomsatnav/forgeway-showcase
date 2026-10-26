import { Link } from '@tanstack/react-router';

import { useLexicon } from '../../theme/useTheme';
import { JoinWaitlist } from './JoinWaitlist';

/**
 * Shown on Pro content to a learner whose plan does not include it, where the run button would
 * be: calm, with no price and nothing to buy, only the waitlist.
 */
export function ProCallToAction() {
  const lexicon = useLexicon();
  return (
    <aside
      aria-labelledby="pro-cta-title"
      className="max-w-measure space-y-3 rounded-panel border border-line-strong bg-raised p-4"
    >
      <h2 id="pro-cta-title" className="m-0 text-lg">
        {lexicon.proCtaTitle}
      </h2>
      <p className="m-0 text-ink-secondary">{lexicon.proCtaBody}</p>
      <JoinWaitlist />
      <p className="m-0">
        <Link to="/pro" className="text-accent-strong underline underline-offset-2">
          {lexicon.proLearnMore}
        </Link>
      </p>
    </aside>
  );
}
