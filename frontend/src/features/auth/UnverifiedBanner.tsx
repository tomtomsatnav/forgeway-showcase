import { useMe } from '../../api/hooks';
import { useLexicon } from '../../theme/useTheme';
import { ResendVerification } from './ResendVerification';

/** Under the header for signed-in learners who have not verified their email address yet. */
export function UnverifiedBanner() {
  const lexicon = useLexicon();
  const me = useMe();
  if (me.data == null || me.data.email_verified) return null;
  return (
    <section aria-label="Email verification" className="border-b border-line-subtle bg-sunken">
      <div className="mx-auto flex max-w-page flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
        <p className="m-0 flex-1 basis-64 text-sm">{lexicon.unverifiedBanner}</p>
        <ResendVerification variant="quiet" />
      </div>
    </section>
  );
}
