import { cleanup, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import type { BranchSummary, Mode } from '../../api/types';
import { renderInRouter, withMode } from '../../test/render';
import { LEXICONS } from '../lexicon';
import { BranchOverview } from '.';
import { openTracks } from './Syllabus';

const branches: BranchSummary[] = [
  {
    id: 'starter',
    title: 'Foundations',
    summary: 'How language models behave.',
    unlocked: true,
    requires: [],
    kind: 'standard',
    pro: false,
    passed_count: 1,
    exercises: [
      {
        id: 'starter.first-completion',
        title: 'Your first completion',
        tier: 'beginner',
        xp: 50,
        prerequisites: [],
        skills: ['model-apis'],
        status: 'passed',
        pro: false,
        entitled: true,
      },
      {
        id: 'starter.system-prompts',
        title: 'System prompts and few-shot examples',
        tier: 'intermediate',
        xp: 60,
        prerequisites: [],
        skills: ['prompting'],
        status: 'available',
        pro: false,
        entitled: true,
      },
      {
        id: 'starter.retries',
        title: 'Retries and backoff',
        tier: 'advanced',
        xp: 125,
        prerequisites: [],
        skills: ['retries'],
        status: 'locked',
        pro: false,
        entitled: true,
      },
    ],
  },
  {
    id: 'retrieval',
    title: 'Retrieval',
    summary: 'Search and ranking.',
    unlocked: false,
    requires: ['starter'],
    kind: 'standard',
    pro: false,
    passed_count: 0,
    exercises: [
      {
        id: 'retrieval.chunking',
        title: 'Fixed-size chunking',
        tier: 'beginner',
        xp: 75,
        prerequisites: [],
        skills: ['chunking'],
        status: 'locked',
        pro: false,
        entitled: true,
      },
    ],
  },
];

const allExercises = branches.flatMap((branch) => branch.exercises);
const modes: Mode[] = ['professional', 'rpg'];

interface ExerciseLink {
  href: string | null;
  name: string;
}

/**
 * Every exercise link a mode shows; RPG shows one zone at a time, so visit each in turn, and the
 * syllabus folds finished and locked tracks, so open each of those.
 */
async function exerciseLinks(mode: Mode): Promise<ExerciseLink[]> {
  const entries = mode === 'rpg' ? branches.map((branch) => `/?zone=${branch.id}`) : ['/'];
  const found: ExerciseLink[] = [];
  for (const entry of entries) {
    await renderInRouter(withMode(mode, <BranchOverview branches={branches} />), undefined, entry);
    for (const fold of screen.queryAllByRole('button', { name: /^Show / }))
      await userEvent.click(fold);
    const links = await screen.findAllByRole('link', { name: /./ });
    for (const link of links) {
      if (link.getAttribute('href')?.startsWith('/exercises/'))
        found.push({
          href: link.getAttribute('href'),
          name: link.getAttribute('aria-label') ?? link.textContent,
        });
    }
    cleanup();
  }
  return found;
}

describe('BranchOverview renderers', () => {
  it.each(modes)('exposes every exercise as a link with its status in %s mode', async (mode) => {
    const links = await exerciseLinks(mode);

    expect(links.map((link) => link.href)).toEqual(
      allExercises.map((exercise) => `/exercises/${exercise.id}`),
    );
    for (const exercise of allExercises) {
      const link = links.find((candidate) => candidate.href === `/exercises/${exercise.id}`);
      expect(link, exercise.id).toBeDefined();
      expect(link?.name).toContain(exercise.title);
      expect(link?.name).toContain(LEXICONS[mode].status[exercise.status]);
    }
  });

  it('exposes the same exercises, in the same order, in both modes', async () => {
    const professional = await exerciseLinks('professional');
    const rpg = await exerciseLinks('rpg');

    expect(rpg.map((link) => link.href)).toEqual(professional.map((link) => link.href));
  });

  it('names each track with a heading and explains a locked one in professional mode', async () => {
    await renderInRouter(withMode('professional', <BranchOverview branches={branches} />));

    const retrieval = await screen.findByRole('region', { name: 'Retrieval' });
    expect(within(retrieval).getByRole('heading', { name: 'Retrieval' })).toBeInTheDocument();
    expect(within(retrieval).getByText(/Foundations/)).toBeInTheDocument();
    expect(await screen.findByRole('region', { name: 'Foundations' })).toBeInTheDocument();
  });

  it('names a selected zone with a heading and explains a locked one in RPG mode', async () => {
    await renderInRouter(
      withMode('rpg', <BranchOverview branches={branches} />),
      undefined,
      '/?zone=retrieval',
    );

    const retrieval = await screen.findByRole('region', { name: 'Retrieval' });
    expect(within(retrieval).getByRole('heading', { name: 'Retrieval' })).toBeInTheDocument();
    expect(within(retrieval).getByText(/Foundations/)).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Foundations' })).not.toBeInTheDocument();
  });

  it('leads with zone and quest names in RPG mode while keeping the real titles visible', async () => {
    await renderInRouter(
      withMode('rpg', <BranchOverview branches={branches} />),
      {
        branches: {
          starter: {
            name: 'The Foundry Vale',
            epithet: 'Where journeys are forged',
            lore: 'Old crafts.',
          },
        },
        quests: { 'starter.first-completion': 'The First Utterance' },
        paths: {},
        bosses: {},
      },
      '/?zone=starter',
    );

    const zone = await screen.findByRole('region', { name: 'The Foundry Vale' });
    expect(within(zone).getByText('Where journeys are forged')).toBeInTheDocument();
    expect(within(zone).getByText('Foundations')).toBeInTheDocument();
    const link = within(zone).getByRole('link', { name: /The First Utterance/ });
    expect(link).toHaveAccessibleName(expect.stringContaining('Your first completion'));
    expect(within(zone).getByText('Your first completion')).toBeInTheDocument();
  });

  it.each([
    ['professional', '/', 'Guided project'],
    ['rpg', '/?zone=retrieval', 'Expedition'],
  ] as const)('frames a project branch as one in %s mode', async (mode, entry, label) => {
    const asProject = branches.map((branch) =>
      branch.id === 'retrieval' ? { ...branch, kind: 'project' as const } : branch,
    );
    await renderInRouter(withMode(mode, <BranchOverview branches={asProject} />), undefined, entry);

    const project = await screen.findByRole('region', { name: 'Retrieval' });
    expect(within(project).getByText(new RegExp(`^${label}`))).toBeInTheDocument();
    if (mode === 'professional') {
      const starter = screen.getByRole('region', { name: 'Foundations' });
      expect(within(starter).queryByText(/Guided project/)).not.toBeInTheDocument();
      expect(within(starter).getByText(/^track 1/)).toBeInTheDocument();
    }
  });

  it('ignores flavour in professional mode', async () => {
    await renderInRouter(withMode('professional', <BranchOverview branches={branches} />), {
      branches: { starter: { name: 'The Foundry Vale', epithet: 'x', lore: 'y' } },
      quests: { 'starter.first-completion': 'The First Utterance' },
      paths: {},
      bosses: {},
    });

    expect(await screen.findByRole('region', { name: 'Foundations' })).toBeInTheDocument();
    expect(screen.queryByText('The Foundry Vale')).not.toBeInTheDocument();
  });
});

describe('syllabus folding', () => {
  const [base] = branches;
  if (base === undefined) throw new Error('No fixture branch');
  const track = (id: string, unlocked: boolean, passed: number, total = 3): BranchSummary => ({
    ...base,
    id,
    title: id,
    unlocked,
    passed_count: passed,
    exercises: base.exercises.slice(0, total),
  });

  it('opens the tracks in progress, else the next one; folds the rest', () => {
    expect([
      ...openTracks([
        track('done', true, 3),
        track('doing', true, 1),
        track('untouched', true, 0),
        track('locked', false, 0),
        track('also-doing', true, 2),
      ]),
    ]).toEqual(['doing', 'also-doing']);
    // Nothing in progress: the next track to take stays open, even before it unlocks.
    expect([...openTracks([track('done', true, 3), track('locked', false, 0)])]).toEqual([
      'locked',
    ]);
    expect([
      ...openTracks([track('done', true, 3), track('fresh', true, 0), track('later', true, 0)]),
    ]).toEqual(['fresh']);
    expect([...openTracks([track('done', true, 3)])]).toEqual([]);
  });

  it('folds a locked track behind a button that says what it holds, and opens it', async () => {
    await renderInRouter(withMode('professional', <BranchOverview branches={branches} />));
    const retrieval = await screen.findByRole('region', { name: 'Retrieval' });
    const fold = within(retrieval).getByRole('button', { name: /^Show 1 exercise in Retrieval$/ });
    expect(fold).toHaveAttribute('aria-expanded', 'false');
    const list = document.getElementById(fold.getAttribute('aria-controls') ?? '');
    expect(list).not.toBeVisible();
    expect(within(retrieval).queryByRole('link', { name: /Fixed-size chunking/ })).toBeNull();

    await userEvent.click(fold);
    expect(fold).toHaveAttribute('aria-expanded', 'true');
    expect(list).toBeVisible();
    expect(within(retrieval).getByRole('link', { name: /Fixed-size chunking/ })).toBeVisible();
    expect(fold).toHaveAccessibleName('Hide 1 exercise in Retrieval');

    // The track in progress is open, and folds on request.
    const foundations = screen.getByRole('region', { name: 'Foundations' });
    const open = within(foundations).getByRole('button', { name: /exercises in Foundations$/ });
    expect(open).toHaveAttribute('aria-expanded', 'true');
    await userEvent.click(open);
    expect(open).toHaveAttribute('aria-expanded', 'false');
  });

  it('opens a folded track when its entry in the index is followed', async () => {
    await renderInRouter(withMode('professional', <BranchOverview branches={branches} />));
    const index = await screen.findByRole('navigation', { name: 'tracks' });
    await userEvent.click(within(index).getByRole('link', { name: /Retrieval/ }));
    const retrieval = screen.getByRole('region', { name: 'Retrieval' });
    expect(within(retrieval).getByRole('link', { name: /Fixed-size chunking/ })).toBeVisible();
  });
});
