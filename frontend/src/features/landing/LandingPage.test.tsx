import { QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider, createMemoryHistory } from '@tanstack/react-router';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { BranchSummary, ExerciseSummary, Mode } from '../../api/types';
import { MAP, json, problem, stubApi } from '../../test/fixtures';
import { newQueryClient, renderInRouter, withMode } from '../../test/render';
import { createAppRouter } from '../../router';
import { LEXICONS } from '../../theme/lexicon';
import { ThemeProvider } from '../../theme/ThemeProvider';
import { formatPrice, priceLines, type Billing } from './billing';
import { LandingPage } from './LandingPage';

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

const exercise = (id: string, tier = 'beginner'): ExerciseSummary => ({
  id,
  title: `Title of ${id}`,
  tier,
  xp: 50,
  prerequisites: [],
  skills: [],
  status: 'locked',
  pro: false,
  entitled: true,
});

const branch = (id: string, count: number, extra: Partial<BranchSummary> = {}): BranchSummary => ({
  id,
  title: `Track ${id}`,
  summary: `Summary of ${id}.`,
  unlocked: id === 'starter',
  requires: id === 'starter' ? [] : ['starter'],
  kind: 'standard',
  pro: false,
  passed_count: 0,
  exercises: Array.from({ length: count }, (_, n) =>
    exercise(
      `${id}.e${n}`,
      n === count - 1 && extra.kind === undefined && id !== 'starter' ? 'capstone' : 'beginner',
    ),
  ),
  ...extra,
});

/** Two tracks with a capstone each, a root track without one, and one guided project. */
const CATALOGUE = {
  branches: [
    branch('starter', 4),
    branch('retrieval', 6),
    branch('memory', 5),
    branch('project-demo', 3, { kind: 'project', pro: true }),
  ],
};

const CONFIG = { turnstile_site_key: null, free_exercises_per_branch: 3, kit_wheel_url: null };

const BILLING: Billing = {
  enabled: true,
  currency: 'GBP',
  monthly_price_minor: 1900,
  annual_price_minor: 19000,
  intro_offer: { kind: 'trial_days', value: 7 },
};

function visitor(config: object = CONFIG) {
  return stubApi({
    'GET /api/auth/me': () => problem(401, 'Not signed in', 'unauthenticated'),
    'GET /api/catalogue': () => json(CATALOGUE),
    'GET /api/config': () => json(config),
  });
}

/** The real app router and theme, at `/`. */
async function renderApp(mode: Mode = 'professional') {
  localStorage.setItem('lattice.theme', JSON.stringify({ mode, scheme: 'light' }));
  const client = newQueryClient();
  const router = createAppRouter(client, createMemoryHistory({ initialEntries: ['/'] }));
  render(
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <RouterProvider router={router} />
      </ThemeProvider>
    </QueryClientProvider>,
  );
  await router.load();
  return router;
}

describe('the home route', () => {
  it('shows a visitor who is not signed in the landing page, not a redirect', async () => {
    visitor();
    const router = await renderApp();

    expect(
      await screen.findByRole('heading', {
        level: 1,
        name: 'Become an AI engineer. For real.',
      }),
    ).toBeVisible();
    expect(router.state.location.pathname).toBe('/');
    expect(document.title).toBe(LEXICONS.professional.landing.documentTitle);
    expect(document.querySelector('meta[name="description"]')).toHaveAttribute(
      'content',
      LEXICONS.professional.landing.metaDescription,
    );
  });

  it('keeps a signed-in learner on their map, as before', async () => {
    const seen = stubApi({
      'GET /api/auth/me': () =>
        json({
          id: 'u1',
          email: 'a@example.com',
          plan: 'free',
          email_verified: true,
          csrf_token: 'x',
          profile: { mode: 'professional', colour_scheme: 'light' },
        }),
      'GET /api/map': () => json(MAP),
      'GET /api/releases': () => json({ last_seen: null, unread: false, releases: [] }),
    });
    await renderApp();

    expect(await screen.findByRole('heading', { level: 1, name: 'Syllabus' })).toBeVisible();
    expect(screen.queryByText('Become an AI engineer. For real.')).toBeNull();
    expect(seen.some((request) => new URL(request.url).pathname === '/api/catalogue')).toBe(false);
  });

  it('takes a visitor from the call to action to registration', async () => {
    visitor();
    const router = await renderApp();

    const hero = await screen.findByRole('region', {
      name: 'Become an AI engineer. For real.',
    });
    await userEvent
      .setup()
      .click(within(hero).getByRole('link', { name: 'Write your first agent' }));
    expect(router.state.location.pathname).toBe('/register');
  });
});

