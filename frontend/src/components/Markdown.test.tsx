import { describe, expect, it } from 'vitest';

import { withoutLeadingTitle } from './Markdown';

describe('withoutLeadingTitle', () => {
  it('drops a leading level-1 heading only', () => {
    expect(withoutLeadingTitle('# Title\n\nBody\n\n# Later')).toBe('Body\n\n# Later');
  });

  it('leaves briefs without one alone', () => {
    expect(withoutLeadingTitle('## Sub\n\nBody')).toBe('## Sub\n\nBody');
  });
});
