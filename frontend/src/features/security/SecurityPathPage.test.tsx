import { screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { BranchSummary, ExerciseSummary } from '../../api/types';
import { json, problem, stubApi } from '../../test/fixtures';
import { renderInRouter, withMode } from '../../test/render';
import { LEXICONS } from '../../theme/lexicon';
import { SecurityPathPage, securityPath } from './SecurityPathPage';

const exercise = (id: string, skills: string[], pro = false): ExerciseSummary => ({
  id,
  title: id,
  tier: 'intermediate',
  xp: 100,
  prerequisites: [],
  skills,
  status: 'available',
  pro,
  entitled: !pro,
});

const branch = (id: string, exercises: ExerciseSummary[]): BranchSummary => ({
  id,
  title: `Track ${id}`,
  summary: '',
  unlocked: true,
  requires: [],
  kind: 'standard',
  passed_count: 0,
  pro: false,
  exercises,
});

const BRANCHES = [
  branch('starter', [
    exercise('starter.plain', ['tool-use']),
    exercise('starter.inject', ['security']),
  ]),
  branch('evals', [exercise('evals.guard', ['guardrails', 'security'], true)]),
];

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('securityPath', () => {
  it('keeps only tagged exercises, in track order', () => {
    expect(securityPath(BRANCHES).map((step) => step.exercise.id)).toEqual([
      'starter.inject',
      'evals.guard',
    ]);
  });
});

describe('SecurityPathPage', () => {
  it('shows a visitor the path from the public catalogue, marking Pro steps', async () => {
    stubApi({
      'GET /api/auth/me': () => problem(401, 'Unauthenticated', 'unauthenticated'),
      'GET /api/catalogue': () => json({ branches: BRANCHES }),
    });
    await renderInRouter(withMode('professional', <SecurityPathPage />));

    const [path] = await screen.findAllByRole('list');
    if (path === undefined) throw new Error('The page has no list.');
    const [first, second, ...rest] = within(path).getAllByRole('listitem') as [
      HTMLElement,
      HTMLElement,
    ];
    expect(rest).toHaveLength(0);
    expect(within(first).getByRole('link')).toHaveAttribute('href', '/exercises/starter.inject');
    expect(within(second).getByText('Track evals')).toBeVisible();
    expect(screen.queryByText('starter.plain')).toBeNull();
    expect(document.title).toBe(LEXICONS.professional.securityPath.documentTitle);
  });
});
