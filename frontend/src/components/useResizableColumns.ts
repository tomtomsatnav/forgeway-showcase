import { useCallback, useLayoutEffect, useState, type RefObject } from 'react';

const KEY = 'lattice.workspace-columns';

/** Width of a splitter's grid track; the hit area is this wide (24px, WCAG 2.5.8). */
export const SPLITTER_WIDTH = 24;
export const COLUMN_MIN = 240;
export const EDITOR_MIN = 360;
export const KEY_STEP = 16;

interface Stored {
  brief?: number;
  results?: number;
}

const isWidth = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value) && value > 0;

/** Storage can be blocked or hold junk, so every access is guarded. */
function read(): Stored {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw === null) return {};
    const parsed = JSON.parse(raw) as Stored | null;
    return {
      brief: isWidth(parsed?.brief) ? parsed.brief : undefined,
      results: isWidth(parsed?.results) ? parsed.results : undefined,
    };
  } catch {
    return {};
  }
}

function write(sizes: Stored): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(sizes));
  } catch {
    /* storage unavailable: the sizes last for this page view only */
  }
}

const clamp = (value: number, min: number, max: number) =>
  Math.round(Math.min(Math.max(value, min), Math.max(min, max)));

export type Column = 'brief' | 'results';

/**
 * Pixel widths for the brief and results columns of a three-column layout, with the editor taking
 * the rest. Widths are clamped to the container, so a saved size never squeezes a pane below its
 * minimum after the window shrinks. Unset columns default to a share of the container.
 */
export function useResizableColumns(container: RefObject<HTMLElement>) {
  const [stored, setStored] = useState(read);
  const [width, setWidth] = useState(() => window.innerWidth);

  useLayoutEffect(() => {
    const measure = () => {
      const measured = container.current?.clientWidth ?? 0;
      setWidth(measured > 0 ? measured : window.innerWidth);
    };
    measure();
    window.addEventListener('resize', measure);
    return () => {
      window.removeEventListener('resize', measure);
    };
  }, [container]);

  const room = width - EDITOR_MIN - 2 * SPLITTER_WIDTH;
  const results = clamp(stored.results ?? width * 0.28, COLUMN_MIN, room - COLUMN_MIN);
  const brief = clamp(stored.brief ?? width * 0.31, COLUMN_MIN, room - results);
  const limits = {
    brief: { min: COLUMN_MIN, max: Math.max(COLUMN_MIN, room - results) },
    results: { min: COLUMN_MIN, max: Math.max(COLUMN_MIN, room - brief) },
  };

  const resize = useCallback(
    (column: Column, value: number) => {
      const next = { brief, results, [column]: value };
      setStored(next);
      write(next);
    },
    [brief, results],
  );

  return { sizes: { brief, results }, limits, resize };
}
