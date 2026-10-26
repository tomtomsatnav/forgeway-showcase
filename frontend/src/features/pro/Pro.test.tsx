import { cleanup, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { BranchSummary, ExerciseDetail, Mode } from '../../api/types';
import { MAP, capstoneBranch, json, stubApi } from '../../test/fixtures';
import { renderInRouter, withMode } from '../../test/render';
import { LEXICONS } from '../../theme/lexicon';
import { BranchOverview } from '../../theme/slots';
import { ProPreview } from '../workspace/WorkspacePage';
import { ProCallToAction } from './ProCallToAction';
import { ProPage } from './ProPage';

const NOT_JOINED = { joined: false, plan_interest: null, joined_at: null };
const JOINED = { joined: true, plan_interest: 'pro', joined_at: '2026-10-26T10:00:00Z' };

/** Retrieval with its capstone marked Pro, as the API marks it for every plan. */
function withProCapstone(): BranchSummary {
  const branch = capstoneBranch('locked');
  return {
    ...branch,
    exercises: branch.exercises.map((exercise) =>
      exercise.tier === 'capstone' ? { ...exercise, pro: true, entitled: false } : exercise,
    ),
  };
}

const CAPSTONE: ExerciseDetail = {
  id: 'retrieval.search-service',
  branch: 'retrieval',
  title: 'Build a search service',
  tier: 'capstone',
  xp: 350,
  status: 'locked',
  pro: true,
  entitled: false,
  prerequisites: [],
  brief: '# Build a search service\n\nShip the whole retrieval stack behind one endpoint.\n',
  editable: ['service.py'],
  files: { 'service.py': '' },
  files_source: 'starter',
  carried_from: null,
  checks: [],
  hints_total: 0,
  hints_revealed: [],
  recent_attempts: [],
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('the Pro mark', () => {
  it('tags Pro exercises, and only those, with "Pro" in professional mode', async () => {
    await renderInRouter(
      withMode('professional', <BranchOverview branches={[withProCapstone()]} />),
    );

    const capstone = await screen.findByRole('link', { name: /Build a search service/ });
    expect(within(capstone).getByText('Pro')).toBeVisible();
    expect(capstone).toHaveAccessibleName(expect.stringContaining('Part of Forgeway Pro'));
    const free = screen.getByRole('link', { name: /Fixed-size chunking/ });
    expect(within(free).queryByText('Pro')).not.toBeInTheDocument();
  });

  it.each(['pro', 'team'] as const)('is not shown to a learner on the %s plan', async (plan) => {
    stubApi({ 'GET /api/auth/me': () => json({ plan, csrf_token: 'x' }) });
    await renderInRouter(
      withMode('professional', <BranchOverview branches={[withProCapstone()]} />),
    );

    const capstone = await screen.findByRole('link', { name: /Build a search service/ });
    await waitFor(() => {
      expect(within(capstone).queryByText('Pro')).not.toBeInTheDocument();
    });
  });

  it('shows no waitlist to a learner who already has Pro', async () => {
    stubApi({
      'GET /api/auth/me': () => json({ plan: 'team', csrf_token: 'x' }),
      'GET /api/pro/waitlist': () => json(NOT_JOINED),
    });
    await renderInRouter(withMode('professional', <ProCallToAction />));

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: 'Join the waitlist' })).toBeNull();
    });
  });

  it('marks a waypoint for guild members in RPG mode, keeping "Pro" visible', async () => {
    await renderInRouter(
      withMode('rpg', <BranchOverview branches={[withProCapstone()]} />),
      undefined,
      '/?zone=retrieval',
    );

    const lair = await screen.findByRole('link', { name: /Build a search service/ });
    expect(lair).toHaveTextContent('Guild · Pro');
    const free = screen.getByRole('link', { name: /Fixed-size chunking/ });
    expect(free).not.toHaveTextContent('Pro');
  });

  it.each([
    ['professional', '/'],
    ['rpg', '/?zone=retrieval'],
  ] as const)('marks a whole guided project once in %s mode', async (mode, entry) => {
    const project: BranchSummary = {
      ...capstoneBranch('locked'),
      kind: 'project',
      pro: true,
    };
    await renderInRouter(withMode(mode, <BranchOverview branches={[project]} />), undefined, entry);
    const region = await screen.findByRole('region', { name: 'Retrieval' });
    expect(within(region).getAllByText(LEXICONS[mode].proMark)).toHaveLength(1);
  });
});

