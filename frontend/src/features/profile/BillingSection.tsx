import { Link } from '@tanstack/react-router';
import { useEffect, useRef, useState } from 'react';

import { useMe } from '../../api/hooks';
import { useProblemMessage } from '../../api/useProblemMessage';
import { Button } from '../../components/Button';
import { Toggle } from '../../components/Toggle';
import { useLexicon } from '../../theme/useTheme';
import { LINK } from '../auth/fields';
import {
  formatDate,
  useBillingStatus,
  useOpenPortal,
  usePause,
  useResume,
  useWithdraw,
  type SubscriptionInfo,
} from '../pro/billing';

const ALERT = 'm-0 rounded-control bg-danger-soft px-3 py-2 text-sm text-danger';
const LIVE = new Set(['trialing', 'active', 'past_due']);
type Step = 'idle' | 'pause' | 'cancel' | 'withdraw';

function dateLine(sub: SubscriptionInfo, copy: ReturnType<typeof useLexicon>['billing']) {
  if (sub.paused && sub.resumes_at) return copy.pausedUntil(formatDate(sub.resumes_at));
  if (sub.cancelling && sub.ends_at) return copy.ends(formatDate(sub.ends_at));
  if (sub.status === 'trialing' && sub.trial_end) return copy.trialEnds(formatDate(sub.trial_end));
  if (LIVE.has(sub.status) && sub.current_period_end)
    return copy.renews(formatDate(sub.current_period_end));
  return null;
}

/**
 * Plan and billing on the profile (`#billing`), with billing on: the plan, status and next date,
 * Manage billing (Stripe's portal), pause and resume, cancel, and for EU customers within 14
 * days, "Withdraw from contract". Cancel passes one optional pause screen whose "Continue to
 * cancel" is as prominent as pausing, then the portal, where cancelling takes one more click.
 */
