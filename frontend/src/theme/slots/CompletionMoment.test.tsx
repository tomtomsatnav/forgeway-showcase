import { render, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { Mode } from '../../api/types';
import { BOSS_FLAVOUR, progression } from '../../test/fixtures';
import { renderInRouter, withMode } from '../../test/render';
import { CompletionMoment } from '.';
import { ProgressionNews } from './ProgressionNews';

const NEWS = progression({
  badges_awarded: [
    { id: 'first-steps', title: 'First steps', description: 'Passed your first exercise.' },
  ],
  talent_points_gained: 1,
  streak: { current: 3, longest: 3 },
});

const mount = (mode: Mode, value = NEWS) =>
  renderInRouter(
    withMode(
      mode,
      <CompletionMoment
        progression={value}
        unlocked={[]}
        onDismiss={() => undefined}
        levelFraction={0.4}
      />,
    ),
  );

describe('completion moment news', () => {
  it('lists the badge, talent point and streak in the professional strip', async () => {
    await mount('professional');

    // The strip fades in from opacity 0, so visibility is timing-dependent under load: assert
    // that each item is rendered with its text, and that the list holds exactly these three.
    expect(await screen.findByText('Passed · +60 XP · Level 2')).toBeInTheDocument();
    const news = screen.getByRole('list', { name: 'What else changed' });
    expect(
      within(news)
        .getAllByRole('listitem')
        .map((item) => item.textContent),
    ).toEqual([
      'Achievement earned: First steps · Passed your first exercise.',
      '+1 competency point',
      '3-day streak',
    ]);
  });

  it('lists the same news in the RPG seal', async () => {
    await mount('rpg');

    const dialog = await screen.findByRole('dialog');
    expect(dialog).toHaveTextContent('Badge won: First steps');
    expect(dialog).toHaveTextContent('+1 talent point');
    expect(dialog).toHaveTextContent('Learning streak: 3 days');
  });

  it.each([
    ['professional', 'Certificate earned: Foundations track'],
    ['rpg', 'The seal is set. Certificate earned: Foundations track'],
  ] as const)('announces a certificate and links to the profile (%s)', async (mode, text) => {
    await mount(
      mode,
      progression({
        certificates_issued: [
          {
            id: 'cert_1',
            branch_id: 'starter',
            branch_title: 'Foundations',
            includes_capstone: false,
          },
        ],
      }),
    );

    expect(await screen.findByText(text)).toBeInTheDocument();
    const link = screen.getByRole('link', {
      name: mode === 'rpg' ? 'See your seals of completion' : 'View your certificates',
    });
    expect(link).toHaveAttribute('href', '/profile#certificates');
  });

  it.each(['professional', 'rpg'] as const)(
    'adds nothing when nothing changed (%s)',
    async (mode) => {
      await mount(mode, progression());

      await screen.findByRole(mode === 'rpg' ? 'dialog' : 'status');
      expect(screen.queryByRole('list', { name: 'What else changed' })).not.toBeInTheDocument();
    },
  );
});

const CAPSTONE = { exerciseId: 'retrieval.search-service', title: 'Build a search service' };

describe('capstone completion', () => {
  it('says "Capstone complete" in the professional strip', async () => {
    await renderInRouter(
      withMode(
        'professional',
        <CompletionMoment
          progression={progression({ xp_awarded: 350, level_after: 5 })}
          unlocked={[]}
          onDismiss={() => undefined}
          levelFraction={0.4}
          capstone={CAPSTONE}
        />,
      ),
      BOSS_FLAVOUR,
    );

    expect(await screen.findByText('Capstone complete · +350 XP · Level 5')).toBeInTheDocument();
    expect(screen.queryByText(/Passed/)).not.toBeInTheDocument();
    expect(screen.queryByText('The Index Warden')).not.toBeInTheDocument();
  });

  it('presses a boss-defeated seal in RPG mode, with the boss name and its defeat line', async () => {
    await renderInRouter(
      withMode(
        'rpg',
        <CompletionMoment
          progression={progression({ xp_awarded: 350, level_after: 5 })}
          unlocked={[]}
          onDismiss={() => undefined}
          levelFraction={0.4}
          capstone={CAPSTONE}
        />,
      ),
      BOSS_FLAVOUR,
    );

    const dialog = await screen.findByRole('dialog', { name: 'Boss defeated' });
    expect(dialog).toHaveTextContent('The Index Warden');
    expect(dialog).toHaveTextContent('The Warden lowers its lantern; the shelves fall quiet.');
    expect(dialog).toHaveTextContent('Build a search service');
    // The XP counts up to its total.
    await waitFor(() => {
      expect(dialog).toHaveTextContent('+350 XP');
    });
    // The tower is pressed into the wax in place of the level number, which stays readable.
    expect(dialog.querySelector('svg text')).toBeNull();
    expect(dialog).toHaveTextContent('Level 5');
  });

  it('keeps the ordinary seal for a pass that is not a capstone', async () => {
    await mount('rpg', progression());

    const dialog = await screen.findByRole('dialog', { name: 'Quest conquered' });
    expect(dialog.querySelector('svg text')).not.toBeNull();
    expect(dialog).not.toHaveTextContent('defeated');
  });

  it('adds no looping motion', async () => {
    await renderInRouter(
      withMode(
        'rpg',
        <CompletionMoment
          progression={progression()}
          unlocked={[]}
          onDismiss={() => undefined}
          levelFraction={0.4}
          capstone={CAPSTONE}
        />,
      ),
      BOSS_FLAVOUR,
    );

    const dialog = await screen.findByRole('dialog');
    expect(dialog.innerHTML).not.toMatch(/repeat|infinite|animate-/);
  });
});

describe('certificate news', () => {
  const issued = progression({
    certificates_issued: [
      { id: 'cert_1', branch_id: 'retrieval', branch_title: 'Retrieval', includes_capstone: true },
    ],
  });

  it.each([
    ['professional', 'Certificate earned: Retrieval track, including its capstone project'],
    ['rpg', 'The seal is set. Certificate earned: Retrieval track, including its capstone project'],
  ] as const)('says the track included its capstone project (%s)', async (mode, text) => {
    await renderInRouter(
      withMode(
        mode,
        <CompletionMoment
          progression={issued}
          unlocked={[]}
          onDismiss={() => undefined}
          levelFraction={0.4}
        />,
      ),
    );

    expect(await screen.findByText(text)).toBeInTheDocument();
  });

  it('says nothing about a capstone for a track without one', async () => {
    await renderInRouter(
      withMode(
        'professional',
        <ProgressionNews
          progression={progression({
            certificates_issued: [
              {
                id: 'cert_1',
                branch_id: 'retrieval',
                branch_title: 'Retrieval',
                includes_capstone: false,
              },
            ],
          })}
        />,
      ),
    );

    expect(screen.getByText('Certificate earned: Retrieval track')).toBeInTheDocument();
    expect(screen.queryByText(/capstone/)).not.toBeInTheDocument();
  });
});

describe('ProgressionNews', () => {
  it('pluralises points and badges and skips a streak of zero', () => {
    render(
      withMode(
        'professional',
        <ProgressionNews
          progression={progression({
            badges_awarded: [
              { id: 'a', title: 'A', description: 'First.' },
              { id: 'b', title: 'B', description: 'Second.' },
            ],
            talent_points_gained: 2,
            streak: { current: 0, longest: 4 },
          })}
        />,
      ),
    );

    expect(screen.getAllByRole('listitem')).toHaveLength(3);
    expect(screen.getByText('+2 competency points')).toBeVisible();
    expect(screen.queryByText(/streak/)).not.toBeInTheDocument();
  });
});
