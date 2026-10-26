import { Link } from '@tanstack/react-router';
import { useEffect, useRef } from 'react';

import { errorMessage } from '../../api/errors';
import { useMe, useVerifyEmail } from '../../api/hooks';
import { PageHeader } from '../../theme/slots';
import { useLexicon } from '../../theme/useTheme';
import { LINK } from './fields';
import { ResendVerification } from './ResendVerification';

/** The target of the emailed link: /verify-email?token=… */
export function VerifyEmailPage({ token }: { token: string | undefined }) {
  const lexicon = useLexicon();
  const verify = useVerifyEmail();
  const me = useMe();
  const sent = useRef(false);

  useEffect(() => {
    // Once only: a token works a single time, and React may run effects twice in development.
    if (token === undefined || sent.current) return;
    sent.current = true;
    verify.mutate(token);
  }, [token, verify]);

  const signedIn = me.data != null;
  let body;
  if (token === undefined) {
    body = (
      <p role="alert" className="m-0 text-danger">
        {lexicon.verifyLinkIncomplete}
      </p>
    );
  } else if (verify.isSuccess) {
    body = (
      <>
        <p className="m-0">{lexicon.emailVerifiedBody}</p>
        <Link to={signedIn ? '/' : '/sign-in'} className={LINK}>
          {signedIn ? lexicon.checkInboxContinue : lexicon.signIn}
        </Link>
      </>
    );
  } else if (verify.isError) {
    body = (
      <>
        <p role="alert" className="m-0 text-danger">
          {errorMessage(verify.error)}
        </p>
        {signedIn ? (
          <ResendVerification />
        ) : (
          <Link to="/sign-in" className={LINK}>
            {lexicon.signIn}
          </Link>
        )}
      </>
    );
  } else {
    body = <p className="m-0">{lexicon.verifyingEmail}</p>;
  }

  return (
    <div className="mx-auto max-w-md space-y-6 px-4 py-12 sm:px-6">
      <PageHeader
        title={verify.isSuccess ? lexicon.emailVerifiedTitle : lexicon.verifyEmailTitle}
      />
      <div aria-live="polite" className="space-y-4">
        {body}
      </div>
    </div>
  );
}
