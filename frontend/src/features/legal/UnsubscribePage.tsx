import { Link } from '@tanstack/react-router';
import { useEffect, useRef } from 'react';

import { errorMessage } from '../../api/errors';
import { useUnsubscribe } from '../../api/hooks';
import { PageHeader } from '../../theme/slots';
import { LINK } from '../auth/fields';

/** The target of the link in every marketing email: /unsubscribe?token=… No sign-in needed. */
export function UnsubscribePage({ token }: { token: string | undefined }) {
  const unsubscribe = useUnsubscribe();
  const sent = useRef(false);

  useEffect(() => {
    // Once: React may run effects twice in development (a second call would be harmless).
    if (token === undefined || sent.current) return;
    sent.current = true;
    unsubscribe.mutate(token);
  }, [token, unsubscribe]);

  let body;
  if (token === undefined) {
    body = (
      <p role="alert" className="m-0 text-danger">
        This link is incomplete. Turn off offers in your profile (Settings) instead.
      </p>
    );
  } else if (unsubscribe.isSuccess) {
    body = (
      <p className="m-0">
        You will get no more emails about Forgeway offers. Emails about your account and payments
        still arrive. You can change this in{' '}
        <Link to="/profile" className={LINK}>
          your profile
        </Link>
        .
      </p>
    );
  } else if (unsubscribe.isError) {
    body = (
      <p role="alert" className="m-0 text-danger">
        {errorMessage(unsubscribe.error)}
      </p>
    );
  } else {
    body = <p className="m-0">Unsubscribing…</p>;
  }

  return (
    <div className="mx-auto max-w-md space-y-6 px-4 py-12 sm:px-6">
      <PageHeader title={unsubscribe.isSuccess ? 'You are unsubscribed' : 'Unsubscribe'} />
      <div aria-live="polite" className="space-y-4">
        {body}
      </div>
    </div>
  );
}
