import { useRef, type KeyboardEvent, type PointerEvent } from 'react';

export interface SplitterProps {
  /** Accessible name, for example "Resize brief". */
  label: string;
  /** The id of the pane whose size this splitter controls. */
  controls: string;
  /** Current size of the controlled pane, in pixels. */
  value: number;
  min: number;
  max: number;
  /** Pixels moved by an arrow key. */
  step: number;
  /** True when the controlled pane sits to the right of the splitter, so moving right shrinks it. */
  invert?: boolean;
  onChange: (value: number) => void;
}

/**
 * A vertical window splitter (WAI-ARIA): drag it, or focus it and use Left/Right, Home and End.
 * The visible rule is a hairline; the element itself fills its 24px grid track so the hit area
 * meets the target size (WCAG 2.5.8). It only exists in the three-column layout.
 */
export function Splitter({
  label,
  controls,
  value,
  min,
  max,
  step,
  invert,
  onChange,
}: SplitterProps) {
  const drag = useRef<{ x: number; value: number } | null>(null);
  const sign = invert ? -1 : 1;
  const clamp = (next: number) => Math.min(max, Math.max(min, Math.round(next)));

  const onKeyDown = (event: KeyboardEvent) => {
    const next = {
      ArrowLeft: value - sign * step,
      ArrowRight: value + sign * step,
      Home: min,
      End: max,
    }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    onChange(clamp(next));
  };

  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    drag.current = { x: event.clientX, value };
  };

  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (drag.current === null) return;
    onChange(clamp(drag.current.value + sign * (event.clientX - drag.current.x)));
  };

  const endDrag = (event: PointerEvent<HTMLDivElement>) => {
    drag.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      aria-controls={controls}
      aria-valuenow={value}
      aria-valuemin={min}
      aria-valuemax={max}
      tabIndex={0}
      onKeyDown={onKeyDown}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={endDrag}
      onPointerCancel={endDrag}
      className="group relative hidden w-6 cursor-col-resize touch-none items-center justify-center xl:flex"
    >
      <span
        aria-hidden="true"
        className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-line-strong group-hover:w-0.5 group-hover:bg-accent-strong group-active:w-0.5 group-active:bg-accent-strong"
      />
      <span
        aria-hidden="true"
        data-grip=""
        className="relative flex h-10 w-3 flex-col items-center justify-center gap-1 rounded-full border border-line-strong bg-raised group-hover:border-accent-strong group-active:border-accent-strong"
      >
        <span className="h-0.5 w-0.5 rounded-full bg-line-strong group-hover:bg-accent-strong" />
        <span className="h-0.5 w-0.5 rounded-full bg-line-strong group-hover:bg-accent-strong" />
        <span className="h-0.5 w-0.5 rounded-full bg-line-strong group-hover:bg-accent-strong" />
      </span>
    </div>
  );
}
