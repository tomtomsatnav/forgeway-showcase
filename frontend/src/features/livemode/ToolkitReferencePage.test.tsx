import { screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { renderInRouter, withMode } from '../../test/render';
import { TOOLKIT_REFERENCE_SOURCE, ToolkitReferencePage } from './ToolkitReferencePage';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('ToolkitReferencePage', () => {
  it('renders the reference from the server', async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(new Response('# Toolkit reference\n\n## Tools\n\nA tool.\n')),
    );
    vi.stubGlobal('fetch', fetchMock);
    await renderInRouter(withMode('rpg', <ToolkitReferencePage />));

    expect(await screen.findByRole('heading', { level: 2, name: 'Tools' })).toBeVisible();
    expect(fetchMock).toHaveBeenCalledWith(TOOLKIT_REFERENCE_SOURCE);
  });
});
