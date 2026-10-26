import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { ExerciseDetail, Mode } from '../../api/types';
import { json, problem, stubApi } from '../../test/fixtures';
import { renderInRouter, withMode } from '../../test/render';
import { WorkspacePage } from './WorkspacePage';

const EXERCISE: ExerciseDetail = {
  id: 'starter.first-completion',
  branch: 'starter',
  title: 'Your first completion',
  tier: 'beginner',
  xp: 50,
  brief: '# Your first completion\n\nCall the model.',
  status: 'available',
  prerequisites: [],
  pro: false,
  entitled: true,
  editable: ['ask.py'],
  files: { 'ask.py': 'def ask():\n    pass\n' },
  files_source: 'starter',
  carried_from: null,
  checks: [],
  hints_total: 2,
  hints_revealed: [],
  recent_attempts: [],
};

const ME = { id: 'u1', email: 'a@example.com', plan: 'free', csrf_token: 'x' };

afterEach(() => {
  vi.unstubAllGlobals();
});

function mount(mode: Mode, me: Record<string, unknown>, attempt?: () => Response) {
  stubApi({
    'GET /api/auth/me': () => json({ ...ME, ...me }),
    'GET /api/exercises/starter.first-completion': () => json(EXERCISE),
    'GET /api/map': () => json({ branches: [] }),
    'POST /api/exercises/starter.first-completion/attempts': attempt ?? (() => json({}, 500)),
  });
  return renderInRouter(
    withMode(mode, <WorkspacePage />),
    undefined,
    '/exercises/starter.first-completion',
  );
}

describe('workspace Run button', () => {
  it.each([
    ['professional', 'Run checks', 'Verify your email address to run checks.'],
    ['rpg', 'Attempt the quest', 'Confirm your messenger address to attempt quests.'],
  ] as const)(
    'is disabled with its reason attached while the email is unverified (%s)',
    async (mode, name, reason) => {
      await mount(mode, { email_verified: false });

      const run = await screen.findByRole('button', { name });
      await vi.waitFor(() => {
        expect(run).toBeDisabled();
      });
      expect(run).toHaveAccessibleDescription(reason);
      expect(screen.getByText(reason)).toBeVisible();
    },
  );

  it('is open to a verified learner', async () => {
    await mount('professional', { email_verified: true });
    expect(await screen.findByRole('button', { name: 'Run checks' })).toBeEnabled();
  });

  it('leaves the hint button open while the email is unverified', async () => {
    await mount('professional', { email_verified: false });
    await vi.waitFor(() => {
      expect(screen.getByRole('button', { name: 'Run checks' })).toBeDisabled();
    });
    expect(screen.getByRole('button', { name: /Reveal a hint/ })).toBeEnabled();
  });

  it.each([
    [
      'professional',
      'Run checks',
      429,
      'attempt-daily-cap',
      { limit: 20 },
      'Today’s 20 graded attempts are used up. More free up as attempts from 24 hours ago age out.',
    ],
    [
      'rpg',
      'Attempt the quest',
      503,
      'busy',
      {},
      'The judges’ hall is full. Your code is safe; try again in a minute.',
    ],
  ] as const)(
    'shows a refused attempt beside the button, in the mode’s voice (%s)',
    async (mode, name, status, code, extra, message) => {
      const refuse = () =>
        json({ title: 'Problem', status, detail: 'Server words.', code, ...extra }, status);
      const user = userEvent.setup();
      await mount(mode, { email_verified: true }, refuse);

      const run = await screen.findByRole('button', { name });
      await user.click(run);

      const alert = await screen.findByRole('alert');
      expect(alert).toHaveTextContent(message);
      // Next to the Run button, not down in the Results section.
      expect(alert.parentElement).toBe(run.parentElement);
      expect(screen.getByRole('region', { name: 'Results' })).not.toContainElement(alert);
    },
  );

  it('keeps the server wording for a code it does not map', async () => {
    const user = userEvent.setup();
    await mount('professional', { email_verified: true }, () =>
      problem(409, 'Server words.', 'something-new'),
    );

    await user.click(await screen.findByRole('button', { name: 'Run checks' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Server words.');
  });
});
