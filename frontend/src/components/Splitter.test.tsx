import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useRef } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { Splitter } from './Splitter';
import { COLUMN_MIN, KEY_STEP, useResizableColumns } from './useResizableColumns';

function Harness() {
  const ref = useRef<HTMLDivElement>(null);
  const columns = useResizableColumns(ref);
  return (
    <div ref={ref}>
      <p data-testid="sizes">{`${columns.sizes.brief}/${columns.sizes.results}`}</p>
      <Splitter
        label="Resize brief"
        controls="brief"
        value={columns.sizes.brief}
        {...columns.limits.brief}
        step={KEY_STEP}
        onChange={(value) => {
          columns.resize('brief', value);
        }}
      />
      <Splitter
        label="Resize results"
        controls="results"
        value={columns.sizes.results}
        {...columns.limits.results}
        step={KEY_STEP}
        invert
        onChange={(value) => {
          columns.resize('results', value);
        }}
      />
    </div>
  );
}

const brief = () => screen.getByRole('separator', { name: 'Resize brief', hidden: true });
const results = () => screen.getByRole('separator', { name: 'Resize results', hidden: true });
const now = (element: HTMLElement) => Number(element.getAttribute('aria-valuenow'));

describe('Splitter', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal('innerWidth', 1600);
  });
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('exposes the window splitter semantics', () => {
    render(<Harness />);
    expect(brief()).toHaveAttribute('aria-orientation', 'vertical');
    expect(brief()).toHaveAttribute('aria-controls', 'brief');
    expect(brief()).toHaveAttribute('tabindex', '0');
    expect(brief()).toHaveAttribute('aria-valuemin', String(COLUMN_MIN));
    expect(Number(brief().getAttribute('aria-valuemax'))).toBeGreaterThan(COLUMN_MIN);
  });

  it('moves by a step with the arrow keys, and inverts for the right-hand pane', async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const start = now(brief());
    brief().focus();
    await user.keyboard('{ArrowRight}');
    expect(now(brief())).toBe(start + KEY_STEP);
    await user.keyboard('{ArrowLeft}{ArrowLeft}');
    expect(now(brief())).toBe(start - KEY_STEP);

    const resultsStart = now(results());
    results().focus();
    await user.keyboard('{ArrowRight}');
    expect(now(results())).toBe(resultsStart - KEY_STEP);
  });

  it('jumps to the limits with Home and End and never passes them', async () => {
    const user = userEvent.setup();
    render(<Harness />);
    brief().focus();
    await user.keyboard('{Home}');
    expect(now(brief())).toBe(COLUMN_MIN);
    await user.keyboard('{ArrowLeft}');
    expect(now(brief())).toBe(COLUMN_MIN);
    await user.keyboard('{End}');
    const max = Number(brief().getAttribute('aria-valuemax'));
    expect(now(brief())).toBe(max);
    await user.keyboard('{ArrowRight}');
    expect(now(brief())).toBe(max);
  });

  it('keeps the other column and the editor usable when one grows to its limit', async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const resultsStart = now(results());
    brief().focus();
    await user.keyboard('{End}');
    expect(now(results())).toBe(resultsStart);
    expect(Number(results().getAttribute('aria-valuemax'))).toBeGreaterThanOrEqual(COLUMN_MIN);
  });

  it('drags with pointer capture', () => {
    const capture = vi.fn();
    const release = vi.fn();
    Object.assign(HTMLElement.prototype, {
      setPointerCapture: capture,
      releasePointerCapture: release,
      hasPointerCapture: () => true,
    });
    render(<Harness />);
    const start = now(brief());
    fireEvent.pointerDown(brief(), { pointerId: 1, clientX: 400 });
    fireEvent.pointerMove(brief(), { pointerId: 1, clientX: 450 });
    expect(capture).toHaveBeenCalledWith(1);
    expect(now(brief())).toBe(start + 50);
    fireEvent.pointerUp(brief(), { pointerId: 1, clientX: 450 });
    fireEvent.pointerMove(brief(), { pointerId: 1, clientX: 600 });
    expect(release).toHaveBeenCalledWith(1);
    expect(now(brief())).toBe(start + 50);
  });

  it('persists sizes and restores them, clamped, on the next visit', async () => {
    const user = userEvent.setup();
    const first = render(<Harness />);
    brief().focus();
    await user.keyboard('{ArrowRight}');
    const saved = now(brief());
    expect(JSON.parse(localStorage.getItem('lattice.workspace-columns') ?? '{}')).toMatchObject({
      brief: saved,
    });
    first.unmount();

    render(<Harness />);
    expect(now(brief())).toBe(saved);
  });

  it('clamps nonsense in storage', () => {
    localStorage.setItem('lattice.workspace-columns', JSON.stringify({ brief: 99999, results: 5 }));
    render(<Harness />);
    expect(now(results())).toBe(COLUMN_MIN);
    expect(now(brief())).toBe(Number(brief().getAttribute('aria-valuemax')));
  });

  it('ignores unparsable storage and still resizes when storage throws', async () => {
    localStorage.setItem('lattice.workspace-columns', '{nope');
    const user = userEvent.setup();
    const { unmount } = render(<Harness />);
    expect(now(brief())).toBeGreaterThanOrEqual(COLUMN_MIN);
    unmount();

    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    render(<Harness />);
    const start = now(brief());
    brief().focus();
    await user.keyboard('{ArrowRight}');
    expect(now(brief())).toBe(start + KEY_STEP);
  });

  it('draws a grip and a hairline from the strong border token, with a hover state', () => {
    render(<Harness />);

    const grip = brief().querySelector('[data-grip]');
    expect(grip).toHaveClass('border-line-strong', 'group-hover:border-accent-strong');
    expect(brief().querySelector('span')).toHaveClass(
      'bg-line-strong',
      'group-hover:bg-accent-strong',
    );
  });
});
