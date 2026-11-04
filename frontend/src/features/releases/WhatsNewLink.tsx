import { Link } from '@tanstack/react-router';
import { ScrollText } from 'lucide-react';

import { useReleases } from '../../api/hooks';
import { useLexicon } from '../../theme/useTheme';

/** The header link to "What's new" (the Chronicle), with a dot while a release is unread. */
export function WhatsNewLink() {
  const lexicon = useLexicon();
  const unread = useReleases().data?.unread === true;
  return (
    <Link
      to="/whats-new"
      data-unread={unread ? '' : undefined}
      className="relative inline-flex min-h-11 items-center gap-2 text-ink no-underline hover:underline aria-[current=page]:underline aria-[current=page]:underline-offset-4"
    >
      <ScrollText aria-hidden="true" className="h-4 w-4" />
      {lexicon.whatsNew}
      {unread && (
        <>
          <span aria-hidden="true" className="h-2 w-2 rounded-full bg-accent" />
          <span className="sr-only">{`, ${lexicon.whatsNewUnread}`}</span>
        </>
      )}
    </Link>
  );
}
