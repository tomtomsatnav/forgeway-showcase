import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { json, stubApi } from '../../test/fixtures';
import { renderInRouter, withMode } from '../../test/render';
import { NewToPythonField } from './NewToPythonField';

const ME = {
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
    new_to_python: false,
  },
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the I'm new to Python toggle", () => {
  it('starts as saved and saves a change at once', async () => {
    const seen = stubApi({
      'GET /api/auth/me': () => json(ME),
      'PATCH /api/auth/profile': () =>
        json({ ...ME, profile: { ...ME.profile, new_to_python: true } }),
    });
    await renderInRouter(withMode('professional', <NewToPythonField />));

    const box = await screen.findByRole('checkbox', { name: "I'm new to Python" });
    expect(box).not.toBeChecked();
    await userEvent.click(box);

    await waitFor(() => {
      expect(box).toBeChecked();
    });
    const patch = seen.find((request) => request.method === 'PATCH');
    expect(await patch?.json()).toEqual({ new_to_python: true });
  });

  it('points at the primer in the words of the mode', async () => {
    stubApi({ 'GET /api/auth/me': () => json(ME) });
    await renderInRouter(withMode('rpg', <NewToPythonField />));

    await screen.findByRole('checkbox', { name: "I'm new to Python" });
    expect(screen.getByText(/Each quest that has them/)).toBeVisible();
    expect(screen.getByRole('link', { name: 'Python for this course' })).toHaveAttribute(
      'href',
      '/?zone=python-primer',
    );
  });
});
