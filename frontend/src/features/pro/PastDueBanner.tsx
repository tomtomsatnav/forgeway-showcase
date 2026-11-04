import { Button } from '../../components/Button';
import { useLexicon } from '../../theme/useTheme';
import { useBillingStatus, useOpenPortal } from './billing';

/** Under the header, on every page, while a renewal payment has failed and Stripe retries it. */
export function PastDueBanner() {
  const copy = useLexicon().billing;
  const status = useBillingStatus();
  const portal = useOpenPortal();
  if (status.data?.subscription?.status !== 'past_due') return null;
  return (
    <section aria-label="Payment overdue" className="border-b border-line-subtle bg-warning-soft">
      <div className="mx-auto flex max-w-page flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
        <p className="m-0 flex-1 basis-64 text-sm">{copy.pastDueBanner}</p>
        <Button
          variant="secondary"
          loading={portal.isPending || portal.isSuccess}
          onClick={() => {
            portal.mutate();
          }}
        >
          {copy.pastDueAction}
        </Button>
      </div>
    </section>
  );
}
