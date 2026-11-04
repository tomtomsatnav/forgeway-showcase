import { Link } from '@tanstack/react-router';
import { useEffect } from 'react';

import { errorMessage } from '../../api/errors';
import { useMarkReleasesSeen, useReleases } from '../../api/hooks';
import type { Release, ReleaseExercise } from '../../api/types';
import { Markdown } from '../../components/Markdown';
import { useFlavour } from '../../theme/flavour';
import { PageHeader } from '../../theme/slots';
import { useLexicon } from '../../theme/useTheme';

/** A release date (an ISO day) in UK long form, whatever the viewer's zone. */
export function formatReleaseDate(day: string): string {
  return new Date(`${day}T00:00:00Z`).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

/**
 * "What's new" (the Chronicle in RPG mode): every content release, newest first, each linking
 * to the exercises it names. Opening it marks the newest release as seen.
 */
export function WhatsNewPage() {
  const lexicon = useLexicon();
  const releases = useReleases();
  const markSeen = useMarkReleasesSeen();
  const unread = releases.data?.unread === true;
  const { mutate, isPending, isError } = markSeen;

  useEffect(() => {
    if (unread && !isPending && !isError) mutate();
  }, [unread, isPending, isError, mutate]);

  return (
    <div className="mx-auto max-w-page space-y-8 px-4 py-8 sm:px-6">
      <PageHeader title={lexicon.whatsNew} summary={lexicon.whatsNewSummary} />
      {releases.isPending && (
        <p role="status" className="m-0 text-ink-muted">
          Loading…
        </p>
      )}
      {releases.isError && (
        <p role="alert" className="m-0 text-danger">
          {errorMessage(releases.error)}
        </p>
      )}
      {releases.data?.releases.length === 0 && (
        <p className="m-0 text-ink-secondary">{lexicon.whatsNewNone}</p>
      )}
      {releases.data && releases.data.releases.length > 0 && (
        <ol className="m-0 list-none space-y-12 p-0">
          {releases.data.releases.map((release) => (
            <li key={release.version}>
              <ReleaseEntry release={release} />
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function ReleaseEntry({ release }: { release: Release }) {
  const lexicon = useLexicon();
  const headingId = `release-${release.version.replace(/\./g, '-')}`;
  return (
    <article aria-labelledby={headingId} className="max-w-measure space-y-4">
      <header className="space-y-1 border-b border-line-subtle pb-3">
        <p className="label-caps m-0 text-ink-muted">
          <span className="tabular">{release.version}</span> ·{' '}
          <time dateTime={release.date}>
            {lexicon.releaseDate(formatReleaseDate(release.date))}
          </time>
        </p>
        <h2 id={headingId} className="m-0 text-2xl">
          {release.title}
        </h2>
        <p className="m-0 text-ink-secondary">{release.summary}</p>
      </header>
      {/* The body's own headings sit a step above its serif text, and below the release title. */}
      <div className="font-reading text-lg [&_h3]:text-xl">
        <Markdown>{nested(release.body)}</Markdown>
      </div>
      <ExerciseList title={lexicon.releaseAdded} items={release.added} />
      <ExerciseList title={lexicon.releaseUpdated} items={release.updated} />
      <ExerciseList title={lexicon.releaseFixed} items={release.fixed} />
    </article>
  );
}

/** Push the body's headings one level down, beneath the release's own h2. */
function nested(markdown: string): string {
  return markdown.replace(/^(#{1,5}) /gm, '#$1 ');
}

function ExerciseList({ title, items }: { title: string; items: readonly ReleaseExercise[] }) {
  const flavour = useFlavour();
  if (items.length === 0) return null;
  return (
    <section className="space-y-2">
      <h3 className="label-caps m-0 text-ink-muted">{title}</h3>
      <ul className="m-0 list-disc space-y-1 pl-5">
        {items.map((item) => {
          const quest = flavour.boss(item.id)?.name ?? flavour.quest(item.id);
          return (
            <li key={item.id}>
              <Link
                to="/exercises/$exerciseId"
                params={{ exerciseId: item.id }}
                className="text-accent-strong underline underline-offset-2"
              >
                {quest ?? item.title}
              </Link>
              {quest !== undefined && <span className="text-ink-secondary"> ({item.title})</span>}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
