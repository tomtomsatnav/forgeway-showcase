import { describe, expect, it } from 'vitest';

import { LEXICONS } from '../theme/lexicon';
import { ApiError, problemMessage, toApiError } from './errors';

const SERVER_DETAIL = 'The server’s own words.';

function fail(status: number, code: string, extra: Record<string, unknown> = {}) {
  return toApiError(status, { title: 'Problem', status, detail: SERVER_DETAIL, code, ...extra });
}

describe('toApiError', () => {
  it('carries the limit and budget_minutes extensions', () => {
    expect(fail(429, 'attempt-daily-cap', { limit: 20 }).limit).toBe(20);
    expect(fail(429, 'grading-budget', { budget_minutes: 15 }).budgetMinutes).toBe(15);
    expect(fail(429, 'rate-limited').limit).toBeNull();
    expect(fail(429, 'rate-limited', { limit: 'lots' }).limit).toBeNull();
  });
});

describe('problemMessage', () => {
  const CASES: [number, string, Record<string, unknown>][] = [
    [403, 'plan-required', {}],
    [403, 'email-unverified', {}],
    [403, 'challenge-failed', {}],
    [409, 'attempt-in-flight', {}],
    [429, 'rate-limited', {}],
    [429, 'attempt-daily-cap', { limit: 20 }],
    [429, 'grading-budget', { budget_minutes: 30 }],
    [503, 'busy', {}],
  ];

  it.each(['professional', 'rpg'] as const)('words every mapped code itself (%s)', (mode) => {
    const lexicon = LEXICONS[mode];
    const messages = CASES.map(([status, code, extra]) =>
      problemMessage(fail(status, code, extra), lexicon),
    );
    for (const message of messages) expect(message).not.toBe(SERVER_DETAIL);
    expect(new Set(messages).size).toBe(CASES.length);
  });

  it.each(['professional', 'rpg'] as const)('names the numbers the server sends (%s)', (mode) => {
    const lexicon = LEXICONS[mode];
    expect(problemMessage(fail(429, 'attempt-daily-cap', { limit: 20 }), lexicon)).toContain('20');
    expect(problemMessage(fail(429, 'grading-budget', { budget_minutes: 30 }), lexicon)).toContain(
      '30 minutes',
    );
    expect(problemMessage(fail(429, 'attempt-daily-cap'), lexicon)).not.toMatch(/null|NaN/);
  });

  it('speaks plainly in professional mode and in voice in RPG mode', () => {
    const plain = problemMessage(fail(503, 'busy'), LEXICONS.professional);
    const voiced = problemMessage(fail(503, 'busy'), LEXICONS.rpg);
    expect(plain).toBe('Grading is busy right now. Your code is saved; try again in a minute.');
    expect(voiced).toMatch(/judges/);
    expect(problemMessage(fail(403, 'plan-required'), LEXICONS.professional)).toMatch(/waitlist/);
    expect(problemMessage(fail(403, 'plan-required'), LEXICONS.rpg)).toMatch(/waitlist/);
  });

  it('keeps the server detail for a code it does not map, and handles other errors', () => {
    expect(problemMessage(fail(409, 'something-new'), LEXICONS.rpg)).toBe(SERVER_DETAIL);
    expect(problemMessage(new TypeError('x'), LEXICONS.professional)).toBe(
      'Cannot reach the server. Check your connection.',
    );
    expect(problemMessage(new ApiError(404, 'not-found', 'Gone.'), LEXICONS.rpg)).toBe('Gone.');
  });
});
