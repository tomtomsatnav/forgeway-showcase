import { describe, expect, it } from 'vitest';

import { checksRevealSeconds } from './ResultsPanel';

describe('checksRevealSeconds', () => {
  it.each([1, 3, 9, 40, 200])('stays short with %i checks', (checks) => {
    expect(checksRevealSeconds(checks)).toBeLessThanOrEqual(0.9);
  });
});
