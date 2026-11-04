import { ChevronRight, Lock } from 'lucide-react';

import { errorMessage, ApiError } from '../../api/errors';
import { useReferenceSolution } from '../../api/hooks';
import { Markdown } from '../../components/Markdown';
import { usePathName } from '../../theme/usePathName';
import { useLexicon } from '../../theme/useTheme';

/**
 * The reference solution for an exercise the learner has passed. It is not requested before the
 * pass. A 403 means a talent is still needed. The hint is always worded by the mode's lexicon,
 * naming the talents (and their specialisation) from the problem, never the server's detail.
 */
export function ReferenceSolution({ exerciseId, passed }: { exerciseId: string; passed: boolean }) {
  const lexicon = useLexicon();
  const pathName = usePathName();
  const solution = useReferenceSolution(exerciseId, passed);

  if (!passed || solution.isPending) return null;

  if (solution.isError) {
    if (solution.error instanceof ApiError && solution.error.status === 403) {
      return (
        <p className="m-0 flex items-start gap-2 text-sm text-ink-secondary">
          <Lock aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            <span className="font-semibold text-ink">{lexicon.referenceSolution}.</span>{' '}
            {lexicon.referenceLocked(
              solution.error.talents.map((t) => ({
                title: t.title,
                pathName: t.path === null ? null : pathName(t.path),
              })),
            )}
          </span>
        </p>
      );
    }
    return (
      <p role="alert" className="m-0 text-sm text-danger">
        {errorMessage(solution.error)}
      </p>
    );
  }

  const { files, notes } = solution.data;
  return (
    <details className="group space-y-3 rounded-control border border-line-strong p-3">
      <summary className="flex min-h-8 cursor-pointer list-none items-center gap-2 font-semibold">
        <ChevronRight
          aria-hidden="true"
          className="h-4 w-4 transition-transform duration-fast group-open:rotate-90"
        />
        {lexicon.referenceSolution}
      </summary>
      <div className="space-y-4 pt-2">
        {Object.entries(files).map(([path, code]) => (
          <section key={path} aria-label={path} className="space-y-1">
            <h3 className="m-0 font-mono text-sm font-semibold">{path}</h3>
            <pre
              tabIndex={0}
              className="m-0 overflow-x-auto rounded-control bg-sunken p-3 font-mono text-sm leading-6 text-ink"
            >
              {code}
            </pre>
          </section>
        ))}
        {notes.trim() !== '' && (
          <section aria-label={lexicon.referenceNotes} className="text-sm">
            <h3 className="mb-2 mt-0 text-base">{lexicon.referenceNotes}</h3>
            <Markdown>{notes}</Markdown>
          </section>
        )}
      </div>
    </details>
  );
}
