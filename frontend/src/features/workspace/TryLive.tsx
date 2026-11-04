import { Radio } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { ApiError, formatResetTime } from '../../api/errors';
import {
  useAcknowledgeLiveNotice,
  useLiveNotice,
  useLiveRun,
  usePublicConfig,
  useStartLiveRun,
} from '../../api/hooks';
import type { LiveAllowance, LiveRunDetail } from '../../api/types';
import { useProblemMessage } from '../../api/useProblemMessage';
import { Button } from '../../components/Button';
import { useLexicon } from '../../theme/useTheme';

/** Costs are fractions of a cent, so they keep enough places to read. */
export function formatUsd(usd: number): string {
  if (usd === 0) return '$0.00';
  return usd < 0.01 ? `$${usd.toFixed(6)}` : `$${usd.toFixed(2)}`;
}

/**
 * Runs the learner's current code with the exercise's `live.py` against Forgeway's model, paid
 * for by the platform (ADR 0012), and shows what it printed and what each model call cost. Grades
 * still come from the checks, and the learner's own key is never involved. Hidden while the
 * server has live runs switched off.
 */
export function TryLive({
  exerciseId,
  files,
  hasLiveExample,
}: {
  exerciseId: string;
  files: Record<string, string>;
  hasLiveExample: boolean;
}) {
  const lexicon = useLexicon();
  const config = usePublicConfig();
  const start = useStartLiveRun(exerciseId);
  const [runId, setRunId] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const run = useLiveRun(runId);
  const enabled = config.data?.live_runs === true;
  const notice = useLiveNotice(enabled);
  const acknowledge = useAcknowledgeLiveNotice();

  if (!enabled) return null;
  const model = config.data?.live_model ?? 'a real model';
  const detail = run.data ?? start.data;
  const busy =
    start.isPending ||
    (detail !== undefined && detail.status !== 'finished' && detail.status !== 'errored');

  const begin = () => {
    start.mutate(files, {
      onSuccess: (started) => {
        setRunId(started.id);
      },
      onError: (error) => {
        if (error instanceof ApiError && error.code === 'live-notice-required') {
          void notice.refetch();
        }
      },
    });
  };
  // The data notice comes first, once per wording (UK GDPR transparency; ADR 0012).
  const needsNotice = notice.data !== undefined && !notice.data.acknowledged;

  return (
    <>
      <Button
        id="try-live"
        variant="secondary"
        onClick={() => {
          setOpen(true);
          if (!needsNotice) begin();
        }}
        loading={busy}
        disabled={!hasLiveExample}
        aria-describedby={hasLiveExample ? undefined : 'try-live-reason'}
      >
        <Radio aria-hidden="true" className="h-4 w-4" />
        {lexicon.tryLive}
      </Button>
      {!hasLiveExample && (
        <p id="try-live-reason" className="m-0 text-sm text-ink-secondary">
          {lexicon.tryLiveNoExample}
        </p>
      )}
      {open && (
        <TryLivePanel
          model={model}
          busy={busy}
          detail={detail}
          error={start.isError ? start.error : acknowledge.isError ? acknowledge.error : null}
          notice={needsNotice ? notice.data.text : null}
          accepting={acknowledge.isPending}
          onAccept={() => {
            if (notice.data === undefined) return;
            acknowledge.mutate(notice.data.version, { onSuccess: begin });
          }}
          onClose={() => {
            setOpen(false);
            document.getElementById('try-live')?.focus();
          }}
        />
      )}
    </>
  );
}

function TryLivePanel({
  model,
  busy,
  detail,
  error,
  notice,
  accepting,
  onAccept,
  onClose,
}: {
  model: string;
  busy: boolean;
  detail: LiveRunDetail | undefined;
  error: unknown;
  notice: string | null;
  accepting: boolean;
  onAccept: () => void;
  onClose: () => void;
}) {
  const lexicon = useLexicon();
  const problemMessage = useProblemMessage();
  const panel = useRef<HTMLElement>(null);
  useEffect(() => {
    panel.current?.focus();
  }, []);
  const finished = detail !== undefined && !busy;
  return (
    <section
      ref={panel}
      tabIndex={-1}
      aria-label={lexicon.tryLive}
      className="basis-full space-y-3 rounded-control border border-line-strong bg-raised p-3 text-sm"
    >
      <p className="m-0 text-ink">{lexicon.tryLiveIntro(model)}</p>
      <p className="m-0 text-ink-secondary">{lexicon.tryLiveGrades}</p>
      {notice !== null && (
        <div className="space-y-2 rounded-control border border-warning bg-warning-soft p-3">
          <h3 className="m-0 text-base">{lexicon.tryLiveNoticeHeading}</h3>
          <p className="m-0 text-ink">{notice}</p>
          <Button onClick={onAccept} loading={accepting}>
            {lexicon.tryLiveNoticeAccept}
          </Button>
        </div>
      )}
      {error !== null && (
        <p role="alert" className="m-0 rounded-control bg-danger-soft px-3 py-2 text-danger">
          {problemMessage(error)}
        </p>
      )}
      <p role="status" aria-live="polite" className="m-0 font-semibold text-ink">
        {busy ? lexicon.tryLiveRunning : finished && detail.message ? detail.message : ''}
      </p>
      {finished && <LiveRunResult detail={detail} />}
      {detail && <AllowanceLine allowance={detail.allowance} />}
      <Button variant="quiet" onClick={onClose}>
        Close
      </Button>
    </section>
  );
}

