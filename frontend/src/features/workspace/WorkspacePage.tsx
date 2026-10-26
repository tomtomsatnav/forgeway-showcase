import { useQueryClient } from '@tanstack/react-query';
import { Link, getRouteApi } from '@tanstack/react-router';
import { Check, CloudOff, Lock, Play } from 'lucide-react';
import { useEffect, useRef, useState, type CSSProperties } from 'react';

import { errorMessage } from '../../api/errors';
import {
  queryKeys,
  useExercise,
  useLearnerMap,
  useMe,
  useResetToStarter,
  useRevealHint,
  useSubmitAttempt,
} from '../../api/hooks';
import { toTier, type ExerciseDetail, type LearnerMap } from '../../api/types';
import { useProblemMessage } from '../../api/useProblemMessage';
import { Button } from '../../components/Button';
import { CodeEditor } from '../../components/CodeEditor';
import { HintReveal } from '../../components/HintReveal';
import { Markdown, withoutLeadingTitle } from '../../components/Markdown';
import { ProMark } from '../../components/ProMark';
import { Splitter } from '../../components/Splitter';
import { KEY_STEP, useResizableColumns } from '../../components/useResizableColumns';
import { useFlavour } from '../../theme/flavour';
import { CompletionMoment, PageHeader } from '../../theme/slots';
import { useLexicon } from '../../theme/useTheme';
import { ProCallToAction } from '../pro/ProCallToAction';
import { BackToMap } from './BackToMap';
import { CarriedFiles } from './CarriedFiles';
import { ResetCode } from './ResetCode';
import { ReferenceSolution } from './ReferenceSolution';
import { ResultsPanel } from './ResultsPanel';
import { useAttemptPolling } from './useAttemptPolling';
import { useDraftAutosave, type SaveState } from './useDraftAutosave';

const route = getRouteApi('/exercises/$exerciseId');

export function WorkspacePage() {
  const { exerciseId } = route.useParams();
  const exercise = useExercise(exerciseId);

  if (exercise.isPending) {
    return (
      <p role="status" className="px-4 py-12 text-ink-muted sm:px-6">
        Loading…
      </p>
    );
  }
  if (exercise.isError) {
    return (
      <div className="mx-auto max-w-page space-y-4 px-4 py-12 sm:px-6">
        <p role="alert" className="m-0 text-danger">
          {errorMessage(exercise.error)}
        </p>
        <BackToMap />
      </div>
    );
  }
  // Locked by plan comes before locked by prerequisites: no progress opens it on the free plan.
  if (!exercise.data.entitled) return <ProPreview exercise={exercise.data} />;
  if (exercise.data.status === 'locked') return <Locked exercise={exercise.data} />;
  return <Workspace key={exercise.data.id} exercise={exercise.data} />;
}

/** A Pro exercise on the free plan: the brief to read, and the waitlist in place of running. */
export function ProPreview({ exercise }: { exercise: ExerciseDetail }) {
  const lexicon = useLexicon();
  return (
    <div className="mx-auto max-w-page space-y-6 px-4 py-8 sm:px-6">
      <div className="space-y-3">
        <BackToMap branch={exercise.branch} />
        <PageHeader
          title={exercise.title}
          exerciseId={exercise.id}
          capstone={exercise.tier === 'capstone'}
          summary={`${lexicon.tier[toTier(exercise.tier)]} · ${lexicon.xpLabel(exercise.xp)}`}
        />
        <ProMark />
      </div>
      {/* The call to action comes first so a phone reaches it before a long brief; from 1024px
          it moves to a column beside the brief. */}
      <div className="space-y-8 lg:grid lg:grid-cols-[minmax(0,1fr)_20rem] lg:gap-12 lg:space-y-0">
        <div className="lg:sticky lg:top-6 lg:col-start-2 lg:row-start-1 lg:self-start">
          <ProCallToAction />
        </div>
        <section id="brief" aria-label="Brief" className="min-w-0 lg:col-start-1 lg:row-start-1">
          <article className="max-w-measure font-reading text-lg">
            <Markdown>{withoutLeadingTitle(exercise.brief)}</Markdown>
          </article>
        </section>
      </div>
    </div>
  );
}

