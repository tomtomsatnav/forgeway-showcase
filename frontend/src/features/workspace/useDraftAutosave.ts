import { useCallback, useEffect, useRef, useState } from 'react';

import { saveDraft } from '../../api/hooks';

export const AUTOSAVE_DELAY_MS = 1000;

export type SaveState = 'idle' | 'saving' | 'saved' | 'error';
type Files = Record<string, string>;

function sameFiles(a: Files, b: Files): boolean {
  const keys = Object.keys(a);
  return keys.length === Object.keys(b).length && keys.every((key) => a[key] === b[key]);
}

/**
 * Save the learner's files about a second after they stop typing. `baseline` is what the server
 * already holds, so nothing is sent until the files differ from it. Pending changes are flushed
 * when the page is left.
 */
export function useDraftAutosave(
  exerciseId: string,
  files: Files,
  baseline: Files,
  save: (exerciseId: string, files: Files) => Promise<void> = saveDraft,
): { state: SaveState; markSaved: (files: Files) => void } {
  const [state, setState] = useState<SaveState>('idle');
  const saved = useRef(baseline);
  const latest = useRef(files);

  useEffect(() => {
    latest.current = files;
    if (sameFiles(files, saved.current)) return;
    const timer = setTimeout(() => {
      setState('saving');
      save(exerciseId, files).then(
        () => {
          saved.current = files;
          setState('saved');
        },
        () => {
          setState('error');
        },
      );
    }, AUTOSAVE_DELAY_MS);
    return () => {
      clearTimeout(timer);
    };
  }, [exerciseId, files, save]);

  useEffect(
    () => () => {
      if (!sameFiles(latest.current, saved.current)) {
        save(exerciseId, latest.current).catch(() => undefined);
      }
    },
    [exerciseId, save],
  );

  /** Submitting an attempt saves the files server-side, so the draft is already current. */
  const markSaved = useCallback((submitted: Files) => {
    saved.current = submitted;
  }, []);

  return { state, markSaved };
}
