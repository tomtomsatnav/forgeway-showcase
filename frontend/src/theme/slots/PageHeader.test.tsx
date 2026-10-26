import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { BOSS_FLAVOUR } from '../../test/fixtures';
import { renderInRouter, withMode } from '../../test/render';
import { PageHeader } from '.';

const CAPSTONE = 'retrieval.search-service';
const TITLE = 'Build a search service';

describe('capstone workspace header', () => {
  it('frames a capstone project in professional mode, with a note and the real title', async () => {
    await renderInRouter(
      withMode(
        'professional',
        <PageHeader title={TITLE} exerciseId={CAPSTONE} capstone summary="Capstone · 350 XP" />,
      ),
      BOSS_FLAVOUR,
    );

    expect(screen.getByText('Capstone project')).toBeVisible();
    expect(screen.getByRole('heading', { level: 1, name: TITLE })).toBeVisible();
    expect(screen.getByText('This project draws on the whole track.')).toBeVisible();
    // Professional mode never shows flavour.
    expect(screen.queryByText('The Index Warden')).not.toBeInTheDocument();
  });

  it('shows the boss name, epithet and lore above the real title in RPG mode', async () => {
    await renderInRouter(
      withMode('rpg', <PageHeader title={TITLE} exerciseId={CAPSTONE} capstone />),
      BOSS_FLAVOUR,
    );

    const name = screen.getByRole('heading', { level: 1, name: 'The Index Warden' });
    const epithet = screen.getByText('Keeper of every shelf');
    const lore = screen.getByText('It has read everything and forgiven nothing.');
    const title = screen.getByText(TITLE);
    expect(title).toBeVisible();
    expect(screen.getByText('Boss challenge')).toBeVisible();
    const order = [name, epithet, lore, title].map((node) => node.compareDocumentPosition(title));
    // Each of the first three precedes the title; the title is its own reference.
    expect(order.slice(0, 3).every((position) => position & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(
      true,
    );
  });

  it('keeps the real title when the boss has no flavour', async () => {
    await renderInRouter(
      withMode('rpg', <PageHeader title={TITLE} exerciseId={CAPSTONE} capstone />),
    );

    expect(screen.getByRole('heading', { level: 1, name: TITLE })).toBeVisible();
    expect(screen.getByText('Boss challenge')).toBeVisible();
  });

  it.each(['professional', 'rpg'] as const)(
    'leaves an ordinary exercise unframed (%s)',
    async (mode) => {
      await renderInRouter(
        withMode(mode, <PageHeader title="Fixed-size chunking" exerciseId="retrieval.chunking" />),
        BOSS_FLAVOUR,
      );

      expect(screen.queryByText(/Capstone project|Boss challenge/)).not.toBeInTheDocument();
      expect(screen.queryByText(/draws on/)).not.toBeInTheDocument();
    },
  );
});

describe('guided project header', () => {
  it.each([
    ['professional', 'Guided project · Research assistant'],
    ['rpg', 'Expedition · Research assistant'],
  ] as const)('labels a milestone with its project in %s mode', async (mode, label) => {
    await renderInRouter(
      withMode(
        mode,
        <PageHeader
          title="Second milestone"
          exerciseId="project-research.second"
          project="Research assistant"
        />,
      ),
    );

    expect(screen.getByText(label)).toBeVisible();
    expect(screen.getByRole('heading', { level: 1, name: 'Second milestone' })).toBeVisible();
  });
});
