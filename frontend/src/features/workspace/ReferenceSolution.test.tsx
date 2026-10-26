import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { Mode } from '../../api/types';
import { json, problem, stubApi } from '../../test/fixtures';
import { newQueryClient, withMode } from '../../test/render';
import { ReferenceSolution } from './ReferenceSolution';

const SOLUTION = {
  files: { 'ask.py': 'def ask(client, question):\n    return "ok"\n' },
  notes: 'Keep the **system prompt** short.',
};

const mount = (mode: Mode, passed: boolean) =>
  render(
    <QueryClientProvider client={newQueryClient()}>
      {withMode(mode, <ReferenceSolution exerciseId="starter.first-completion" passed={passed} />)}
    </QueryClientProvider>,
  );

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('ReferenceSolution', () => {
  it('does not ask for the solution before the exercise is passed', () => {
    const seen = stubApi({});
    mount('professional', false);

    expect(seen).toHaveLength(0);
    expect(screen.queryByText(/reference solution/i)).not.toBeInTheDocument();
  });

  it.each([
    ['professional', 'Reference solution'],
    ['rpg', "Master's copy"],
  ] as const)(
    'shows the files and notes in a disclosure when entitled (%s)',
    async (mode, name) => {
      stubApi({
        'GET /api/exercises/starter.first-completion/reference-solution': () => json(SOLUTION),
      });
      mount(mode, true);

      const summary = await screen.findByText(name);
      const details = summary.closest('details');
      expect(details).not.toHaveAttribute('open');

      await userEvent.setup().click(summary);

      expect(details).toHaveAttribute('open');
      expect(screen.getByRole('heading', { name: 'ask.py' })).toBeVisible();
      expect(screen.getByText(/return "ok"/)).toBeVisible();
      expect(screen.getByText('system prompt').tagName).toBe('STRONG');
    },
  );

  it.each([
    [
      'professional',
      'A competency unlocks reference solutions for this track. Acquire Guarded builder to unlock it.',
    ],
    ['rpg', "A talent unlocks master's copies for this zone. Learn Guarded builder to unlock it."],
  ] as const)("words the 403 hint in the mode's own vocabulary (%s)", async (mode, hint) => {
    stubApi({
      'GET /api/exercises/starter.first-completion/reference-solution': () =>
        json(
          {
            title: 'Forbidden',
            status: 403,
            detail: 'A talent unlocks reference solutions for this branch. Take Guarded builder.',
            code: 'forbidden',
            talents: [{ id: 'guarded', title: 'Guarded builder' }],
          },
          403,
        ),
    });
    mount(mode, true);

    expect(await screen.findByText(hint, { exact: false })).toBeVisible();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(document.querySelector('details')).toBeNull();
  });

  it.each([
    [
      'professional',
      'A competency unlocks reference solutions for this track. Acquire Hybrid ranking as a Retrieval specialist to unlock it.',
    ],
    [
      'rpg',
      "A talent unlocks master's copies for this zone. Learn Hybrid ranking as a Loremaster to unlock it.",
    ],
  ] as const)('names the specialisation of a talent on another path (%s)', async (mode, hint) => {
    stubApi({
      'GET /api/exercises/starter.first-completion/reference-solution': () =>
        json(
          {
            title: 'Forbidden',
            status: 403,
            detail: 'This reference solution is locked. Take Hybrid ranking to unlock it.',
            code: 'forbidden',
            talents: [{ id: 'hybrid', title: 'Hybrid ranking', path: 'retrieval' }],
          },
          403,
        ),
    });
    mount(mode, true);

    expect(await screen.findByText(hint, { exact: false })).toBeVisible();
    expect(screen.queryByText(/This reference solution is locked/)).not.toBeInTheDocument();
  });

  it('words the lock in the mode, never with the server detail, when no talent is named', async () => {
    stubApi({
      'GET /api/exercises/starter.first-completion/reference-solution': () =>
        problem(403, 'A talent unlocks reference solutions for this branch.', 'forbidden'),
    });
    mount('professional', true);

    expect(
      await screen.findByText('A competency unlocks reference solutions for this track.', {
        exact: false,
      }),
    ).toBeVisible();
    expect(screen.queryByText(/this branch/)).not.toBeInTheDocument();
  });

  it('shows any other failure as an alert', async () => {
    stubApi({
      'GET /api/exercises/starter.first-completion/reference-solution': () =>
        problem(500, 'The solution store is down.', 'server'),
    });
    mount('professional', true);

    expect(await screen.findByRole('alert')).toHaveTextContent('The solution store is down.');
  });
});
