import { motion } from 'motion/react';
import { LoaderCircle, TriangleAlert } from 'lucide-react';

import type { CheckInfo, Progression } from '../../api/types';
import { CheckResult } from '../../components/CheckResult';
import { ProgressionNews } from '../../theme/slots/ProgressionNews';
import { useLexicon } from '../../theme/useTheme';
import type { PollingState } from './useAttemptPolling';

const list = {
  hidden: {},
  show: { transition: { staggerChildren: 0.04 } },
};
const item = {
  hidden: { opacity: 0, y: 6 },
  show: { opacity: 1, y: 0, transition: { duration: 0.2, ease: [0.2, 0.7, 0.2, 1] as const } },
};

interface ResultsPanelProps {
  checks: readonly CheckInfo[];
  polling: PollingState;
  submitting: boolean;
  /**
   * Badge, talent point and streak news to show with the results. The page leaves it out while a
   * completion moment is already telling the learner the same thing.
   */
  news?: Progression | null;
}

/** What the grader said, or what it will check. Announced separately through the live region. */
export function ResultsPanel({ checks, polling, submitting, news }: ResultsPanelProps) {
  const lexicon = useLexicon();
  const { attempt } = polling;

  if (polling.phase === 'idle' && !submitting) {
    return (
      <div className="space-y-3">
        <p className="m-0 text-sm text-ink-secondary">
          {lexicon.attemptSubmit} to see how each check judges your code. The grader will look for:
        </p>
        <ul className="m-0 list-disc space-y-1 pl-5 text-sm text-ink-secondary">
          {checks.map((check) => (
            <li key={check.id}>{check.title}</li>
          ))}
        </ul>
      </div>
    );
  }

  if (submitting || polling.phase === 'polling') {
    return (
      <p className="m-0 flex items-center gap-2 text-ink-secondary">
        <LoaderCircle aria-hidden="true" className="h-4 w-4 animate-spin" />
        {attempt?.status === 'running' ? `${lexicon.attemptRunning}…` : 'Waiting for the grader…'}
      </p>
    );
  }

  if (polling.phase === 'timeout') {
    return (
      <Notice>
        Grading is taking longer than expected, so we stopped waiting. Your attempt is saved and may
        still finish; run the checks again in a moment.
      </Notice>
    );
  }

  if (polling.phase === 'failed') {
    return <Notice>{polling.message}</Notice>;
  }

  if (polling.phase !== 'done') return null;
  const { checks: results, status, error } = polling.attempt;
  const passedCount = results.filter((check) => check.passed).length;

  return (
    <div className="space-y-4">
      {status === 'errored' ? (
        <div
          role="group"
          aria-label="Grading error"
          className="space-y-2 rounded-control border border-warning bg-warning-soft p-3"
        >
          <p className="m-0 flex items-center gap-2 font-semibold text-warning">
            <TriangleAlert aria-hidden="true" className="h-4 w-4" />
            The grader hit a problem
          </p>
          {error !== null && (
            <p className="m-0 whitespace-pre-wrap rounded-control bg-sunken px-3 py-2 font-mono text-sm text-ink">
              {error}
            </p>
          )}
          <p className="m-0 text-sm text-ink">
            This is not your fault and it does not count against you. Try again.
          </p>
        </div>
      ) : (
        <p className="tabular m-0 font-semibold">
          {status === 'passed' ? 'Passed' : 'Not yet'}: {passedCount} of {results.length} checks
          passed
        </p>
      )}
      {news != null && <ProgressionNews progression={news} />}
      <motion.ul
        variants={list}
        initial="hidden"
        animate="show"
        className="m-0 list-none space-y-4 p-0"
      >
        {results.map((check) => (
          <motion.li key={check.id} variants={item} className="border-t border-line-subtle pt-4">
            <CheckResult check={check} />
          </motion.li>
        ))}
      </motion.ul>
    </div>
  );
}

function Notice({ children }: { children: string }) {
  return (
    <p className="m-0 rounded-control border border-warning bg-warning-soft px-3 py-2 text-sm text-ink">
      {children}
    </p>
  );
}
