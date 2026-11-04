import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { LiveRunDetail, Mode } from '../../api/types';
import { json, stubApi } from '../../test/fixtures';
import { newQueryClient, QueryWrapper, withMode } from '../../test/render';
import { problemMessage, toApiError } from '../../api/errors';
import { LEXICONS } from '../../theme/lexicon';
import { formatUsd, TryLive } from './TryLive';

const CONFIG = {
  turnstile_site_key: null,
  free_exercises_per_branch: 3,
  kit_wheel_url: null,
  live_runs: true,
  live_model: 'claude-haiku-5-5' as string | null,
};

const NOTICE =
  'A live run sends your current files and the messages your program sends to Anthropic, PBC in the United States.';

const ALLOWANCE = {
  monthly_cap_usd: 10,
  spent_month_usd: 0.000005,
  daily_cap_usd: 1,
  spent_today_usd: 0.000005,
  remaining_usd: 0.999995,
  exhausted: null,
  resets_at: '2026-11-04T00:00:00+00:00',
};

function run(overrides: Partial<LiveRunDetail> = {}): LiveRunDetail {
  return {
    id: 'run-1',
    exercise_id: 'starter.one',
    status: 'finished',
    created_at: '2026-11-03T12:00:00Z',
    finished_at: '2026-11-03T12:00:03Z',
    outcome: 'finished',
    message: null,
    exit_status: 0,
    stdout: 'The model said: four\n',
    stderr: '',
    stdout_truncated: false,
    stderr_truncated: false,
    duration_ms: 2900,
    calls: [
      {
        model: 'claude-haiku-5-5',
        requested_model: 'claude-opus-5-5',
        max_tokens: 1024,
        input_tokens: 30,
        output_tokens: 4,
        cache_read_tokens: 0,
        cache_write_tokens: 0,
        cost_usd: 0.000005,
        latency_ms: 412,
        outcome: 'ok',
      },
    ],
    total_cost_usd: 0.000005,
    allowance: ALLOWANCE,
    ...overrides,
  };
}

