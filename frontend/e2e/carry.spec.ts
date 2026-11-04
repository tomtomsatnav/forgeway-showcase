import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { expect, test } from '@playwright/test';

import { GRADED, passStarterZone, registerPro } from './support';

/**
 * Carried files, on a test-only guided project (e2e/fixtures/e2e-project) whose second milestone
 * says `carry_from` the first. The project needs only the starter zone, so it is cheap to reach.
 * It is never shipped: the e2e stack (docker-compose.e2e.yml, used by CI) mounts the fixture at
 * content/branches/e2e-project in the api, worker and migrate containers. Without it the spec
 * skips.
 */
const BRANCH = 'e2e-project';
const FIRST = `${BRANCH}.first-milestone`;
const SECOND = `${BRANCH}.second-milestone`;
const MARKER = '# my own greeting, carried forward';

const fixtureSolution = readFileSync(
  resolve(import.meta.dirname, 'fixtures/e2e-project/exercises/first-milestone/solution/greet.py'),
  'utf8',
);

test('a milestone opens on the passing files from the one before, and can start over', async ({
  page,
}) => {
  test.setTimeout(240_000);
  await registerPro(page); // guided projects are Pro
  const { branches } = (await (await page.request.get('/api/map')).json()) as {
    branches: { id: string }[];
  };
  test.skip(!branches.some((branch) => branch.id === BRANCH), 'needs the e2e-project fixture');

  await passStarterZone(page);
  const me = (await (await page.request.get('/api/auth/me')).json()) as { csrf_token: string };
  let id = '';
  // The starter zone used up this minute's attempts, so wait out the rate limit.
  await expect(async () => {
    const submitted = await page.request.post(`/api/exercises/${FIRST}/attempts`, {
      headers: { 'X-CSRF-Token': me.csrf_token },
      data: { files: { 'greet.py': `${MARKER}\n${fixtureSolution}` } },
    });
    expect(submitted.status()).toBe(202);
    ({ id } = (await submitted.json()) as { id: string });
  }).toPass({ timeout: 90_000, intervals: [5_000] });
  await expect
    .poll(
      async () =>
        ((await (await page.request.get(`/api/attempts/${id}`)).json()) as { status: string })
          .status,
      { timeout: 60_000 },
    )
    .toBe('passed');

  await page.goto(`/exercises/${SECOND}`);
  const editor = page.getByRole('textbox', { name: /code editor/i });
  const note = page.getByRole('note').filter({ hasText: 'Continuing from your work on' });
  await expect(note).toContainText('First milestone', GRADED);
  await expect(editor).toContainText(MARKER);

  await note.getByRole('button', { name: 'Start from the provided code instead' }).click();
  await expect(note.getByText(/replaced by the provided starter code/)).toBeVisible();
  await note.getByRole('button', { name: 'Use the provided code' }).click();
  await expect(note).toBeHidden();
  await expect(editor).toContainText('raise NotImplementedError');
  await expect(editor).not.toContainText(MARKER);

  // The reset sticks: the carried files do not come back.
  await page.reload();
  await expect(editor).toContainText('raise NotImplementedError');
  await expect(editor).not.toContainText(MARKER);
  await expect(page.getByRole('note').filter({ hasText: 'Continuing from' })).toHaveCount(0);
});
