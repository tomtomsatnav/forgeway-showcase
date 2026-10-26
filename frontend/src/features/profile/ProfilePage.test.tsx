import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { Mode, PathProfile, TalentTree, ThemeFlavour } from '../../api/types';
import {
  BADGES,
  CERTIFICATE,
  MAP,
  NODES,
  PATH_PROFILE,
  json,
  problem,
  stubApi,
  treeOf,
} from '../../test/fixtures';
import { renderInRouter, withMode } from '../../test/render';
import { ProfilePage } from './ProfilePage';

const flavour: ThemeFlavour = {
  branches: {},
  quests: {},
  bosses: {},
  paths: {
    retrieval: { name: 'Loremaster', epithet: 'Keeper of the Deepstacks' },
    generalist: { name: 'Wayfarer', epithet: 'Walks every road' },
  },
};

function api(overrides: Record<string, () => Response> = {}) {
  return stubApi({
    'GET /api/map': () => json(MAP),
    'GET /api/profile': () => json(PATH_PROFILE),
    'GET /api/talents': () => json(treeOf()),
    'GET /api/badges': () => json({ badges: BADGES }),
    'GET /api/certificates': () => json({ certificates: [] }),
    ...overrides,
  });
}

const mount = (mode: Mode) => renderInRouter(withMode(mode, <ProfilePage />), flavour);

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('profile page', () => {
  it('is the profile in professional mode, with level, path, streak, titles and badges', async () => {
    api();
    await mount('professional');

    expect(await screen.findByRole('heading', { level: 1, name: 'Profile' })).toBeVisible();
    // The level is named once, in the summary; the rule beside it shows the way to the next.
    // (A talent's own requirement may also say "Level 3"; that is not the learner's level.)
    const levels = screen
      .getAllByText(/\bLevel 3\b/)
      .filter((element) => element.closest('[aria-labelledby="talents-heading"]') === null);
    expect(levels).toHaveLength(1);
    expect(screen.getByText('250 / 400 XP')).toBeVisible();
    expect(screen.getByText('3-day streak')).toBeVisible();
    expect(screen.getByText('Longest: 7 days')).toBeVisible();
    expect(screen.getByText('Prompt engineer')).toBeVisible();
    expect(screen.getByRole('heading', { level: 2, name: 'specialisation' })).toBeVisible();
    expect(screen.getByRole('heading', { level: 3, name: 'Retrieval specialist' })).toBeVisible();
    expect(screen.getByRole('heading', { level: 2, name: 'Competency matrix' })).toBeVisible();
    expect(screen.queryByRole('img', { name: 'Talent tree' })).not.toBeInTheDocument();
  });

  it('is the character sheet in RPG mode, with class names and the constellation', async () => {
    api();
    await mount('rpg');

    expect(await screen.findByRole('heading', { level: 1, name: 'Character sheet' })).toBeVisible();
    expect(screen.getByText('Learning streak: 3 days')).toBeVisible();
    expect(screen.getByRole('heading', { level: 2, name: 'class' })).toBeVisible();
    expect(screen.getByRole('heading', { level: 3, name: 'Loremaster' })).toBeVisible();
    expect(screen.getByText('Keeper of the Deepstacks')).toBeVisible();
    // Names without flavour fall back to the RPG lexicon.
    expect(screen.getByRole('heading', { level: 3, name: 'Artificer' })).toBeVisible();
    expect(screen.getByRole('img', { name: 'Talent tree' })).toBeInTheDocument();
    expect(screen.getByRole('table')).toBeInTheDocument();
  });

  it('lists earned badges first with their date, then the rest with how to earn them', async () => {
    api();
    await mount('professional');

    const section = within(await screen.findByRole('region', { name: 'achievements' }));
    const cards = section.getAllByRole('listitem');
    expect(cards).toHaveLength(2);
    expect(cards[0]).toHaveTextContent('First steps');
    expect(cards[0]).toHaveTextContent('Earned 3 Oct 2026');
    expect(cards[0]).toHaveAttribute('data-earned', 'true');
    expect(cards[1]).toHaveTextContent('Getting going');
    expect(cards[1]).toHaveTextContent('Not yet earned');
    expect(cards[1]).toHaveTextContent('Pass five exercises.');
    expect(cards[0]).toHaveTextContent('Passed one exercise.');
    expect(section.getByText('1 of 2 earned')).toBeVisible();
    // The ones still to earn are folded away under a disclosure that says how many.
    const more = section.getByText('1 more to earn').closest('details');
    expect(more).not.toBeNull();
    expect(more).not.toHaveAttribute('open');
    expect(more).toContainElement(cards[1] ?? null);
    expect(more).not.toContainElement(cards[0] ?? null);
    await userEvent.click(section.getByText('1 more to earn'));
    expect(more).toHaveAttribute('open');
  });

  it('keeps the time zone in a settings section at the end', async () => {
    api();
    await mount('rpg');
    const settings = await screen.findByRole('region', { name: 'Settings' });
    expect(within(settings).getByRole('combobox', { name: 'Time zone' })).toBeVisible();
    const regions = screen.getAllByRole('region');
    expect(regions[regions.length - 1]).toBe(settings);
    expect(screen.queryByRole('heading', { level: 2, name: 'Time zone' })).toBeNull();
  });

  it('words badges in quests in RPG mode, never exercises', async () => {
    api();
    await mount('rpg');

    const section = within(await screen.findByRole('region', { name: 'badges' }));
    const cards = section.getAllByRole('listitem');
    expect(cards[0]).toHaveTextContent('Conquered one quest.');
    expect(cards[1]).toHaveTextContent('Conquer five quests.');
    expect(section.queryByText(/exercise/)).toBeNull();
  });

  it.each([
    ['professional', 'Certificates'],
    ['rpg', 'Seals of completion'],
  ] as const)('lists certificates in an anchored section (%s)', async (mode, heading) => {
    api({ 'GET /api/certificates': () => json({ certificates: [CERTIFICATE] }) });
    await mount(mode);

    const section = await screen.findByRole('region', { name: heading });
    expect(section).toHaveAttribute('id', 'certificates');
    expect(within(section).getByRole('heading', { level: 3, name: 'Foundations' })).toBeVisible();
  });

  it('says why a path cannot be chosen yet', async () => {
    api();
    await mount('professional');

    const choose = await screen.findByRole('button', {
      name: 'Choose: Integration specialist',
    });
    expect(choose).toBeDisabled();
    expect(choose).toHaveAccessibleDescription(
      'Complete Foundations to choose this specialisation.',
    );
    expect(screen.getByText('Current')).toBeVisible();
  });

  it('says why a class cannot be taken yet in RPG words', async () => {
    api();
    await mount('rpg');

    const take = await screen.findByRole('button', { name: 'Take this class: Artificer' });
    expect(take).toHaveAccessibleDescription('Conquer Foundations to take this class.');
  });

  it('warns before changing path, names the refunded talents, then lists them afterwards', async () => {
    const tree: TalentTree = treeOf({
      nodes: NODES.map((node) =>
        node.id === 'index-builder' ? { ...node, state: 'allocated' as const } : node,
      ),
    });
    let profile: PathProfile = PATH_PROFILE;
    const seen = api({
      'GET /api/talents': () => json(tree),
      'GET /api/profile': () => json(profile),
      'PUT /api/profile': () => {
        profile = { ...PATH_PROFILE, path: 'generalist', dropped_talents: ['index-builder'] };
        return json(profile);
      },
    });
    const user = userEvent.setup();
    await mount('professional');

    expect(await screen.findByText(/refunds the competency points/)).toBeVisible();
    await user.click(await screen.findByRole('button', { name: 'Choose: Generalist' }));

    const confirm = screen.getByRole('group', { name: 'Confirm specialisation change' });
    expect(confirm).toHaveTextContent('Switching to Generalist refunds Index builder.');
    expect(seen.some((request) => request.method === 'PUT')).toBe(false);

    await user.click(within(confirm).getByRole('button', { name: 'Change anyway' }));

    expect(await screen.findByText('Refunded: Index builder.')).toBeVisible();
    const put = seen.find((request) => request.method === 'PUT');
    expect(await put?.json()).toEqual({ path: 'generalist' });
  });

  it('changes path straight away when there is nothing to refund', async () => {
    const seen = api({ 'PUT /api/profile': () => json({ ...PATH_PROFILE, path: 'generalist' }) });
    await mount('rpg');

    await userEvent
      .setup()
      .click(await screen.findByRole('button', { name: /Take this class: Wayfarer/ }));

    await waitFor(() => {
      expect(seen.some((request) => request.method === 'PUT')).toBe(true);
    });
    expect(screen.queryByRole('group', { name: /Confirm/ })).not.toBeInTheDocument();
  });

  it('saves the time zone, offering only zones from the list', async () => {
    const seen = api({
      'PUT /api/profile': () => json({ ...PATH_PROFILE, time_zone: 'Asia/Tokyo' }),
    });
    const user = userEvent.setup();
    await mount('professional');

    const field = await screen.findByRole('combobox', { name: 'Time zone' });
    const save = screen.getByRole('button', { name: 'Save time zone' });
    expect(field).toHaveValue('Europe/London');
    expect(save).toBeDisabled();

    await user.clear(field);
    await user.type(field, 'Mars/Olympus');
    expect(save).toBeDisabled();
    expect(field).toBeInvalid();

    await user.clear(field);
    await user.type(field, 'Asia/Tokyo');
    expect(save).toBeEnabled();
    await user.click(save);

    await waitFor(() => {
      expect(seen.some((request) => request.method === 'PUT')).toBe(true);
    });
    expect(await seen.find((request) => request.method === 'PUT')?.json()).toEqual({
      time_zone: 'Asia/Tokyo',
    });
  });

  it('allocates a talent from the keyboard and shows a 409 reason inline', async () => {
    const seen = api({
      'POST /api/talents/prompt-craft/allocation': () =>
        problem(409, 'No talent points are left to spend.'),
    });
    const user = userEvent.setup();
    await mount('rpg');

    const learn = await screen.findByRole('button', { name: 'Learn Prompt craft' });
    learn.focus();
    await user.keyboard('{Enter}');

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Prompt craft: No talent points are left to spend.',
    );
    expect(
      seen.some((request) => request.url.endsWith('/api/talents/prompt-craft/allocation')),
    ).toBe(true);
  });

  it('updates the tree and the point counter after a successful allocation', async () => {
    let tree = treeOf();
    api({
      'GET /api/talents': () => json(tree),
      'POST /api/talents/prompt-craft/allocation': () => {
        tree = treeOf({
          spent_points: 2,
          available_points: 1,
          nodes: NODES.map((node) =>
            node.id === 'prompt-craft' ? { ...node, state: 'allocated' as const } : node,
          ),
        });
        return json(tree);
      },
    });
    await mount('professional');

    await userEvent
      .setup()
      .click(await screen.findByRole('button', { name: 'Acquire Prompt craft' }));

    expect(await screen.findByRole('button', { name: 'Release Prompt craft' })).toBeVisible();
    expect(screen.getByText('1 of 3 competency points available')).toBeVisible();
  });

  it('respecs after a confirm step and shows the refreshed tree', async () => {
    let tree = treeOf();
    const seen = api({
      'GET /api/talents': () => json(tree),
      'POST /api/talents/respec': () => {
        tree = treeOf({
          spent_points: 0,
          available_points: 3,
          nodes: NODES.map((node) => ({ ...node, state: 'available' as const })),
        });
        return json(tree);
      },
    });
    const user = userEvent.setup();
    await mount('professional');

    await user.click(await screen.findByRole('button', { name: 'Reset competencies' }));
    expect(seen.some((request) => request.method === 'POST')).toBe(false);
    await user.click(screen.getByRole('button', { name: 'Reset all' }));

    expect(await screen.findByText('3 of 3 competency points available')).toBeVisible();
  });

  it('reports a failed load', async () => {
    api({ 'GET /api/badges': () => problem(500, 'The badge list is unavailable.', 'server') });
    await mount('professional');

    expect(await screen.findByRole('alert')).toHaveTextContent('The badge list is unavailable.');
  });
});
