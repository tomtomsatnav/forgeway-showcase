import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AUTOSAVE_DELAY_MS, useDraftAutosave } from './useDraftAutosave';

describe('useDraftAutosave', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('saves once, a second after the last keystroke, and reports it', async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    const baseline = { 'a.py': 'start' };
    const { result, rerender } = renderHook(
      ({ files }) => useDraftAutosave('x', files, baseline, save),
      { initialProps: { files: baseline } },
    );

    await vi.advanceTimersByTimeAsync(AUTOSAVE_DELAY_MS * 2);
    expect(save).not.toHaveBeenCalled();

    rerender({ files: { 'a.py': 'start1' } });
    await vi.advanceTimersByTimeAsync(AUTOSAVE_DELAY_MS - 100);
    rerender({ files: { 'a.py': 'start12' } });
    await vi.advanceTimersByTimeAsync(AUTOSAVE_DELAY_MS - 100);
    expect(save).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(100);
    expect(save).toHaveBeenCalledExactlyOnceWith('x', { 'a.py': 'start12' });
    expect(result.current.state).toBe('saved');
  });

  it('reports a failed save', async () => {
    const save = vi.fn().mockRejectedValue(new Error('offline'));
    const { result } = renderHook(() =>
      useDraftAutosave('x', { 'a.py': 'new' }, { 'a.py': 'old' }, save),
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(AUTOSAVE_DELAY_MS);
    });
    expect(result.current.state).toBe('error');
  });
});
