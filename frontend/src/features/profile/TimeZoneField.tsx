import { useState, type FormEvent } from 'react';

import { errorMessage } from '../../api/errors';
import { useUpdatePathProfile } from '../../api/hooks';
import { Button } from '../../components/Button';
import { useLexicon } from '../../theme/useTheme';

/** Every IANA zone this browser knows, with the learner's own and UTC always present. */
export function supportedZones(current: string): string[] {
  const known =
    typeof Intl.supportedValuesOf === 'function' ? Intl.supportedValuesOf('timeZone') : [];
  return [...new Set([current, 'UTC', ...known])].sort((a, b) => a.localeCompare(b));
}

const FIELD =
  'block min-h-11 w-full max-w-sm rounded-control border border-line-strong bg-sunken px-3 text-base text-ink';

/**
 * A searchable list of time zones: typing filters the browser's own suggestions, and only a name
 * from the list can be saved. The streak counts days in this zone.
 */
export function TimeZoneField({ current }: { current: string }) {
  const lexicon = useLexicon();
  const update = useUpdatePathProfile();
  const [value, setValue] = useState(current);
  const [zones] = useState(() => supportedZones(current));

  const valid = zones.includes(value);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (valid && value !== current) update.mutate({ time_zone: value });
  };

  return (
    <form onSubmit={submit} className="space-y-3">
      <div className="space-y-1">
        <label htmlFor="time-zone" className="block text-sm font-medium">
          {lexicon.timeZone}
        </label>
        <input
          id="time-zone"
          list="time-zone-options"
          className={FIELD}
          autoComplete="off"
          spellCheck={false}
          aria-describedby="time-zone-hint"
          aria-invalid={!valid || undefined}
          value={value}
          onChange={(event) => {
            setValue(event.target.value);
          }}
        />
        <datalist id="time-zone-options">
          {zones.map((zone) => (
            <option key={zone} value={zone} />
          ))}
        </datalist>
        <p id="time-zone-hint" className="m-0 text-sm text-ink-muted">
          {valid
            ? lexicon.timeZoneHint
            : 'Choose a time zone from the list, such as Europe/London.'}
        </p>
      </div>
      <Button
        type="submit"
        variant="secondary"
        disabled={!valid || value === current}
        loading={update.isPending}
      >
        {lexicon.timeZoneSave}
      </Button>
      {update.isError && (
        <p
          role="alert"
          className="m-0 rounded-control bg-danger-soft px-3 py-2 text-sm text-danger"
        >
          {errorMessage(update.error)}
        </p>
      )}
    </form>
  );
}