export function BillingSection() {
  const copy = useLexicon().billing;
  const me = useMe();
  const status = useBillingStatus();
  const portal = useOpenPortal();
  const pause = usePause();
  const resume = useResume();
  const withdraw = useWithdraw();
  const problemMessage = useProblemMessage();
  const [step, setStep] = useState<Step>('idle');
  const [months, setMonths] = useState<'1' | '2' | '3'>('1');
  const [withdrawn, setWithdrawn] = useState(false);
  const panel = useRef<HTMLDivElement>(null);

  // A second step takes focus, so a keyboard user lands on what it asks.
  useEffect(() => {
    if (step !== 'idle') panel.current?.focus();
  }, [step]);

  if (status.data === undefined) {
    return status.isError ? (
      <p role="alert" className={ALERT}>
        {problemMessage(status.error)}
      </p>
    ) : null;
  }
  const sub = status.data.subscription;
  const live = sub !== null && LIVE.has(sub.status);
  const failure = [portal, pause, resume, withdraw].find((m) => m.isError)?.error;
  const date = sub === null ? null : dateLine(sub, copy);

  return (
    <div className="space-y-4">
      <dl className="m-0 grid max-w-md grid-cols-[auto_1fr] gap-x-6 gap-y-1">
        <dt className="font-medium">{copy.planLabel}</dt>
        <dd className="m-0">{copy.planName(me.data?.plan ?? status.data.plan)}</dd>
        {sub !== null && (
          <>
            <dt className="font-medium">{copy.statusLabel}</dt>
            <dd className="m-0">{copy.status(sub.status, sub.paused, sub.cancelling)}</dd>
          </>
        )}
      </dl>
      {date !== null && <p className="m-0 text-ink-secondary">{date}</p>}
      {withdrawn && (
        <p role="status" className="m-0 text-success">
          {copy.withdrawn}
        </p>
      )}

      {!live && (
        <p className="m-0">
          {copy.noSubscription}{' '}
          <Link to="/pro" className={LINK}>
            {copy.seePlans}
          </Link>
        </p>
      )}

      {sub !== null && step === 'idle' && (
        <div className="flex flex-wrap gap-3">
          <Button
            variant="secondary"
            loading={portal.isPending || portal.isSuccess}
            onClick={() => {
              portal.mutate();
            }}
          >
            {copy.manage}
          </Button>
          {live && sub.paused && (
            <Button
              variant="secondary"
              loading={resume.isPending}
              onClick={() => {
                resume.mutate(undefined);
              }}
            >
              {copy.resumeAction}
            </Button>
          )}
          {live && sub.status === 'active' && !sub.paused && !sub.cancelling && (
            <Button
              variant="secondary"
              onClick={() => {
                setStep('pause');
              }}
            >
              {copy.pauseAction}
            </Button>
          )}
          {live && !sub.cancelling && (
            <Button
              variant="secondary"
              onClick={() => {
                // Only an active, unpaused subscription can pause; any other goes straight on.
                if (sub.status === 'active' && !sub.paused) setStep('cancel');
                else portal.mutate();
              }}
            >
              {copy.cancelAction}
            </Button>
          )}
        </div>
      )}

      {(step === 'pause' || step === 'cancel') && (
        <div
          ref={panel}
          tabIndex={-1}
          role="group"
          aria-labelledby="pause-heading"
          className="max-w-measure space-y-3 rounded-panel border border-line-strong p-4 outline-none"
        >
          <h3 id="pause-heading" className="m-0 text-base font-semibold">
            {copy.pauseHeading}
          </h3>
          <p className="m-0 text-sm text-ink-secondary">{copy.pauseBody}</p>
          <Toggle
            legend={copy.pauseMonthsLegend}
            value={months}
            options={(['1', '2', '3'] as const).map((n) => ({
              value: n,
              label: copy.pauseFor(Number(n)),
            }))}
            onChange={setMonths}
          />
          <div className="flex flex-wrap gap-3">
            <Button
              variant="secondary"
              loading={pause.isPending}
              onClick={() => {
                pause.mutate(Number(months), {
                  onSuccess: () => {
                    setStep('idle');
                  },
                });
              }}
            >
              {copy.pauseConfirm}
            </Button>
            {step === 'cancel' && (
              <Button
                variant="secondary"
                loading={portal.isPending || portal.isSuccess}
                onClick={() => {
                  portal.mutate();
                }}
              >
                {copy.continueToCancel}
              </Button>
            )}
            <Button
              variant="quiet"
              onClick={() => {
                setStep('idle');
              }}
            >
              {copy.keepAsItIs}
            </Button>
          </div>
        </div>
      )}

      {live && sub.withdrawal_until !== null && !withdrawn && (
        <div className="max-w-measure space-y-3 border-t border-line-subtle pt-4">
          <h3 className="m-0 text-base font-semibold">{copy.withdrawHeading}</h3>
          <p className="m-0 text-sm text-ink-secondary">
            {copy.withdrawBody(formatDate(sub.withdrawal_until))}
          </p>
          {step === 'withdraw' ? (
            <div ref={panel} tabIndex={-1} className="space-y-3 outline-none">
              <p className="m-0 font-medium">{copy.withdrawConfirmBody}</p>
              <div className="flex flex-wrap gap-3">
                <Button
                  variant="secondary"
                  className="border-danger text-danger"
                  loading={withdraw.isPending}
                  onClick={() => {
                    withdraw.mutate(undefined, {
                      onSuccess: () => {
                        setStep('idle');
                        setWithdrawn(true);
                      },
                    });
                  }}
                >
                  {copy.withdrawConfirm}
                </Button>
                <Button
                  variant="quiet"
                  onClick={() => {
                    setStep('idle');
                  }}
                >
                  {copy.withdrawKeep}
                </Button>
              </div>
            </div>
          ) : (
            <Button
              variant="secondary"
              className="border-danger text-danger"
              onClick={() => {
                setStep('withdraw');
              }}
            >
              {copy.withdrawStart}
            </Button>
          )}
        </div>
      )}

      {failure != null && (
        <p role="alert" className={ALERT}>
          {problemMessage(failure)}
        </p>
      )}
    </div>
  );
}
