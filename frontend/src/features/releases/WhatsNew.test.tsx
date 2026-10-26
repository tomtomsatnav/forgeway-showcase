import { screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { ReleaseList } from '../../api/types';
import { json, stubApi } from '../../test/fixtures';
import { renderInRouter, withMode } from '../../test/render';
import { WhatsNewLink } from './WhatsNewLink';
import { WhatsNewPage, formatReleaseDate } from './WhatsNewPage';

const RELEASES: ReleaseList = {
  last_seen: null,
  unread: true,
  releases: [
    {
      version: '2026.11.0',
      date: '2026-11-09',
      title: 'Second release',
      summary: 'More to do.',
      body: '## What changed\n\nA new exercise.\n',
      added: [{ id: 'retrieval.reranking', title: 'Reranking', branch: 'retrieval' }],
      updated: [],
      fixed: [{ id: 'starter.tool-use', title: 'Tool use', branch: 'starter' }],
    },
    {
      version: '2026.10.0',
      date: '2026-10-26',
      title: 'First release',
      summary: 'Everything so far.',
      body: 'Hello.\n',
      added: [],
      updated: [],
      fixed: [],
    },
  ],
};
const SEEN: ReleaseList = { ...RELEASES, unread: false, last_seen: '2026.11.0' };

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('What’s new', () => {
  it('lists releases newest first with links to the exercises they name, and marks them seen', async () => {
    const seen = stubApi({
      'GET /api/releases': () => json(RELEASES),
      'POST /api/releases/seen': () => json(SEEN),
    });
    await renderInRouter(withMode('professional', <WhatsNewPage />));

    expect(await screen.findByRole('heading', { level: 1, name: 'What’s new' })).toBeVisible();
    const titles = (await screen.findAllByRole('heading', { level: 2 })).map((h) => h.textContent);
    expect(titles).toEqual(['Second release', 'First release']);
    const second = screen.getByRole('article', { name: 'Second release' });
    const subheading = within(second).getByRole('heading', { level: 3, name: 'What changed' });
    expect(subheading).toBeVisible();
    // Hierarchy: release title (2xl) > body subheading (xl) > serif body text (lg).
    expect(within(second).getByRole('heading', { level: 2 })).toHaveClass('text-2xl');
    expect(subheading.closest('.font-reading')).toHaveClass('text-lg', '[&_h3]:text-xl');
    expect(within(second).getByRole('link', { name: 'Reranking' })).toHaveAttribute(
      'href',
      '/exercises/retrieval.reranking',
    );
    expect(within(second).getByRole('heading', { name: 'Fixed' })).toBeVisible();
    expect(within(second).queryByRole('heading', { name: 'Updated' })).toBeNull();
    expect(within(second).getByText('Released 9 November 2026')).toBeVisible();

    await waitFor(() => {
      expect(seen.some((r) => r.method === 'POST' && r.url.endsWith('/api/releases/seen'))).toBe(
        true,
      );
    });
  });

  it('is the Chronicle in RPG mode and does not mark seen when nothing is unread', async () => {
    const seen = stubApi({ 'GET /api/releases': () => json(SEEN) });
    await renderInRouter(withMode('rpg', <WhatsNewPage />));

    expect(await screen.findByRole('heading', { level: 1, name: 'Chronicle' })).toBeVisible();
    expect(await screen.findAllByRole('heading', { name: 'New quests' })).toHaveLength(1);
    expect(screen.getByRole('heading', { name: 'Mended' })).toBeVisible();
    expect(seen.every((r) => r.method === 'GET')).toBe(true);
  });

  it('shows a dot on the header link only while a release is unread', async () => {
    stubApi({ 'GET /api/releases': () => json(RELEASES) });
    const { unmount } = await renderInRouter(withMode('professional', <WhatsNewLink />));

    const link = await screen.findByRole('link', { name: 'What’s new, new release' });
    expect(link).toHaveAttribute('href', '/whats-new');
    expect(link).toHaveAttribute('data-unread');
    unmount();
    vi.unstubAllGlobals();

    stubApi({ 'GET /api/releases': () => json(SEEN) });
    await renderInRouter(withMode('rpg', <WhatsNewLink />));
    const read = await screen.findByRole('link', { name: 'Chronicle' });
    await waitFor(() => {
      expect(read).not.toHaveAttribute('data-unread');
    });
  });

  it('formats a release day the same in every time zone', () => {
    expect(formatReleaseDate('2026-10-26')).toBe('26 October 2026');
  });
});
