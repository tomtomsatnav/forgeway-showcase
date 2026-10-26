import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { AttemptDetail } from '../../api/types';
import { progression } from '../../test/fixtures';
import { renderInRouter, withMode } from '../../test/render';
import { ResultsPanel } from './ResultsPanel';

const base: AttemptDetail = {
  id: 'a',
  exercise_id: 'x',
  status: 'failed',
  created_at: '2026-01-01T00:00:00Z',
  finished_at: '2026-01-01T00:00:02Z',
  checks: [],
  error: null,
  duration_ms: 1200,
  progression: null,
};

const checks = [{ id: 'c1', title: 'Returns the reply', kind: 'functional' }];

describe('ResultsPanel', () => {
  it('lists what will be checked before the first run', () => {
    render(
      withMode(
        'professional',
        <ResultsPanel
          checks={checks}
          polling={{ phase: 'idle', attempt: null }}
          submitting={false}
        />,
      ),
    );

    expect(screen.getByText('Returns the reply')).toBeVisible();
  });

  it('shows each result with a pass or fail word', () => {
    const attempt: AttemptDetail = {
      ...base,
      checks: [
        { id: 'c1', title: 'Returns the reply', passed: true, message: '', output: '' },
        {
          id: 'c2',
          title: 'Sends a user message',
          passed: false,
          message: 'Got role "system"',
          output: '',
        },
      ],
    };
    render(
      withMode(
        'professional',
        <ResultsPanel checks={checks} polling={{ phase: 'done', attempt }} submitting={false} />,
      ),
    );

    expect(screen.getByText('Not yet: 1 of 2 checks passed')).toBeVisible();
    // Results animate in from transparent, so assert presence rather than visibility.
    expect(screen.getByText('Passed')).toBeInTheDocument();
    expect(screen.getByText('Failed')).toBeInTheDocument();
    expect(screen.getByText('Got role "system"')).toBeInTheDocument();
  });

  it('shows a grader error and says it does not count against the learner', () => {
    const attempt: AttemptDetail = { ...base, status: 'errored', error: 'Sandbox timed out' };
    render(
      withMode(
        'professional',
        <ResultsPanel checks={checks} polling={{ phase: 'done', attempt }} submitting={false} />,
      ),
    );

    expect(screen.getByText('Sandbox timed out')).toBeVisible();
    expect(screen.getByText(/does not count against you/)).toBeVisible();
  });

  it('explains a timeout clearly', () => {
    render(
      withMode(
        'professional',
        <ResultsPanel
          checks={checks}
          polling={{ phase: 'timeout', attempt: null }}
          submitting={false}
        />,
      ),
    );

    expect(screen.getByText(/taking longer than expected/)).toBeVisible();
  });

  it('shows a badge and the streak earned by a failed attempt, without a completion moment', () => {
    const news = progression({
      xp_awarded: 0,
      level_after: 1,
      badges_awarded: [
        { id: 'three', title: 'Three in a row', description: 'Learned on three days.' },
      ],
      streak: { current: 3, longest: 3 },
    });
    const attempt: AttemptDetail = { ...base, progression: news };
    render(
      withMode(
        'rpg',
        <ResultsPanel
          checks={checks}
          polling={{ phase: 'done', attempt }}
          submitting={false}
          news={news}
        />,
      ),
    );

    expect(screen.getByText('Not yet: 0 of 0 checks passed')).toBeVisible();
    expect(screen.getByText('Badge won: Three in a row')).toBeVisible();
    expect(screen.getByText('Learning streak: 3 days')).toBeVisible();
  });

  it('announces an earned certificate with a link to the profile', async () => {
    const news = progression({
      certificates_issued: [
        {
          id: 'cert_1',
          branch_id: 'starter',
          branch_title: 'Foundations',
          includes_capstone: false,
        },
      ],
    });
    const attempt: AttemptDetail = { ...base, status: 'passed', progression: news };
    await renderInRouter(
      withMode(
        'professional',
        <ResultsPanel
          checks={checks}
          polling={{ phase: 'done', attempt }}
          submitting={false}
          news={news}
        />,
      ),
    );

    expect(await screen.findByText('Certificate earned: Foundations track')).toBeVisible();
    expect(screen.getByRole('link', { name: 'View your certificates' })).toHaveAttribute(
      'href',
      '/profile#certificates',
    );
  });

  it('shows no news unless the page passes some', () => {
    const attempt: AttemptDetail = {
      ...base,
      progression: progression({ talent_points_gained: 1 }),
    };
    render(
      withMode(
        'professional',
        <ResultsPanel checks={checks} polling={{ phase: 'done', attempt }} submitting={false} />,
      ),
    );

    expect(screen.queryByText('+1 competency point')).not.toBeInTheDocument();
  });
});