function Output({ label, text, truncated }: { label: string; text: string; truncated: boolean }) {
  if (text === '') return null;
  return (
    <div className="space-y-1">
      <p className="m-0 font-semibold text-ink">{label}</p>
      <pre
        tabIndex={0}
        aria-label={label}
        className="m-0 max-h-72 overflow-auto whitespace-pre-wrap rounded-control bg-sunken p-3 font-mono text-sm leading-6 text-ink"
      >
        {text}
      </pre>
      {truncated && (
        <p className="m-0 text-ink-secondary">Only the start of this output is shown.</p>
      )}
    </div>
  );
}

function LiveRunResult({ detail }: { detail: LiveRunDetail }) {
  return (
    <div className="space-y-3">
      <Output label="Output" text={detail.stdout} truncated={detail.stdout_truncated} />
      <Output label="Errors" text={detail.stderr} truncated={detail.stderr_truncated} />
      {detail.calls.length > 0 && (
        <div className="overflow-x-auto">
          <table className="tabular w-full border-collapse text-left">
            <caption className="label-caps mb-1 text-left text-ink-secondary">Model calls</caption>
            <thead>
              <tr className="border-b border-line-strong">
                <th scope="col" className="py-1 pr-3 font-semibold">
                  Model
                </th>
                <th scope="col" className="py-1 pr-3 text-right font-semibold">
                  Tokens in
                </th>
                <th scope="col" className="py-1 pr-3 text-right font-semibold">
                  Tokens out
                </th>
                <th scope="col" className="py-1 pr-3 text-right font-semibold">
                  Cost
                </th>
                <th scope="col" className="py-1 text-right font-semibold">
                  Latency
                </th>
              </tr>
            </thead>
            <tbody>
              {detail.calls.map((call, index) => (
                <tr key={index} className="border-b border-line-subtle">
                  <td className="py-1 pr-3">
                    {call.model}
                    {call.outcome !== 'ok' && (
                      <span className="text-danger"> ({call.outcome.replace('_', ' ')})</span>
                    )}
                  </td>
                  <td className="py-1 pr-3 text-right">
                    {call.input_tokens.toLocaleString('en-GB')}
                    {call.cache_read_tokens > 0 && (
                      <span className="text-ink-secondary">
                        {' '}
                        ({call.cache_read_tokens.toLocaleString('en-GB')} cached)
                      </span>
                    )}
                  </td>
                  <td className="py-1 pr-3 text-right">
                    {call.output_tokens.toLocaleString('en-GB')}
                  </td>
                  <td className="py-1 pr-3 text-right">{formatUsd(call.cost_usd)}</td>
                  <td className="py-1 text-right">{call.latency_ms.toLocaleString('en-GB')} ms</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <th scope="row" colSpan={3} className="py-1 pr-3 font-semibold">
                  Total
                </th>
                <td className="py-1 pr-3 text-right font-semibold">
                  {formatUsd(detail.total_cost_usd)}
                </td>
                <td />
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </div>
  );
}

function AllowanceLine({ allowance }: { allowance: LiveAllowance }) {
  return (
    <p className="tabular m-0 text-ink-secondary">
      Allowance left: {formatUsd(allowance.remaining_usd)} (today{' '}
      {formatUsd(allowance.spent_today_usd)} of {formatUsd(allowance.daily_cap_usd)}, this month{' '}
      {formatUsd(allowance.spent_month_usd)} of {formatUsd(allowance.monthly_cap_usd)}). More
      becomes available {formatResetTime(allowance.resets_at)}.
    </p>
  );
}
