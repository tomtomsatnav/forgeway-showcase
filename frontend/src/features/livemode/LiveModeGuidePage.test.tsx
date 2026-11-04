import { screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { renderInRouter, withMode } from '../../test/render';
import { LIVE_MODE_GUIDE_SOURCE, LiveModeGuidePage } from './LiveModeGuidePage';

const GUIDE =
  '# Live mode: run your code\n\n## 1. Download the exercise\n\nChoose **Run locally**.\n';

function stubGuide(status = 200) {
  const fetchMock = vi.fn(() => Promise.resolve(new Response(GUIDE, { status })));
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('LiveModeGuidePage', () => {
  it('renders the guide from the server under the page title', async () => {
    const fetchMock = stubGuide();
    await renderInRouter(withMode('professional', <LiveModeGuidePage />));

    expect(screen.getByRole('heading', { level: 1, name: 'Live mode' })).toBeVisible();
    expect(
      await screen.findByRole('heading', { level: 2, name: '1. Download the exercise' }),
    ).toBeVisible();
    expect(screen.queryByText('Live mode: run your code')).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(LIVE_MODE_GUIDE_SOURCE);
  });

  it('says so when the guide cannot be loaded', async () => {
    stubGuide(404);
    await renderInRouter(withMode('rpg', <LiveModeGuidePage />));

    expect(await screen.findByRole('alert')).toHaveTextContent('could not be loaded');
  });
});