describe('the landing page', () => {
  it.each<Mode>(['professional', 'rpg'])(
    'states the counts the catalogue gives, in %s words',
    async (mode) => {
      visitor();
      await renderInRouter(withMode(mode, <LandingPage />));
      const summary =
        mode === 'professional'
          ? '3 tracks and 1 guided project: 18 exercises, 2 of them capstone projects.'
          : '3 zones and 1 expedition: 18 quests, 2 of them boss challenges.';
      expect(await screen.findByText(summary)).toBeVisible();
    },
  );

  it.each<Mode>(['professional', 'rpg'])(
    'counts a primer apart from the tracks and their exercises, in %s words',
    async (mode) => {
      stubApi({
        'GET /api/auth/me': () => problem(401, 'Not signed in', 'unauthenticated'),
        'GET /api/config': () => json(CONFIG),
        'GET /api/catalogue': () =>
          json({
            branches: [
              ...CATALOGUE.branches,
              branch('python-primer', 5, { kind: 'primer', requires: [] }),
            ],
          }),
      });
      await renderInRouter(withMode(mode, <LandingPage />));
      const summary =
        mode === 'professional'
          ? '3 tracks and 1 guided project: 18 exercises, 2 of them capstone projects. A free Python primer sits alongside them.'
          : '3 zones and 1 expedition: 18 quests, 2 of them boss challenges. A free Python primer zone lies alongside them.';
      expect(await screen.findByText(summary)).toBeVisible();
    },
  );

  it('lays the tracks out as the syllabus, from the catalogue', async () => {
    visitor();
    await renderInRouter(withMode('professional', <LandingPage />));
    const tracks = await screen.findByRole('region', { name: 'What you will build' });
    expect(await within(tracks).findByRole('heading', { name: 'Track retrieval' })).toBeVisible();
    expect(within(tracks).getByText(/track 2 · 6 exercises/)).toBeVisible();
  });

  it('starts every track folded: summary, count, Pro mark and a control to show it', async () => {
    visitor();
    await renderInRouter(withMode('professional', <LandingPage />));
    const tracks = await screen.findByRole('region', { name: 'What you will build' });
    await within(tracks).findByRole('heading', { name: 'Track starter' });
    for (const [id, count] of [
      ['starter', 4],
      ['retrieval', 6],
      ['memory', 5],
      ['project-demo', 3],
    ] as const) {
      expect(within(tracks).getByText(`Summary of ${id}.`)).toBeVisible();
      const fold = within(tracks).getByRole('button', {
        name: `Show ${String(count)} exercises in Track ${id}`,
      });
      expect(fold).toHaveAttribute('aria-expanded', 'false');
      expect(
        within(tracks).queryByRole('link', { name: new RegExp(`Title of ${id}\\.e0`) }),
      ).toBeNull();
    }
    const project = tracks.querySelector('#track-project-demo');
    if (project === null) throw new Error('the project track should be there');
    expect(within(project as HTMLElement).getByText('Pro')).toBeVisible();

    await userEvent.click(
      within(tracks).getByRole('button', { name: 'Show 4 exercises in Track starter' }),
    );
    expect(within(tracks).getByRole('link', { name: /Title of starter\.e0/ })).toBeVisible();
  });

  it('says so, without inventing numbers, when the catalogue cannot be read', async () => {
    stubApi({
      'GET /api/catalogue': () => problem(404, 'Not found', 'not-found'),
      'GET /api/config': () => json(CONFIG),
      'GET /api/auth/me': () => problem(401, 'Not signed in', 'unauthenticated'),
    });
    await renderInRouter(withMode('professional', <LandingPage />));
    expect(await screen.findByText(LEXICONS.professional.landing.tracksUnavailable)).toBeVisible();
  });

  it('shows a real failing check with its message, using the app’s check result', async () => {
    visitor();
    await renderInRouter(withMode('professional', <LandingPage />));
    const example = screen.getByRole('figure', { name: 'Example check results' });
    expect(within(example).getByText('Not yet: 3 of 4 checks passed')).toBeVisible();
    expect(within(example).getAllByText('Failed')).toHaveLength(1);
    expect(within(example).getByText(/long after max_steps/)).toBeVisible();
  });

  it('offers the waitlist and shows no price while billing is off', async () => {
    visitor();
    await renderInRouter(withMode('professional', <LandingPage />));
    const plans = screen.getByRole('region', { name: 'Free and Pro' });
    expect(await within(plans).findByText('The first 3 exercises of every track')).toBeVisible();
    expect(within(plans).getByText(/Pro is not on sale yet and nothing is charged/)).toBeVisible();
    expect(within(plans).queryByRole('link', { name: 'Choose Pro' })).toBeNull();
    expect(document.body.textContent).not.toMatch(/£|\$\d|pre-order/i);
  });

  it('prices both plans from the config once billing is on, annual first', async () => {
    visitor({ ...CONFIG, billing: BILLING });
    await renderInRouter(withMode('professional', <LandingPage />));
    const plans = screen.getByRole('region', { name: 'Free and Pro' });
    expect(await within(plans).findByRole('radio', { name: 'Annual' })).toBeChecked();
    expect(within(plans).getByText('£190/year')).toBeVisible();
    expect(within(plans).getByText('Two months free')).toBeVisible();
    expect(
      within(plans).getByText(
        'Start your 7-day free trial. Then £190/year, or £19/month. Cancel any time before the trial ends and you won’t be charged.',
      ),
    ).toBeVisible();
    expect(within(plans).getByRole('link', { name: 'Start your free trial' })).toHaveAttribute(
      'href',
      '/pro',
    );
    expect(within(plans).queryByText(/Pro is not on sale yet/)).toBeNull();
    expect(plans.textContent).not.toMatch(/VAT/);

    await userEvent.setup().click(within(plans).getByRole('radio', { name: 'Monthly' }));
    expect(within(plans).getByText('£19/month')).toBeVisible();
    expect(within(plans).queryByText('Two months free')).toBeNull();
    expect(within(plans).getByText(/Then £19\/month, or £190\/year\./)).toBeVisible();
  });

  it('keeps the waitlist when billing exists but is switched off', async () => {
    visitor({ ...CONFIG, billing: { ...BILLING, enabled: false } });
    await renderInRouter(withMode('professional', <LandingPage />));
    const plans = screen.getByRole('region', { name: 'Free and Pro' });
    expect(await within(plans).findByText(/Pro is not on sale yet/)).toBeVisible();
    expect(plans.textContent).not.toMatch(/£/);
  });

  it('keeps its headings in order', async () => {
    visitor();
    await renderInRouter(withMode('rpg', <LandingPage />));
    await screen.findByText(/3 zones/);
    const levels = screen.getAllByRole('heading').map((heading) => Number(heading.tagName[1]));
    expect(levels[0]).toBe(1);
    levels.slice(1).forEach((level, index) => {
      expect(level - (levels[index] ?? 1)).toBeLessThanOrEqual(1);
    });
  });
});

