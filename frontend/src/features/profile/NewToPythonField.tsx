import { errorMessage } from '../../api/errors';
import { useMe, useUpdateProfile } from '../../api/hooks';
import { PrimerLink } from '../../components/PrimerLink';
import { useLexicon } from '../../theme/useTheme';

/** "I'm new to Python": adds the "Python you'll need" notes to exercises. Saves at once. */
export function NewToPythonField() {
  const lexicon = useLexicon();
  const me = useMe();
  const update = useUpdateProfile();
  if (!me.data) return null;
  const on = update.isPending ? update.variables.new_to_python : me.data.profile.new_to_python;

  return (
    <div className="space-y-1">
      <div className="flex items-start gap-3">
        <input
          id="new-to-python"
          type="checkbox"
          className="mt-1 h-5 w-5 shrink-0 accent-[var(--accent)]"
          checked={on}
          disabled={update.isPending}
          aria-describedby="new-to-python-hint"
          onChange={(event) => {
            update.mutate({ new_to_python: event.target.checked });
          }}
        />
        <label htmlFor="new-to-python" className="text-sm font-medium">
          {lexicon.newToPythonLabel}
        </label>
      </div>
      <p id="new-to-python-hint" className="m-0 max-w-measure text-sm text-ink-muted">
        {lexicon.newToPythonHint} {lexicon.primerPrompt} <PrimerLink />
      </p>
      {update.isError && (
        <p role="alert" className="m-0 text-sm text-danger">
          {errorMessage(update.error)}
        </p>
      )}
    </div>
  );
}