function mount(
  mode: Mode,
  routes: Record<string, (request: Request) => Response> = {},
  { config = CONFIG, hasLiveExample = true } = {},
) {
  const seen = stubApi({
    'GET /api/config': () => json(config),
    'GET /api/live/notice': () => json({ version: 'v1', text: NOTICE, acknowledged: true }),
    'POST /api/exercises/starter.one/live-runs': () =>
      json(run({ status: 'queued', outcome: null, stdout: '', calls: [], total_cost_usd: 0 }), 202),
    'GET /api/live-runs/run-1': () => json(run()),
    ...routes,
  });
  render(
    <QueryWrapper client={newQueryClient()}>
      {withMode(
        mode,
        <TryLive
          exerciseId="starter.one"
          files={{ 'agent.py': 'print(1)\n' }}
          hasLiveExample={hasLiveExample}
        />,
      )}
    </QueryWrapper>,
  );
  return seen;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('TryLive', () => {
  it('is hidden while the server has live runs switched off', async () => {
    mount('professional', {}, { config: { ...CONFIG, live_runs: false, live_model: null } });
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(screen.queryByRole('button', { name: 'Try it live' })).not.toBeInTheDocument();
  });

  it('says plainly when the exercise has no live example', async () => {
    mount('professional', {}, { hasLiveExample: false });
    const button = await screen.findByRole('button', { name: 'Try it live' });
    expect(button).toBeDisabled();
    expect(button).toHaveAccessibleDescription('This exercise has no live example yet.');
  });

  it('runs the current code and shows the output, each call’s cost and the allowance', async () => {
    const seen = mount('professional');
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Try it live' }));

    const panel = screen.getByRole('region', { name: 'Try it live' });
    expect(within(panel).getByText(/on Forgeway’s model and at Forgeway’s cost/)).toBeVisible();
    expect(within(panel).getByText(/against claude-haiku-5-5/)).toBeVisible();
    expect(within(panel).getByText(/never used or asked for/)).toBeVisible();
    expect(within(panel).getByText(/Grades still come from the checks/)).toBeVisible();

    expect(await within(panel).findByText('The model said: four')).toBeVisible();
    const table = within(panel).getByRole('table', { name: 'Model calls' });
    const cells = within(table)
      .getAllByRole('cell')
      .map((cell) => cell.textContent);
    expect(cells).toEqual(
      expect.arrayContaining(['claude-haiku-5-5', '30', '4', '$0.000005', '412 ms']),
    );
    expect(within(table).getByRole('rowheader', { name: 'Total' })).toBeVisible();
    expect(within(panel).getByText(/Allowance left: \$1\.00/)).toHaveTextContent(
      'More becomes available on 4 Nov 2026 at 00:00 UTC.',
    );

    const post = seen.find((request) => request.method === 'POST');
    expect(await post?.json()).toEqual({ files: { 'agent.py': 'print(1)\n' } });
  });

  it('words the run in RPG mode too, still saying grades and keys are untouched', async () => {
    mount('rpg');
    await userEvent
      .setup()
      .click(await screen.findByRole('button', { name: 'Consult the oracle' }));
    const panel = screen.getByRole('region', { name: 'Consult the oracle' });
    expect(within(panel).getByText(/The guild pays the toll/)).toBeVisible();
    expect(within(panel).getByText(/conquered only by the trial/)).toBeVisible();
  });

  it('tells the learner at the cap when it resets, never failing silently', async () => {
    mount('professional', {
      'POST /api/exercises/starter.one/live-runs': () =>
        json(
          {
            title: 'Too many requests',
            status: 429,
            code: 'live-cap',
            detail: 'server wording',
            scope: 'day',
            resets_at: '2026-11-04T00:00:00+00:00',
          },
          429,
        ),
    });
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Try it live' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Today’s share of your live-run allowance is used up. More becomes available on 4 Nov 2026 at 00:00 UTC.',
    );
  });

  it.each([
    ['trial', 'Your trial’s live-run allowance is used up.'],
    ['time', 'Today’s live-run time is used up.'],
  ])('names a %s cap in the learner’s words', (scope, words) => {
    const error = toApiError(429, { code: 'live-cap', detail: 'server wording', scope });
    expect(problemMessage(error, LEXICONS.professional)).toContain(words);
  });

  it('shows why a run was stopped', async () => {
    mount('professional', {
      'GET /api/live-runs/run-1': () =>
        json(
          run({
            outcome: 'timed-out',
            message: 'Your program ran past the 60 seconds a live run may take, so it was stopped.',
            calls: [],
          }),
        ),
    });
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Try it live' }));
    expect(await screen.findByText(/ran past the 60 seconds a live run may take/)).toBeVisible();
  });
});

describe('TryLive data notice', () => {
  it('asks for the notice to be acknowledged before the first run, then runs', async () => {
    const seen = mount('professional', {
      'GET /api/live/notice': () => json({ version: 'v1', text: NOTICE, acknowledged: false }),
      'POST /api/live/notice': () => json({ version: 'v1', text: NOTICE, acknowledged: true }),
    });
    const user = userEvent.setup();
    const button = await screen.findByRole('button', { name: 'Try it live' });
    await new Promise((resolve) => setTimeout(resolve, 20));
    await user.click(button);
    const panel = screen.getByRole('region', { name: 'Try it live' });
    expect(
      within(panel).getByRole('heading', { name: 'Before your first live run' }),
    ).toBeVisible();
    expect(within(panel).getByText(NOTICE)).toBeVisible();
    expect(seen.some((r) => r.method === 'POST' && r.url.endsWith('/live-runs'))).toBe(false);

    await user.click(within(panel).getByRole('button', { name: 'I understand, run it' }));
    expect(await within(panel).findByText('The model said: four')).toBeVisible();
    const ack = seen.find((r) => r.method === 'POST' && r.url.endsWith('/api/live/notice'));
    expect(await ack?.json()).toEqual({ version: 'v1' });
  });
});

describe('formatUsd', () => {
  it('keeps enough places for fractions of a cent', () => {
    expect(formatUsd(0)).toBe('$0.00');
    expect(formatUsd(0.000005)).toBe('$0.000005');
    expect(formatUsd(1.5)).toBe('$1.50');
  });
});
