import { useMe } from '../../api/hooks';
import { Markdown } from '../../components/Markdown';
import { PrimerLink } from '../../components/PrimerLink';
import { useLexicon } from '../../theme/useTheme';

/**
 * "Python you'll need": the exercise's `python.md`, for a learner who said they are new to
 * Python. The API sends the notes only when the learner is entitled to the exercise; an exercise
 * without them shows nothing. Grading, the tests and the brief never depend on this.
 */
export function PythonNotes({ notes }: { notes: string }) {
  const lexicon = useLexicon();
  const me = useMe();
  if (me.data?.profile.new_to_python !== true || notes.trim() === '') return null;
  return (
    <section
      aria-labelledby="python-notes-heading"
      className="space-y-3 text-sm [&_h3]:mb-1 [&_h3]:mt-4 [&_h3]:font-ui [&_h3]:text-sm [&_h3]:font-semibold [&_p]:mb-2 [&_pre]:mb-3 [&_pre]:p-3 [&_pre]:text-xs"
    >
      <h2
        id="python-notes-heading"
        className="m-0 font-ui text-base font-semibold first-letter:uppercase"
      >
        {lexicon.pythonNotesHeading}
      </h2>
      <Markdown>{notes}</Markdown>
      <p className="m-0 text-ink-secondary">
        {lexicon.primerPrompt} <PrimerLink />
      </p>
    </section>
  );
}