function Locked({ exercise }: { exercise: ExerciseDetail }) {
  const lexicon = useLexicon();
  const flavour = useFlavour();
  const map = useLearnerMap();
  const branches = map.data?.branches ?? [];
  const everyExercise = new Map(
    branches.flatMap((branch) => branch.exercises).map((item) => [item.id, item]),
  );
  const unmet = exercise.prerequisites.flatMap((id) => {
    const found = everyExercise.get(id);
    return found && found.status !== 'passed' ? [found] : [];
  });
  const branch = branches.find((item) => item.id === exercise.branch);
  const gate = branch && !branch.unlocked ? branch : undefined;
  const gateNames = (gate?.requires ?? [])
    .flatMap((id) => {
      const required = branches.find((item) => item.id === id);
      return required && required.passed_count < required.exercises.length ? [required] : [];
    })
    .map((required) => flavour.zone(required.id)?.name ?? required.title);

  return (
    <div className="mx-auto max-w-page space-y-6 px-4 py-8 sm:px-6">
      <PageHeader
        title={exercise.title}
        exerciseId={exercise.id}
        capstone={exercise.tier === 'capstone'}
        summary={`${lexicon.status.locked} ${lexicon.exercise}`}
      />
      <div
        role="note"
        className="flex max-w-measure items-start gap-3 rounded-panel border border-line-strong bg-raised p-4"
      >
        <Lock aria-hidden="true" className="mt-1 h-5 w-5 shrink-0 text-ink-muted" />
        <div className="space-y-3">
          <p className="m-0">{lexicon.lockedExercise}</p>
          {gateNames.length > 0 && <p className="m-0">{lexicon.lockedBranch(gateNames)}</p>}
          {unmet.length > 0 && (
            <>
              <p className="m-0">{lexicon.lockedByExercises}</p>
              <ul className="m-0 list-disc space-y-1 pl-5">
                {unmet.map((item) => (
                  <li key={item.id}>
                    <Link
                      to="/exercises/$exerciseId"
                      params={{ exerciseId: item.id }}
                      className="text-accent-strong underline underline-offset-2"
                    >
                      {item.title}
                    </Link>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      </div>
      <BackToMap branch={exercise.branch} />
    </div>
  );
}

function pick(files: Record<string, string>, paths: readonly string[]): Record<string, string> {
  return Object.fromEntries(paths.map((path) => [path, files[path] ?? '']));
}

/** An exercise's title from the map, or its id while the map loads. */
function titleOf(map: LearnerMap | undefined, id: string): string {
  const exercises = map?.branches.flatMap((branch) => branch.exercises) ?? [];
  return exercises.find((exercise) => exercise.id === id)?.title ?? id;
}

/** The guided project an exercise belongs to, by the name the mode gives it; none for a track. */
function projectOf(
  map: LearnerMap | undefined,
  branchId: string,
  zoneName: (branchId: string) => string | undefined,
): string | undefined {
  const branch = map?.branches.find((item) => item.id === branchId);
  if (branch?.kind !== 'project') return undefined;
  return zoneName(branch.id) ?? branch.title;
}

/** Find the titles of exercises a pass opened, using the map as it was before it refreshes. */
function resolveUnlocked(map: LearnerMap | undefined, ids: readonly string[]) {
  const exercises = map?.branches.flatMap((branch) => branch.exercises) ?? [];
  return ids.flatMap((id) => {
    const found = exercises.find((exercise) => exercise.id === id);
    return found ? [{ id, title: found.title }] : [];
  });
}

function Workspace({ exercise }: { exercise: ExerciseDetail }) {
  const lexicon = useLexicon();
  const flavour = useFlavour();
  const client = useQueryClient();
  const map = useLearnerMap();
  const me = useMe();
  const problemMessage = useProblemMessage();
  const [initialFiles] = useState(() => pick(exercise.files, exercise.editable));
  const [files, setFiles] = useState(initialFiles);
  const [activePath, setActivePath] = useState(exercise.editable[0] ?? '');
  const [attemptId, setAttemptId] = useState<string | null>(null);
  const [dismissedId, setDismissedId] = useState<string | null>(null);
  const draft = useDraftAutosave(exercise.id, files, initialFiles);
  const submit = useSubmitAttempt(exercise.id);
  const reveal = useRevealHint(exercise.id);
  const reset = useResetToStarter(exercise.id);
  // The note stays for this visit, even once edits make the files a draft.
  const [carriedFrom, setCarriedFrom] = useState(
    exercise.files_source === 'carried' ? exercise.carried_from : null,
  );
  const polling = useAttemptPolling(attemptId);
  const handled = useRef<string | null>(null);
  const layout = useRef<HTMLDivElement>(null);
  const columns = useResizableColumns(layout);

  const busy = submit.isPending || polling.phase === 'polling';
  // The server refuses a run from an unverified email, so say so up front instead of after a click.
  const unverified = me.data?.email_verified === false;

  const resetToStarter = () => {
    reset.mutate(undefined, {
      onSuccess: (opened) => {
        const starter = pick(opened.files, opened.editable);
        draft.markSaved(starter);
        setFiles(starter);
        setCarriedFrom(null);
      },
    });
  };

  const run = () => {
    submit.mutate(files, {
      onSuccess: (attempt) => {
        draft.markSaved(files);
        setAttemptId(attempt.id);
      },
    });
  };

  // React once to each finished attempt: mark the exercise passed and refresh the map.
  const finished = polling.phase === 'done' ? polling.attempt : null;
  useEffect(() => {
    if (finished === null || handled.current === finished.id) return;
    handled.current = finished.id;
    if (finished.progression) {
      // Even a failed attempt can move the streak or earn a badge.
      void client.invalidateQueries({ queryKey: queryKeys.map });
      void client.invalidateQueries({ queryKey: queryKeys.badges });
      void client.invalidateQueries({ queryKey: queryKeys.talents });
    }
    if (finished.status !== 'passed') return;
    client.setQueryData<ExerciseDetail>(
      queryKeys.exercise(exercise.id),
      (previous) => previous && { ...previous, status: 'passed' },
    );
    void client.invalidateQueries({ queryKey: queryKeys.map });
  }, [finished, client, exercise.id]);

  const progression =
    finished?.status === 'passed' && finished.id !== dismissedId ? finished.progression : null;

  const announcement = describe(polling, submit.isPending);

  return (
    <div className="px-4 py-6 sm:px-6 xl:flex xl:h-full xl:flex-col">
      <div role="status" className="sr-only">
        {announcement}
      </div>
      <div className="mb-4 space-y-3 xl:shrink-0">
        <BackToMap branch={exercise.branch} />
        <PageHeader
          title={exercise.title}
          exerciseId={exercise.id}
          capstone={exercise.tier === 'capstone'}
          project={projectOf(map.data, exercise.branch, (id) => flavour.zone(id)?.name)}
          summary={`${lexicon.tier[toTier(exercise.tier)]} · ${lexicon.xpLabel(exercise.xp)} · ${lexicon.status[exercise.status]}`}
        />
      </div>

      <div
        ref={layout}
        style={
          {
            '--brief-width': `${columns.sizes.brief}px`,
            '--results-width': `${columns.sizes.results}px`,
          } as CSSProperties
        }
        className="space-y-8 xl:grid xl:min-h-[32rem] xl:flex-1 xl:grid-cols-[var(--brief-width)_1.5rem_minmax(0,1fr)_1.5rem_var(--results-width)] xl:space-y-0"
      >
        <section
          id="brief"
          aria-label="Brief"
          tabIndex={0}
          className="min-w-0 xl:overflow-y-auto xl:pr-2"
        >
          <a
            href="#editor"
            className="mb-4 inline-flex min-h-11 items-center text-sm text-accent-strong underline underline-offset-2 xl:hidden"
          >
            Skip to the editor
          </a>
          <article className="max-w-measure font-reading text-lg">
            <Markdown>{withoutLeadingTitle(exercise.brief)}</Markdown>
          </article>
        </section>

        <Splitter
          label="Resize brief"
          controls="brief"
          value={columns.sizes.brief}
          {...columns.limits.brief}
          step={KEY_STEP}
          onChange={(value) => {
            columns.resize('brief', value);
          }}
        />

        <section id="editor" aria-label="Editor" className="flex min-w-0 flex-col gap-3 xl:min-h-0">
          {carriedFrom != null && (
            <CarriedFiles
              title={flavour.quest(carriedFrom) ?? titleOf(map.data, carriedFrom)}
              pending={reset.isPending}
              error={reset.isError ? errorMessage(reset.error) : null}
              onReset={resetToStarter}
            />
          )}
          <CodeEditor
            files={files}
            paths={exercise.editable}
            activePath={activePath}
            onActivePathChange={setActivePath}
            onChange={(path, value) => {
              setFiles((current) => ({ ...current, [path]: value }));
            }}
          />
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-3">
              <Button
                onClick={run}
                loading={busy}
                disabled={unverified}
                aria-describedby={unverified ? 'run-reason' : undefined}
              >
                <Play aria-hidden="true" className="h-4 w-4" />
                {lexicon.attemptSubmit}
              </Button>
              {unverified && (
                <p id="run-reason" className="m-0 text-sm text-ink-secondary">
                  {lexicon.attemptNeedsVerified}
                </p>
              )}
              {submit.isError && (
                <p
                  role="alert"
                  className="m-0 rounded-control bg-danger-soft px-3 py-2 text-sm text-danger"
                >
                  {problemMessage(submit.error)}
                </p>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <SaveIndicator state={draft.state} />
              {carriedFrom == null && (
                <ResetCode
                  pending={reset.isPending}
                  error={reset.isError ? errorMessage(reset.error) : null}
                  onReset={resetToStarter}
                />
              )}
            </div>
          </div>
        </section>

        <Splitter
          label="Resize results"
          controls="results"
          value={columns.sizes.results}
          {...columns.limits.results}
          step={KEY_STEP}
          invert
          onChange={(value) => {
            columns.resize('results', value);
          }}
        />

        <section
          id="results"
          aria-label="Results"
          tabIndex={0}
          className="min-w-0 space-y-6 xl:overflow-y-auto xl:pl-2"
        >
          <div className="space-y-4">
            <h2 className="m-0 text-lg">Results</h2>
            {progression && (
              <CompletionMoment
                progression={progression}
                unlocked={resolveUnlocked(map.data, progression.unlocked)}
                levelFraction={map.data?.level.fraction ?? 0}
                capstone={
                  exercise.tier === 'capstone'
                    ? { exerciseId: exercise.id, title: exercise.title }
                    : null
                }
                onDismiss={() => {
                  setDismissedId(finished?.id ?? null);
                }}
              />
            )}
            <ResultsPanel
              checks={exercise.checks}
              polling={polling}
              submitting={submit.isPending}
              news={progression ? null : finished?.progression}
            />
          </div>
          <HintReveal
            revealed={exercise.hints_revealed}
            total={exercise.hints_total}
            pending={reveal.isPending}
            error={reveal.isError ? problemMessage(reveal.error) : null}
            onReveal={() => {
              reveal.mutate();
            }}
          />
          <ReferenceSolution exerciseId={exercise.id} passed={exercise.status === 'passed'} />
        </section>
      </div>
    </div>
  );
}

function SaveIndicator({ state }: { state: SaveState }) {
  if (state === 'idle') return <span />;
  const Icon = state === 'error' ? CloudOff : Check;
  const text = { saving: 'Saving draft…', saved: 'Draft saved', error: 'Draft not saved' }[state];
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-xs ${state === 'error' ? 'text-danger' : 'text-ink-muted'}`}
    >
      {state !== 'saving' && <Icon aria-hidden="true" className="h-3.5 w-3.5" />}
      {text}
    </span>
  );
}

function describe(polling: ReturnType<typeof useAttemptPolling>, submitting: boolean): string {
  if (submitting) return 'Submitting your code.';
  switch (polling.phase) {
    case 'polling':
      return 'Running checks.';
    case 'timeout':
      return 'Grading is taking longer than expected.';
    case 'failed':
      return polling.message;
    case 'done': {
      const { status, checks } = polling.attempt;
      if (status === 'errored')
        return 'The grader hit a problem. This attempt does not count against you.';
      const passed = checks.filter((check) => check.passed).length;
      return `${status === 'passed' ? 'Passed' : 'Not yet'}. ${passed} of ${checks.length} checks passed.`;
    }
    case 'idle':
      return '';
  }
}
