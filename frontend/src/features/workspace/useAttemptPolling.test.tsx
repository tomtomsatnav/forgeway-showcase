import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../api/errors';
import type { AttemptDetail } from '../../api/types';
import { POLL_TIMEOUT_MS, pollDelay, useAttemptPolling } from './useAttemptPolling';

const attempt = (status: AttemptDetail['status']): AttemptDetail => ({
  id: 'a1',
  exercise_id: 'x',
  status,
  created_at: '2026-01-01T00:00:00Z',
  finished_at: null,
  checks: [],
  error: null,
  duration_ms: null,
  progression: null,
});

/** Advance the fake clock inside act() so state updates from timers are flushed. */
async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe('pollDelay', () => {
  it('starts at 400ms, grows by 1.5x and is capped at 2s', () => {
    expect([0, 1, 2, 3, 4, 5, 9].map(pollDelay)).toEqual([400, 600, 900, 1350, 2000, 2000, 2000]);
  });
});

describe('useAttemptPolling', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('backs off between polls and stops once the attempt is terminal', async () => {
    const fetcher = vi
      .fn<(id: string) => Promise<AttemptDetail>>()
      .mockResolvedValueOnce(attempt('queued'))
      .mockResolvedValueOnce(attempt('running'))
      .mockResolvedValue(attempt('passed'));
    const { result } = renderHook(() => useAttemptPolling('a1', fetcher));

    expect(fetcher).not.toHaveBeenCalled();
    await advance(399);
    expect(fetcher).not.toHaveBeenCalled();
    await advance(1);
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(result.current.phase).toBe('polling');

    await advance(599);
    expect(fetcher).toHaveBeenCalledTimes(1);
    await advance(1);
    expect(fetcher).toHaveBeenCalledTimes(2);

    await advance(900);
    expect(fetcher).toHaveBeenCalledTimes(3);
    expect(result.current).toMatchObject({ phase: 'done', attempt: { status: 'passed' } });

    await advance(30_000);
    expect(fetcher).toHaveBeenCalledTimes(3);
  });

  it.each(['failed', 'errored'] as const)('treats %s as terminal', async (status) => {
    const fetcher = vi.fn().mockResolvedValue(attempt(status));
    const { result } = renderHook(() => useAttemptPolling('a1', fetcher));

    await advance(400);
    expect(result.current.phase).toBe('done');
    await advance(10_000);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('gives up after a minute and says so', async () => {
    const fetcher = vi.fn().mockResolvedValue(attempt('queued'));
    const { result } = renderHook(() => useAttemptPolling('a1', fetcher));

    await advance(POLL_TIMEOUT_MS + 2000);
    expect(result.current.phase).toBe('timeout');
    const calls = fetcher.mock.calls.length;
    await advance(10_000);
    expect(fetcher).toHaveBeenCalledTimes(calls);
  });

  it('keeps going through a transient failure but stops on a client error', async () => {
    const flaky = vi
      .fn<(id: string) => Promise<AttemptDetail>>()
      .mockRejectedValueOnce(new TypeError('network'))
      .mockResolvedValue(attempt('passed'));
    const first = renderHook(() => useAttemptPolling('a1', flaky));
    await advance(400 + 600);
    expect(first.result.current.phase).toBe('done');

    const gone = vi.fn().mockRejectedValue(new ApiError(404, 'not-found', 'No such attempt.'));
    const second = renderHook(() => useAttemptPolling('a2', gone));
    await advance(400);
    expect(second.result.current).toMatchObject({ phase: 'failed', message: 'No such attempt.' });
    await advance(5000);
    expect(gone).toHaveBeenCalledTimes(1);
  });

  it('stays idle without an attempt', () => {
    const fetcher = vi.fn();
    const { result } = renderHook(() => useAttemptPolling(null, fetcher));

    expect(result.current.phase).toBe('idle');
  });
});
