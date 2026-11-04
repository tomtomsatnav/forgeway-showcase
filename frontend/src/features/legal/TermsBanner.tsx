import { Link } from '@tanstack/react-router';

import { errorMessage } from '../../api/errors';
import { useAcceptTerms, useMe } from '../../api/hooks';
import { Button } from '../../components/Button';
import { useLexicon } from '../../theme/useTheme';
import { LINK } from '../auth/fields';
import { TERMS_VERSION } from './LegalPages';

/** Under the header for signed-in learners who have not accepted the current terms. */
export function TermsBanner() {
  const { termsChanged, termsLegal: legal } = useLexicon();
  const me = useMe();
  const accept = useAcceptTerms();
  if (me.data?.terms_current !== false) return null;
  return (
    <section aria-label="Updated terms" className="border-b border-line-subtle bg-sunken">
      <div className="mx-auto flex max-w-page flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
        <p className="m-0 flex-1 basis-64 text-sm">
          {termsChanged} {legal.before}
          <Link to="/terms" className={LINK}>
            {legal.terms}
          </Link>
          {legal.between}
          <Link to="/privacy" className={LINK}>
            {legal.privacy}
          </Link>
          {legal.after}
        </p>
        <Button
          variant="secondary"
          loading={accept.isPending}
          onClick={() => {
            accept.mutate(TERMS_VERSION, {
              // The button goes with the banner: keep keyboard focus from falling to the body.
              onSuccess: () => {
                document.getElementById('main')?.focus();
              },
            });
          }}
        >
          {legal.accept}
        </Button>
        {accept.isError && (
          <p role="alert" className="m-0 basis-full text-sm text-danger">
            {errorMessage(accept.error)}
          </p>
        )}
      </div>
    </section>
  );
}
