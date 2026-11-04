import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { Mode } from '../../api/types';
import { json, stubApi } from '../../test/fixtures';
import { newQueryClient, QueryWrapper, withMode } from '../../test/render';
import { LIVE_MODE_GUIDE, RunLocally, TOOLKIT_REFERENCE, ToolkitReferenceLink } from './RunLocally';

const WHEEL = 'https://forgeway.dev/kit/forgeway_kit-2.0.0-py3-none-any.whl';

function mount(mode: Mode, wheel: string | null = WHEEL) {
  const seen = stubApi({
    'GET /api/config': () =>
      json({ turnstile_site_key: null, free_exercises_per_branch: 3, kit_wheel_url: wheel }),
  });
  render(
    <QueryWrapper client={newQueryClient()}>
      {withMode(mode, <RunLocally exerciseId="starter.first-completion" />)}
    </QueryWrapper>,
  );
  return seen;
}

/** Click the download link without jsdom trying to navigate. */
async function download(name: string) {
  const link = screen.getByRole('link', { name });
  link.addEventListener('click', (event) => {
    event.preventDefault();
  });
  await userEvent.setup().click(link);
  return link;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('RunLocally', () => {
  it('downloads the exercise zip and asks nothing of the server until clicked', () => {
    const seen = mount('professional');
    const link = screen.getByRole('link', { name: 'Run locally' });
    expect(link).toHaveAttribute('href', '/api/exercises/starter.first-completion/download');
    expect(link).toHaveAttribute('download');
    expect(screen.queryByRole('region')).not.toBeInTheDocument();
    expect(seen).toHaveLength(0);
  });

  it('then says how to install the kit, which variables to set and that the key stays local', async () => {
    mount('professional');
    await download('Run locally');

    const panel = screen.getByRole('region', { name: 'Run locally' });
    expect(panel).toHaveFocus();
    expect(await screen.findByText(`pip install "${WHEEL}"`)).toBeVisible();
    for (const name of [
      'FORGEWAY_LIVE',
      'ANTHROPIC_API_KEY or OPENAI_API_KEY',
      'FORGEWAY_MODEL',
      'FORGEWAY_BASE_URL',
    ]) {
      expect(screen.getByText(name)).toBeVisible();
    }
    expect(panel).toHaveTextContent('Your key never leaves your machine');
    expect(panel).toHaveTextContent('Grades still come from the checks here');
    const guide = screen.getByRole('link', { name: /live mode guide/ });
    expect(guide).toHaveAttribute('href', LIVE_MODE_GUIDE);
    expect(guide).toHaveAttribute('target', '_blank');
    expect(panel.querySelector('input')).toBeNull(); // nowhere to type a key
  });

  it('closes back to the link', async () => {
    mount('professional');
    const link = await download('Run locally');
    await userEvent.setup().click(screen.getByRole('button', { name: 'Close' }));
    expect(screen.queryByRole('region')).not.toBeInTheDocument();
    expect(link).toHaveFocus();
  });

  it('speaks the mode, and points to the README where no wheel is built', async () => {
    mount('rpg', null);
    await download('Take it to your own forge');
    const panel = screen.getByRole('region', { name: 'Take it to your own forge' });
    expect(await screen.findByText(/The README in the download has the command/)).toBeVisible();
    expect(panel).toHaveTextContent('conquered only by the trial here');
  });
});

describe('ToolkitReferenceLink', () => {
  it.each([
    ['professional', /Toolkit reference/],
    ['rpg', /Consult the toolkit/],
  ] as const)('links to the reference in %s mode', (mode, name) => {
    render(withMode(mode, <ToolkitReferenceLink />));
    expect(screen.getByRole('link', { name })).toHaveAttribute('href', TOOLKIT_REFERENCE);
  });
});
