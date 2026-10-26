import { readFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';

import { expect, type Page } from '@playwright/test';

import type { Mode } from '../src/api/types';
import { LEXICONS } from '../src/theme/lexicon';

export const MODES: readonly Mode[] = ['professional', 'rpg'];
export const SCHEMES = ['light', 'dark'] as const;
export type Scheme = (typeof SCHEMES)[number];

const MODE_LABEL: Record<Mode, string> = { professional: 'Professional', rpg: 'RPG' };

export const PASSWORD = 'correct horse battery staple';

export function uniqueEmail(): string {
  return `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

/**
 * The token in the newest email sent to `email`. The stack's console email provider keeps an
 * outbox that the API exposes only with LATTICE_E2E=1 (docker-compose.e2e.yml); the email goes
 * out just after the response, so this polls.
 */
export async function emailedToken(page: Page, email: string): Promise<string> {
  let token = '';
  await expect
    .poll(
      async () => {
        const response = await page.request.get('/api/test/outbox/latest', { params: { email } });
        if (response.status() === 404 && !('code' in ((await response.json()) as object))) {
          throw new Error('No test outbox: start the stack with docker-compose.e2e.yml');
        }
        if (!response.ok()) return '';
        token = ((await response.json()) as { token: string }).token;
        return token;
      },
      { message: `an email to ${email}`, timeout: 10_000 },
    )
    .not.toBe('');
  return token;
}

/** Fill in and send the register form; the page then says to check the inbox. */
export async function registerUnverified(page: Page, email = uniqueEmail()): Promise<string> {
  await page.goto('/register');
  await page.getByLabel('Display name').fill('E2E Learner');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(PASSWORD);
  await page.getByRole('button', { name: LEXICONS.professional.register }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(
    LEXICONS.professional.checkInboxTitle,
  );
  return email;
}

/** Follow the verification link emailed to `email`. */
export async function verifyEmail(page: Page, email: string): Promise<void> {
  await page.goto(`/verify-email?token=${await emailedToken(page, email)}`);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(
    LEXICONS.professional.emailVerifiedTitle,
  );
}

/** Register a fresh learner, verify their email, set the mode and land on the map. */
export async function register(page: Page, mode: Mode = 'professional'): Promise<string> {
  const email = await registerUnverified(page);
  await verifyEmail(page, email);
  await page.getByRole('link', { name: LEXICONS.professional.checkInboxContinue }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(LEXICONS.professional.mapTitle);
  await setTheme(page, mode, 'light');
  return email;
}

/**
 * Put a learner on a plan through the test-only endpoint, which the API mounts only on the e2e
 * stack (LATTICE_E2E=1 with console email; never in production, where the owner runs
 * `forgeway accounts set-plan`). Capstones, guided projects and publishing certificates are Pro.
 */
export async function setPlan(
  page: Page,
  email: string,
  plan: 'free' | 'pro' | 'team',
): Promise<void> {
  const response = await page.request.post('/api/test/plan', { data: { email, plan } });
  expect(response.status(), 'set the plan (needs docker-compose.e2e.yml)').toBe(204);
}

/** Register a fresh Pro learner: `register`, then the Pro plan. */
export async function registerPro(page: Page, mode: Mode = 'professional'): Promise<string> {
  const email = await register(page, mode);
  await setPlan(page, email, 'pro');
  // The app reads the plan once per visit, as it would after a real plan change.
  await page.reload();
  return email;
}

export async function setTheme(page: Page, mode: Mode, scheme: Scheme): Promise<void> {
  // Below 640px the toggles sit in the header menu: open it, and close it again afterwards.
  const menu = page.getByRole('banner').getByRole('button', { name: 'Menu' });
  const folded = (await menu.isVisible()) && (await menu.getAttribute('aria-expanded')) === 'false';
  if (folded) await menu.click();
  await page.getByRole('radio', { name: MODE_LABEL[mode] }).check();
  await page
    .getByRole('radio', { name: `${scheme === 'light' ? 'Light' : 'Dark'} colour scheme` })
    .check();
  if (folded) await page.keyboard.press('Escape');
  await expect(page.locator('html')).toHaveAttribute('data-mode', mode);
  await expect(page.locator('html')).toHaveAttribute('data-scheme', scheme);
}

/** The map link for an exercise, matched on its real title (present in both modes). */
export function exerciseLink(page: Page, title: RegExp) {
  return page.getByRole('link', { name: title });
}

export const FIRST_EXERCISE = /your first completion/i;

/** Grading is asynchronous and queued: under a parallel suite a result can take several seconds. */
export const GRADED = { timeout: 30_000 } as const;

/** The syllabus folds finished and locked tracks: open one if it is folded. */
export async function openTrack(page: Page, branchId: string): Promise<void> {
  const track = page.locator(`#track-${branchId}`);
  await expect(track).toBeVisible();
  const fold = track.getByRole('button', { name: /^Show / });
  if ((await fold.count()) > 0) await fold.click();
}

/** RPG mode opens on the world map: select the hub zone to reach its quests. Professional is a no-op. */
export async function enterStarterZone(page: Page): Promise<void> {
  if ((await page.locator('html').getAttribute('data-mode')) !== 'rpg') return;
  // Already inside a zone (for example after "Back to the atlas" from an exercise).
  const zones = page.getByRole('navigation', { name: LEXICONS.rpg.branchPlural }).getByRole('link');
  if ((await zones.count()) === 0) return;
  await zones.first().click();
}

export async function openFirstExercise(page: Page): Promise<void> {
  await enterStarterZone(page);
  await exerciseLink(page, FIRST_EXERCISE).click();
  await expect(page.getByRole('textbox', { name: /code editor/i })).toBeVisible();
}

const STARTER_EXERCISES = resolve(import.meta.dirname, '../../content/branches/starter/exercises');

/** The reference solution's files for a starter exercise id such as "starter.first-completion". */
export function starterSolution(exerciseId: string): Record<string, string> {
  const dir = resolve(STARTER_EXERCISES, exerciseId.split('.')[1] ?? '', 'solution');
  return Object.fromEntries(
    readdirSync(dir).map((name) => [name, readFileSync(resolve(dir, name), 'utf8')]),
  );
}

/**
 * Pass every starter exercise through the API with its reference solution, in unlock order, as
 * the signed-in learner. The journey spec covers passing by hand; this gets a learner to the
 * point of choosing a class without grading ten exercises through the UI.
 */
export async function passStarterZone(page: Page): Promise<void> {
  const { request } = page;
  const me = (await (await request.get('/api/auth/me')).json()) as { csrf_token: string };
  const headers = { 'X-CSRF-Token': me.csrf_token };

  for (let round = 0; round < 12; round++) {
    const map = (await (await request.get('/api/map')).json()) as {
      branches: { id: string; exercises: { id: string; status: string }[] }[];
    };
    const next = map.branches
      .find((branch) => branch.id === 'starter')
      ?.exercises.find((exercise) => exercise.status === 'available');
    if (next === undefined) return;

    const submitted = await request.post(`/api/exercises/${next.id}/attempts`, {
      headers,
      data: { files: starterSolution(next.id) },
    });
    expect(submitted.ok(), `submit ${next.id}`).toBe(true);
    const { id } = (await submitted.json()) as { id: string };
    await expect
      .poll(
        async () =>
          ((await (await request.get(`/api/attempts/${id}`)).json()) as { status: string }).status,
        { message: `grading ${next.id}`, timeout: 60_000 },
      )
      .toBe('passed');
  }
  throw new Error('The starter zone did not finish');
}

export interface CapstoneRef {
  branchId: string;
  exerciseId: string;
  title: string;
  /** The boss's name when the RPG flavour has one. */
  boss: string | undefined;
}

interface MapBranch {
  id: string;
  requires: string[];
  exercises: { id: string; title: string; tier: string }[];
}

/** The first capstone in the signed-in learner's map, or undefined if the content has none. */
export async function findCapstone(page: Page): Promise<CapstoneRef | undefined> {
  const { branches } = (await (await page.request.get('/api/map')).json()) as {
    branches: MapBranch[];
  };
  for (const branch of branches) {
    const exercise = branch.exercises.find((item) => item.tier === 'capstone');
    if (exercise === undefined) continue;
    const flavour = (await (await page.request.get('/api/themes/rpg/flavour')).json()) as {
      bosses: Record<string, { name: string }>;
    };
    return {
      branchId: branch.id,
      exerciseId: exercise.id,
      title: exercise.title,
      boss: flavour.bosses[exercise.id]?.name,
    };
  }
  return undefined;
}
