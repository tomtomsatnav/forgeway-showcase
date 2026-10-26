import { Link } from '@tanstack/react-router';

import { PageHeader } from '../../theme/slots';
import { useLexicon } from '../../theme/useTheme';

/**
 * Shown in place of the register form once the account exists and its link is on its way. The
 * banner above it (UnverifiedBanner) carries the one "send a new link" button.
 */
export function CheckInbox({ email }: { email: string }) {
  const lexicon = useLexicon();
  return (
    <div className="mx-auto max-w-md space-y-6 px-4 py-12 sm:px-6">
      <PageHeader title={lexicon.checkInboxTitle} summary={lexicon.checkInboxBody(email)} />
      <Link
        to="/"
        className="inline-flex min-h-11 items-center rounded-control bg-accent px-4 font-medium text-on-accent no-underline hover:bg-accent-strong"
      >
        {lexicon.checkInboxContinue}
      </Link>
    </div>
  );
}
