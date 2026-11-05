import { Link } from '@tanstack/react-router';

import { errorMessage } from '../../api/errors';
import { useLearnerMap, useMe } from '../../api/hooks';
import type { BranchSummary } from '../../api/types';
import { ProMark } from '../../components/ProMark';
import { StatusMark } from '../../components/StatusMark';
import { TierMark } from '../../components/TierMark';
import { useFlavour } from '../../theme/flavour';
import { PageHeader } from '../../theme/slots';
import { useLexicon } from '../../theme/useTheme';
import { useDocumentHead } from '../landing/LandingPage';
import { useCatalogue } from '../landing/useCatalogue';

/**
 * The exercises tagged `security` in their exercise.yaml, in track order, which respects
 * prerequisites. Read from the API rather than listed here, so no Pro exercise is named in the
 * public source.
 */
export function securityPath(branches: readonly BranchSummary[]) {
  return branches.flatMap((branch) =>
    branch.exercises
      .filter((exercise) => exercise.skills.includes('security'))
      .map((exercise) => ({ exercise, track: branch.id, trackTitle: branch.title })),
  );
}

const SOURCES = [
  {
    title: 'OWASP Top 10 for Agentic Applications 2026',
    href: 'https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/',
  },
  { title: 'OWASP Top 10 for LLM Applications', href: 'https://genai.owasp.org/llm-top-10/' },
  {
    title: 'MCP security best practices',
    href: 'https://modelcontextprotocol.io/specification/2025-11-25/basic/security_best_practices',
  },
] as const;

/** Public: signed-in learners see their progress, visitors the catalogue. */
export function SecurityPathPage() {
  const lexicon = useLexicon();
  const copy = lexicon.securityPath;
  const flavour = useFlavour();
  const signedIn = useMe().data != null;
  const map = useLearnerMap(signedIn);
  const catalogue = useCatalogue(!signedIn);
  const source = signedIn ? map : catalogue;
  useDocumentHead(copy.documentTitle, copy.metaDescription);

  if (source.isPending) {
    return (
      <p role="status" className="mx-auto max-w-page px-4 py-12 text-ink-muted sm:px-6">
        Loading…
      </p>
    );
  }
  if (source.isError) {
    return (
      <p role="alert" className="mx-auto max-w-page px-4 py-12 text-danger sm:px-6">
        {errorMessage(source.error)}
      </p>
    );
  }

  const steps = securityPath(source.data.branches);
  return (
    <div className="mx-auto max-w-page space-y-8 px-4 py-8 sm:px-6">
      <PageHeader title={copy.title} summary={copy.summary(steps.length)} />
      <p className="m-0 max-w-measure font-reading text-lg">{copy.intro}</p>
      <ol className="m-0 list-none p-0">
        {steps.map(({ exercise, track, trackTitle }, position) => (
          <li key={exercise.id} className="border-b border-line-subtle">
            <Link
              to="/exercises/$exerciseId"
              params={{ exerciseId: exercise.id }}
              className="group grid min-h-11 grid-cols-[2rem_minmax(0,1fr)] gap-x-3 gap-y-1 py-3 text-ink no-underline sm:grid-cols-[2.5rem_minmax(0,1fr)_auto_7.5rem] sm:items-center sm:gap-x-4"
            >
              <span className="tabular text-ink-muted">
                {String(position + 1).padStart(2, '0')}
              </span>
              <span className="min-w-0">
                <span className="block font-medium group-hover:underline">
                  {flavour.quest(exercise.id) ?? exercise.title}
                </span>
                <span className="block truncate text-sm text-ink-muted">
                  {flavour.zone(track)?.name ?? trackTitle}
                </span>
              </span>
              <span className="col-start-2 inline-flex flex-wrap items-center gap-2 sm:col-start-auto">
                <TierMark tier={exercise.tier} />
                {exercise.pro && <ProMark />}
              </span>
              <span className="col-start-2 sm:col-start-auto sm:justify-self-end">
                <StatusMark status={exercise.status} />
              </span>
            </Link>
          </li>
        ))}
      </ol>
      <p className="m-0 max-w-measure text-sm text-ink-secondary">{copy.lockedNote}</p>
      <section aria-label={copy.sourcesLabel}>
        <h2 className="m-0 text-lg">{copy.sourcesLabel}</h2>
        <ul className="m-0 mt-2 list-disc space-y-1 pl-5">
          {SOURCES.map((source) => (
            <li key={source.href}>
              <a href={source.href} target="_blank" rel="noreferrer">
                {source.title}
              </a>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
