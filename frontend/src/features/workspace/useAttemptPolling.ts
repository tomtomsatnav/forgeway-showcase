import { useEffect, useState } from 'react';

import { ApiError } from '../../api/errors';
import { fetchAttempt } from '../../api/hooks';
import { isTerminal, type AttemptDetail } from '../../api/types';

export const POLL_INITIAL_MS = 400;
export const POLL_FACTOR = 1.5;
export const POLL_MAX_MS = 2000;
export const POLL_TIMEOUT_MS = 60_000;

/** Delay before the nth poll (0-based): 400ms, then growing by 1.5x up to 2s. */
export function pollDelay(n: number): number {
  return Math.min(POLL_INITIAL_MS * POLL_FACTOR ** n, POLL_MAX_MS);
}

export type PollingState =
  | { phase: 'idle'; attempt: null }
  | { phase: 'polling'; attempt: AttemptDetail | null }
  | { phase: 'done'; attempt: AttemptDetail }
  | { phase: 'timeout'; attempt: AttemptDetail | null }
  | { phase: 'failed'; attempt: AttemptDetail | null; message: string };

const IDLE: PollingState = { phase: 'idle', attempt: null };
const STARTED: PollingState = { phase: 'polling', attempt: null };

/** Client errors other than rate limiting will not fix themselves, so polling stops. */
function isFatal(error: unknown): error is ApiError {
  return (
    error instanceof ApiError && error.status >= 400 && error.status < 500 && error.status !== 429
  );
}

/**
 * Poll an attempt until it reaches a terminal status, backing off between requests and giving
 * up after a minute. Transient failures are retried within that budget.
 */
export function useAttemptPolling(
  attemptId: string | null,
  fetcher: (id: string) => Promise<AttemptDetail> = fetchAttempt,
): PollingState {
  // The state is tagged with the attempt it belongs to, so a new attempt starts from a clean slate.
  const [result, setResult] = useState<{ id: string; state: PollingState } | null>(null);

  useEffect(() => {
    if (attemptId === null) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let latest: AttemptDetail | null = null;
    let polls = 0;
    const startedAt = Date.now();
    const publish = (state: PollingState) => {
      if (!cancelled) setResult({ id: attemptId, state });
    };

    const schedule = () => {
      if (Date.now() - startedAt >= POLL_TIMEOUT_MS) {
        publish({ phase: 'timeout', attempt: latest });
        return;
      }
      timer = setTimeout(() => void poll(), pollDelay(polls));
      polls += 1;
    };

    const poll = async () => {
      try {
        const attempt = await fetcher(attemptId);
        latest = attempt;
        if (isTerminal(attempt.status)) {
          publish({ phase: 'done', attempt });
          return;
        }
        publish({ phase: 'polling', attempt });
      } catch (error) {
        if (isFatal(error)) {
          publish({ phase: 'failed', attempt: latest, message: error.message });
          return;
        }
      }
      if (!cancelled) schedule();
    };

    schedule();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [attemptId, fetcher]);

  if (attemptId === null) return IDLE;
  return result?.id === attemptId ? result.state : STARTED;
}