describe('addresses people guess', () => {
  async function at(path: string) {
    visitor();
    const client = newQueryClient();
    const router = createAppRouter(client, createMemoryHistory({ initialEntries: [path] }));
    render(
      <QueryClientProvider client={client}>
        <ThemeProvider>
          <RouterProvider router={router} />
        </ThemeProvider>
      </QueryClientProvider>,
    );
    await router.load();
    return router;
  }

  it.each([
    ['/home', '/'],
    ['/login', '/sign-in'],
    ['/signup', '/register'],
    ['/pricing', '/welcome'],
    ['/privacy-policy', '/privacy'],
  ])('sends %s to %s', async (from, to) => {
    const router = await at(from);
    await vi.waitFor(() => {
      expect(router.state.location.pathname).toBe(to);
    });
  });

  it('shows the landing page at /welcome even when signed in', async () => {
    stubApi({
      'GET /api/auth/me': () =>
        json({
          id: 'u1',
          email: 'a@example.com',
          plan: 'free',
          email_verified: true,
          csrf_token: 'x',
          profile: { mode: 'professional', colour_scheme: 'system' },
        }),
      'GET /api/catalogue': () => json(CATALOGUE),
      'GET /api/config': () => json(CONFIG),
    });
    const client = newQueryClient();
    const router = createAppRouter(client, createMemoryHistory({ initialEntries: ['/welcome'] }));
    render(
      <QueryClientProvider client={client}>
        <ThemeProvider>
          <RouterProvider router={router} />
        </ThemeProvider>
      </QueryClientProvider>,
    );
    await router.load();
    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent(
      LEXICONS.professional.landing.heroTitle,
    );
  });

  it('shows a real page, with a way back, for anything else', async () => {
    await at('/no-such-page');
    const copy = LEXICONS.professional;
    expect(await screen.findByRole('heading', { name: copy.notFoundTitle })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: copy.notFoundHome })).toHaveAttribute('href', '/');
  });
});

describe('in-app live runs', () => {
  it.each([true, false])('mentions them only while they are on (%s)', async (on) => {
    visitor({ ...CONFIG, live_runs: on });
    await renderApp();
    await screen.findByRole('heading', { level: 1 });
    await vi.waitFor(() => {
      expect(screen.queryByText(LEXICONS.professional.landing.liveInApp) !== null).toBe(on);
    });
  });
});

describe('prices', () => {
  it('formats pence, dropping whole-pound pence', () => {
    expect(formatPrice(1900, 'GBP')).toBe('£19');
    expect(formatPrice(950, 'GBP')).toBe('£9.50');
  });

  it('words a saving that is not whole months, and shows no offer without a trial', () => {
    const copy = LEXICONS.professional.landing;
    expect(priceLines({ ...BILLING, annual_price_minor: 20000 }, 'annual', copy).saving).toBe(
      '£28 less than paying monthly',
    );
    expect(priceLines({ ...BILLING, annual_price_minor: 22800 }, 'annual', copy).saving).toBeNull();
    const coupon = { kind: 'percent_off_first_month' as const, value: 50 };
    expect(priceLines({ ...BILLING, intro_offer: coupon }, 'monthly', copy).trial).toBeNull();
    expect(
      priceLines({ ...BILLING, intro_offer: null }, 'annual', LEXICONS.rpg.landing).trial,
    ).toBeNull();
  });
});
