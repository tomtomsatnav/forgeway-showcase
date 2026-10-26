import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { BOSS_FLAVOUR, capstoneBranch } from '../../test/fixtures';
import { renderInRouter, withMode } from '../../test/render';
import { BranchOverview } from '.';

const ZONE = '/?zone=retrieval';

const renderZone = (status: 'locked' | 'available' | 'passed', flavour = BOSS_FLAVOUR) =>
  renderInRouter(
    withMode('rpg', <BranchOverview branches={[capstoneBranch(status)]} />),
    flavour,
    ZONE,
  );

describe('the lair (RPG)', () => {
  it.each([
    ['locked', 'Sealed'],
    ['available', 'Awaiting'],
    ['passed', 'Defeated'],
  ] as const)(
    'is the last waypoint, with the boss, the real title and "%s" in words',
    async (status, word) => {
      await renderZone(status);

      const zone = await screen.findByRole('region', { name: 'The Sunken Archive' });
      const links = within(zone).getAllByRole('link');
      const lair = links[links.length - 1];
      expect(lair).toHaveAttribute('href', '/exercises/retrieval.search-service');
      expect(lair).toHaveAccessibleName(expect.stringContaining('The Index Warden'));
      expect(lair).toHaveAccessibleName(expect.stringContaining('Build a search service'));
      expect(lair).toHaveAccessibleName(expect.stringContaining(`Boss · 350 XP · ${word}`));
      expect(lair).toHaveAttribute('data-lair', status);
      // Visible text, not only the accessible name.
      expect(within(zone).getByText('Build a search service')).toBeInTheDocument();
      expect(within(zone).getByText('Boss challenge')).toBeInTheDocument();
    },
  );

  it('tells the three states apart by shape as well as by word', async () => {
    const glyphs = new Set<string>();
    for (const status of ['locked', 'available', 'passed'] as const) {
      const { container, unmount } = await renderZone(status);
      await screen.findByRole('region', { name: 'The Sunken Archive' });
      const lair = container.querySelector(`[data-lair="${status}"]`);
      // The badge on the lair: a padlock (rect), an open dot (circle) or a tick (path).
      const badge = lair?.querySelector('g > g:last-of-type');
      glyphs.add(
        [badge?.querySelector('rect'), badge?.querySelector('path[stroke-linecap]')]
          .map((node) => (node ? node.tagName : '-'))
          .join(':') + String(badge?.querySelectorAll('circle').length),
      );
      unmount();
    }
    expect(glyphs.size).toBe(3);
  });

  it('draws the lair larger than a waypoint', async () => {
    const { container } = await renderZone('available');
    await screen.findByRole('region', { name: 'The Sunken Archive' });

    const radii = [...container.querySelectorAll('a circle')].map((c) =>
      Number(c.getAttribute('r')),
    );
    expect(Math.max(...radii)).toBeGreaterThan(20);
    const lair = container.querySelector('[data-lair]');
    expect(lair?.querySelector('circle[r="27"]')).not.toBeNull();
  });

  it('falls back to the real title, still framed as a boss challenge, with no boss in the flavour', async () => {
    await renderZone('locked', { ...BOSS_FLAVOUR, bosses: {} });

    const zone = await screen.findByRole('region', { name: 'The Sunken Archive' });
    const lair = within(zone).getAllByRole('link').at(-1);
    expect(lair).toHaveAccessibleName(expect.stringContaining('Build a search service'));
    expect(lair).toHaveAccessibleName(expect.stringContaining('Sealed'));
    expect(within(zone).getByText('Boss challenge')).toBeInTheDocument();
  });

  it('leaves ordinary waypoints as they were', async () => {
    const { container } = await renderZone('locked');
    await screen.findByRole('region', { name: 'The Sunken Archive' });

    expect(container.querySelectorAll('[data-lair]')).toHaveLength(1);
    expect(screen.getByRole('link', { name: /Fixed-size chunking/ })).toHaveAccessibleName(
      expect.stringContaining('Novice · 75 XP · Conquered'),
    );
  });
});

describe('the capstone row (professional)', () => {
  it('is framed as a capstone project with its own mark, and keeps the real title', async () => {
    await renderInRouter(
      withMode('professional', <BranchOverview branches={[capstoneBranch()]} />),
    );

    const track = await screen.findByRole('region', { name: 'Retrieval' });
    expect(within(track).getByText('Capstone project')).toBeInTheDocument();
    const row = within(track).getByRole('link', { name: /Build a search service/ });
    expect(row).toHaveTextContent('Capstone');
    expect(row).toHaveTextContent('Locked');
    expect(row.closest('li')).toHaveClass('border-tier-capstone');
    expect(row.querySelector('svg[viewBox="0 0 12 12"]')).not.toBeNull();
    // Only the capstone is framed.
    expect(within(track).getAllByText('Capstone project')).toHaveLength(1);
  });
});
