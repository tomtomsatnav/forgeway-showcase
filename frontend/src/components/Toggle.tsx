import type { LucideIcon } from 'lucide-react';

interface Option<T extends string> {
  value: T;
  label: string;
  /** When given, the icon is shown and the label is kept for assistive technology only. */
  icon?: LucideIcon;
  /** Refuse this choice; `describedBy` names the element that says why. */
  disabled?: boolean;
  describedBy?: string;
}

interface ToggleProps<T extends string> {
  legend: string;
  value: T;
  options: readonly Option<T>[];
  onChange: (value: T) => void;
}

/** A labelled segmented control built from native radio buttons. */
export function Toggle<T extends string>({ legend, value, options, onChange }: ToggleProps<T>) {
  return (
    <fieldset className="m-0 min-w-0 border-0 p-0">
      <legend className="sr-only">{legend}</legend>
      <div className="inline-flex overflow-hidden rounded-control border border-line-strong">
        {options.map((option) => (
          <label
            key={option.value}
            className="relative flex min-h-11 has-[:disabled]:opacity-60 min-w-11 cursor-pointer items-center justify-center px-3 text-sm font-medium transition-colors duration-fast has-[:checked]:bg-accent has-[:checked]:text-on-accent has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-focus [&:not(:has(:checked))]:hover:bg-sunken"
          >
            <input
              type="radio"
              name={legend}
              value={option.value}
              checked={option.value === value}
              disabled={option.disabled}
              aria-describedby={option.describedBy}
              onChange={() => {
                onChange(option.value);
              }}
              className="absolute inset-0 m-0 cursor-pointer opacity-0 disabled:cursor-not-allowed"
            />
            {option.icon ? (
              <>
                <option.icon aria-hidden="true" className="h-4 w-4" />
                <span className="sr-only">{option.label}</span>
              </>
            ) : (
              option.label
            )}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
