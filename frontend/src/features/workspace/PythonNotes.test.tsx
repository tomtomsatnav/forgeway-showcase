import { screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { Mode } from '../../api/types';
import { json, stubApi } from '../../test/fixtures';
import { renderInRouter, withMode } from '../../test/render';
import { PythonNotes } from './PythonNotes';

const NOTES = '### `@dataclass(frozen=True)` makes an immutable record\n\nSo fields cannot change.';

const me = (newToPython: boolean) => ({
  id: 'u1',
  email: 'a@example.com',
  email_verified: true,
  pending_email: null,
  display_name: 'A',
  plan: 'free',
  csrf_token: 'csrf',
  terms_current: true,
  profile: {
    mode: 'professional',
    colour_scheme: 'system',
    marketing_opt_out: false,
    new_to_python: newToPython,
  },
});

afterEach(() => {
  vi.unstubAllGlobals();
});

async function render(mode: Mode, newToPython: boolean, notes: string) {
  const seen = stubApi({ 'GET /api/auth/me': () => json(me(newToPython)) });
  await renderInRouter(withMode(mode, <PythonNotes notes={notes} />));
  return seen;
}

describe("the Python you'll need panel", () => {
  it('shows the notes and points at the primer when the toggle is on', async () => {
    await render('professional', true, NOTES);

    const panel = await screen.findByRole('region', { name: "Python you'll need" });
    expect(
      within(panel).getByRole('heading', { level: 3, name: /makes an immutable record/ }),
    ).toBeVisible();
    expect(within(panel).getByRole('link', { name: 'Python for this course' })).toHaveAttribute(
      'href',
      '/#track-python-primer',
    );
  });

  it('points at the primer zone in RPG mode', async () => {
    await render('rpg', true, NOTES);

    const panel = await screen.findByRole('region', { name: "Python you'll need" });
    expect(panel).toHaveTextContent('walk the free primer zone');
    expect(within(panel).getByRole('link', { name: 'Python for this course' })).toHaveAttribute(
      'href',
      '/?zone=python-primer',
    );
  });

  it('stays away when the toggle is off', async () => {
    const seen = await render('professional', false, NOTES);

    await vi.waitFor(() => {
      expect(seen.length).toBeGreaterThan(0);
    });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.queryByRole('heading', { name: "Python you'll need" })).not.toBeInTheDocument();
    expect(screen.queryByText(/immutable record/)).not.toBeInTheDocument();
  });

  it('stays away when the exercise has no notes, toggle or no toggle', async () => {
    const seen = await render('professional', true, '');

    await vi.waitFor(() => {
      expect(seen.length).toBeGreaterThan(0);
    });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.queryByRole('heading', { name: "Python you'll need" })).not.toBeInTheDocument();
  });
});
