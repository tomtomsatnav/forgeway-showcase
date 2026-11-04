import { errorMessage } from '../../api/errors';
import { useMe, useUpdateProfile } from '../../api/hooks';

/**
 * The marketing preference (PECR reg 22). Offers go only to trial and Pro customers who have
 * not opted out; each change saves at once. Service emails, such as receipts, are not affected.
 */
export function MarketingField() {
  const me = useMe();
  const update = useUpdateProfile();
  if (!me.data) return null;
  const wanted = !(update.variables?.marketing_opt_out ?? me.data.profile.marketing_opt_out);

  return (
    <div className="space-y-1">
      <div className="flex items-start gap-3">
        <input
          id="marketing-emails"
          type="checkbox"
          className="mt-1 h-5 w-5 shrink-0 accent-[var(--accent)]"
          checked={wanted}
          disabled={update.isPending}
          aria-describedby="marketing-emails-hint"
          onChange={(event) => {
            update.mutate({ marketing_opt_out: !event.target.checked });
          }}
        />
        <label htmlFor="marketing-emails" className="text-sm font-medium">
          Send me emails about Forgeway offers
        </label>
      </div>
      <p id="marketing-emails-hint" className="m-0 max-w-measure text-sm text-ink-muted">
        Only while you have a trial or a subscription. Emails about your account and payments are
        sent either way.
      </p>
      {update.isError && (
        <p role="alert" className="m-0 text-sm text-danger">
          {errorMessage(update.error)}
        </p>
      )}
    </div>
  );
}
