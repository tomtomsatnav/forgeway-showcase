import { useQueryClient } from '@tanstack/react-query';
import { Link } from '@tanstack/react-router';
import { useEffect } from 'react';

import { useMe } from '../../api/hooks';
import { PageHeader } from '../../theme/slots';
import { useLexicon } from '../../theme/useTheme';
import { LINK } from '../auth/fields';
import { refreshBilling } from './billing';

const POLL_MS = 2000;
const POLLS = 15;

/**
 * Where Checkout returns after payment. Stripe's webhook may land a moment after the browser,
 * so the page re-reads the account until Pro shows (for up to half a minute).
 */
export function CheckoutSuccessPage() {
  const copy = useLexicon().billing;
  const me = useMe();
  const client = useQueryClient();
  const hasPro = me.data != null && me.data.plan !== 'free';

  useEffect(() => {
    if (hasPro) return;
    let polls = 0;
    const timer = window.setInterval(() => {
      polls += 1;
      if (polls > POLLS) window.clearInterval(timer);
      else void refreshBilling(client);
    }, POLL_MS);
    void refreshBilling(client);
    return () => {
      window.clearInterval(timer);
    };
  }, [hasPro, client]);

  return (
    <div className="mx-auto max-w-page space-y-6 px-4 py-8 sm:px-6">
      <PageHeader
        title={copy.successTitle}
        summary={hasPro ? copy.successBody : copy.successPending}
      />
      <p role="status" className="sr-only">
        {hasPro ? copy.successBody : copy.successPending}
      </p>
      <p className="m-0">
        <Link to="/" className={LINK}>
          {copy.toMap}
        </Link>
      </p>
    </div>
  );
}

/** Where Checkout returns when the learner backs out. Nothing was charged. */
export function CheckoutCancelledPage() {
  const copy = useLexicon().billing;
  return (
    <div className="mx-auto max-w-page space-y-6 px-4 py-8 sm:px-6">
      <PageHeader title={copy.cancelledTitle} summary={copy.cancelledBody} />
      <p className="m-0">
        <Link to="/pro" className={LINK}>
          {copy.backToPro}
        </Link>
      </p>
    </div>
  );
}
