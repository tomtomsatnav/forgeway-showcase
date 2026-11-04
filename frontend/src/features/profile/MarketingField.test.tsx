import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { json, stubApi } from '../../test/fixtures';
import { renderInRouter, withMode } from '../../test/render';
import { MarketingField } from './MarketingField';

const ME = {
  id: 'u1',
  email: 'a@example.com',
  email_verified: true,
  pending_email: null,
  display_name: 'A',
  plan: 'pro',
  csrf_token: 'csrf',
  terms_current: true,
  profile: { mode: 'professional', colour_scheme: 'system', marketing_opt_out: false },
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('the marketing preference', () => {
  it('shows offers as on unless refused, and turning them off saves the opt-out', async () => {
    const seen = stubApi({
      'GET /api/auth/me': () => json(ME),
      'PATCH /api/auth/profile': () =>
        json({ ...ME, profile: { ...ME.profile, marketing_opt_out: true } }),
    });
    await renderInRouter(withMode('professional', <MarketingField />));

    const box = await screen.findByRole('checkbox', {
      name: 'Send me emails about Forgeway offers',
    });
    expect(box).toBeChecked();
    await userEvent.click(box);

    await waitFor(() => {
      expect(box).not.toBeChecked();
    });
    const patch = seen.find((request) => request.method === 'PATCH');
    expect(await patch?.json()).toEqual({ marketing_opt_out: true });
  });
});