describe('the Pro call to action', () => {
  it.each<Mode>(['professional', 'rpg'])(
    'joins the waitlist and then says so, with no price (%s)',
    async (mode) => {
      const seen = stubApi({
        'GET /api/pro/waitlist': () => json(NOT_JOINED),
        'POST /api/pro/waitlist': () => json(JOINED),
      });
      await renderInRouter(withMode(mode, <ProCallToAction />));
      const lexicon = LEXICONS[mode];

      const cta = await screen.findByRole('complementary', { name: lexicon.proCtaTitle });
      expect(cta).toHaveTextContent('Forgeway Pro');
      expect(cta.textContent).not.toMatch(/£|\$|price|pre-order|buy/i);
      expect(within(cta).getByRole('link', { name: lexicon.proLearnMore })).toHaveAttribute(
        'href',
        '/pro',
      );

      await userEvent
        .setup()
        .click(await within(cta).findByRole('button', { name: 'Join the waitlist' }));
      expect(await within(cta).findByRole('status')).toHaveTextContent(lexicon.proJoined);
      expect(within(cta).queryByRole('button', { name: 'Join the waitlist' })).toBeNull();
      const post = seen.find((request) => request.method === 'POST');
      expect(await post?.json()).toEqual({ plan: 'pro' });
      cleanup();
    },
  );

  it('shows the brief and the waitlist in place of the run button on a Pro exercise', async () => {
    stubApi({
      'GET /api/pro/waitlist': () => json(NOT_JOINED),
      'GET /api/map': () => json(MAP),
    });
    await renderInRouter(withMode('professional', <ProPreview exercise={CAPSTONE} />));

    expect(await screen.findByText(/Ship the whole retrieval stack/)).toBeVisible();
    expect(screen.getByRole('complementary', { name: 'Forgeway Pro is coming' })).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Run checks' })).toBeNull();
    expect(screen.queryByRole('textbox', { name: /code editor/i })).toBeNull();
    expect(screen.getByText('Capstone project')).toBeVisible();
  });

  it('puts the call to action before the brief, so a phone reaches it first', async () => {
    stubApi({
      'GET /api/pro/waitlist': () => json(NOT_JOINED),
      'GET /api/map': () => json(MAP),
    });
    await renderInRouter(withMode('professional', <ProPreview exercise={CAPSTONE} />));

    const cta = await screen.findByRole('complementary', { name: 'Forgeway Pro is coming' });
    const brief = screen.getByRole('region', { name: 'Brief' });
    expect(cta.compareDocumentPosition(brief) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // From 1024px the grid places it in the second column, beside the brief.
    expect(cta.parentElement).toHaveClass('lg:col-start-2', 'lg:row-start-1');
    expect(brief).toHaveClass('lg:col-start-1', 'lg:row-start-1');
  });
});

describe('the Pro page', () => {
  it('lists what Pro includes and what stays free, and remembers joining', async () => {
    stubApi({
      'GET /api/pro/waitlist': () => json(JOINED),
      'GET /api/auth/me': () => json({ plan: 'free', csrf_token: 'x' }),
      'GET /api/config': () => json({ turnstile_site_key: null, free_exercises_per_branch: 3 }),
    });
    await renderInRouter(withMode('professional', <ProPage />));

    expect(await screen.findByRole('heading', { level: 1, name: 'Forgeway Pro' })).toBeVisible();
    expect(screen.getByText(/capstone project that closes every track/)).toBeVisible();
    expect(await screen.findByText(/first 3 exercises of every track stay free/)).toBeVisible();
    expect(await screen.findByText('You are on the waitlist.')).toBeVisible();
    expect(screen.getByText(/nothing is charged/)).toBeVisible();
    expect(document.body.textContent).not.toMatch(/£|\$\d|pre-order/i);
  });

  it('tells a learner who already has Pro, in RPG wording', async () => {
    stubApi({
      'GET /api/pro/waitlist': () => json(NOT_JOINED),
      'GET /api/auth/me': () => json({ plan: 'pro', csrf_token: 'x' }),
      'GET /api/config': () => json({ turnstile_site_key: null, free_exercises_per_branch: 3 }),
    });
    await renderInRouter(withMode('rpg', <ProPage />));

    expect(await screen.findByText(/already a guild member/)).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Join the waitlist' })).toBeNull();
  });
});
