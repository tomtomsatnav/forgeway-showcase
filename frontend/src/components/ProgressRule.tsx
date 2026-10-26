interface ProgressRuleProps {
  value: number;
  max: number;
  /** Accessible name, e.g. "Experience towards level 2". */
  label: string;
  /** Visible text beside the rule; tabular figures. */
  caption?: string;
}

/** A thin bar with tabular numbers for XP and branch completion. */
export function ProgressRule({ value, max, label, caption }: ProgressRuleProps) {
  const fraction = max > 0 ? Math.min(Math.max(value / max, 0), 1) : 0;
  return (
    <div className="flex items-center gap-3">
      <div
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={value}
        className="h-1 min-w-16 flex-1 overflow-hidden rounded-full bg-line-subtle"
      >
        <div
          className="h-full bg-accent transition-[width] duration-base"
          style={{ width: `${(fraction * 100).toFixed(1)}%` }}
        />
      </div>
      {caption !== undefined && (
        <span className="tabular whitespace-nowrap text-sm text-ink-secondary">{caption}</span>
      )}
    </div>
  );
}
