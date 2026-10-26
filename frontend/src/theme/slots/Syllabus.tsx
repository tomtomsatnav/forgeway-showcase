import { Link } from '@tanstack/react-router';
import { ChevronRight } from 'lucide-react';
import { useState } from 'react';

import type { BranchSummary } from '../../api/types';
import { ProMark } from '../../components/ProMark';
import { ProgressRule } from '../../components/ProgressRule';
import { StatusMark } from '../../components/StatusMark';
import { TierMark } from '../../components/TierMark';
import { useLexicon } from '../useTheme';
import type { BranchOverviewProps } from './types';

function titleOf(branches: readonly BranchSummary[], id: string): string {
  return branches.find((branch) => branch.id === id)?.title ?? id;
}

const complete = (branch: BranchSummary) =>
  branch.exercises.length > 0 && branch.passed_count === branch.exercises.length;

/**
 * The tracks whose exercises are listed when the page opens: the ones in progress or, when none
 * is, the next one to take (the first unlocked one not yet complete, else the first not
 * complete). The rest (finished, locked, not yet started) start folded to their header.
 */
export function openTracks(branches: readonly BranchSummary[]): Set<string> {
  const current = branches.filter((branch) => branch.passed_count > 0 && !complete(branch));
  if (current.length > 0) return new Set(current.map((branch) => branch.id));
  const next =
    branches.find((branch) => branch.unlocked && !complete(branch)) ??
    branches.find((branch) => !complete(branch));
  return new Set(next === undefined ? [] : [next.id]);
}

/** Professional BranchOverview: a numbered, ruled syllabus per track. No cards. */
export function Syllabus({ branches }: BranchOverviewProps) {
  const lexicon = useLexicon();
  const [open, setOpen] = useState<ReadonlySet<string>>(() => openTracks(branches));
  const toggle = (id: string, show: boolean) => {
    setOpen((current) => {
      const next = new Set(current);
      if (show) next.add(id);
      else next.delete(id);
      return next;
    });
  };
  return (
    <div className="lg:grid lg:grid-cols-[14rem_minmax(0,1fr)] lg:gap-12">
      <nav
        aria-label={lexicon.branchPlural}
        className="mb-8 lg:sticky lg:top-6 lg:mb-0 lg:max-h-[calc(100vh-3rem)] lg:self-start lg:overflow-y-auto"
      >
        <ol className="m-0 list-none space-y-3 p-0">
          {branches.map((branch, index) => (
            <li key={branch.id}>
              <a
                href={`#track-${branch.id}`}
                className="block text-ink no-underline hover:underline"
                onClick={() => {
                  // Going to a folded track opens it.
                  toggle(branch.id, true);
                }}
              >
                <span className="tabular text-ink-muted">{index + 1}. </span>
                {branch.title}
              </a>
              <span className="tabular block text-sm text-ink-muted">
                {lexicon.progressLabel(branch.passed_count, branch.exercises.length)}
              </span>
            </li>
          ))}
        </ol>
      </nav>

      <div className="space-y-12">
        {branches.map((branch, index) => {
          const shown = open.has(branch.id);
          const listId = `track-list-${branch.id}`;
          return (
            <section
              key={branch.id}
              id={`track-${branch.id}`}
              aria-labelledby={`heading-${branch.id}`}
            >
              <header className="space-y-2 border-b-2 border-ink pb-3">
                <p className="label-caps m-0 text-ink-muted">
                  {branch.kind === 'project'
                    ? lexicon.projectLabel
                    : `${lexicon.branch} ${index + 1}`}{' '}
                  · {lexicon.exerciseCount(branch.exercises.length)}
                  {branch.pro && (
                    <>
                      {' '}
                      <ProMark />
                    </>
                  )}
                </p>
                <h2 id={`heading-${branch.id}`} className="m-0 text-xl">
                  {branch.title}
                </h2>
                <p className="m-0 max-w-measure text-base text-ink-secondary">{branch.summary}</p>
                {!branch.unlocked && (
                  <p className="m-0 text-sm text-ink-muted">
                    {lexicon.lockedBranch(branch.requires.map((id) => titleOf(branches, id)))}
                  </p>
                )}
                <ProgressRule
                  value={branch.passed_count}
                  max={branch.exercises.length}
                  label={`${branch.title} progress`}
                  caption={lexicon.progressLabel(branch.passed_count, branch.exercises.length)}
                />
                <button
                  type="button"
                  aria-expanded={shown}
                  aria-controls={listId}
                  onClick={() => {
                    toggle(branch.id, !shown);
                  }}
                  className="-ml-1 inline-flex min-h-11 items-center gap-2 rounded-control px-1 text-sm font-medium text-ink hover:underline"
                >
                  <ChevronRight
                    aria-hidden="true"
                    className={`h-4 w-4 transition-transform duration-fast ${shown ? 'rotate-90' : ''}`}
                  />
                  {shown ? 'Hide' : 'Show'} {lexicon.exerciseCount(branch.exercises.length)}{' '}
                  <span className="sr-only">in {branch.title}</span>
                </button>
              </header>
              <ol id={listId} hidden={!shown} className="m-0 list-none p-0">
                {branch.exercises.map((exercise, position) => (
                  <li
                    key={exercise.id}
                    className={
                      exercise.tier === 'capstone'
                        ? 'mt-3 border-y-2 border-tier-capstone'
                        : 'border-b border-line-subtle'
                    }
                  >
                    {exercise.tier === 'capstone' && (
                      <p className="label-caps m-0 pt-3 text-tier-capstone">
                        {lexicon.capstoneLabel}
                      </p>
                    )}
                    <Link
                      to="/exercises/$exerciseId"
                      params={{ exerciseId: exercise.id }}
                      className="group grid min-h-11 grid-cols-[2rem_minmax(0,1fr)] gap-x-3 gap-y-1 py-3 text-ink no-underline sm:grid-cols-[2.5rem_minmax(0,1fr)_auto_auto_7.5rem] sm:items-center sm:gap-x-4"
                    >
                      <span className="tabular row-span-1 text-ink-muted">
                        {String(position + 1).padStart(2, '0')}
                      </span>
                      <span className="min-w-0">
                        <span
                          className={`block font-medium group-hover:underline ${exercise.status === 'locked' ? 'text-ink-secondary' : ''}`}
                        >
                          {exercise.title}
                        </span>
                        <span className="block truncate text-sm text-ink-muted">
                          {exercise.skills.join(' · ')}
                        </span>
                      </span>
                      <span className="col-start-2 inline-flex flex-wrap items-center gap-2 sm:col-start-auto">
                        <TierMark tier={exercise.tier} />
                        {exercise.pro && !branch.pro && <ProMark />}
                      </span>
                      <span className="tabular col-start-2 text-sm text-ink-secondary sm:col-start-auto">
                        {lexicon.xpLabel(exercise.xp)}
                      </span>
                      <span className="col-start-2 sm:col-start-auto sm:justify-self-end">
                        <StatusMark status={exercise.status} />
                      </span>
                    </Link>
                  </li>
                ))}
              </ol>
            </section>
          );
        })}
      </div>
    </div>
  );
}
