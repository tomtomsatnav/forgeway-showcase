import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Markdown, withoutLeadingTitle } from './Markdown';

describe('Markdown', () => {
  it('renders tables, which briefs use for rules', () => {
    render(<Markdown>{'| Code | Meaning |\n| --- | --- |\n| -32601 | Unknown |'}</Markdown>);
    expect(screen.getByRole('columnheader', { name: 'Meaning' })).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: '-32601' })).toBeInTheDocument();
  });

  it('still drops raw HTML', () => {
    const { container } = render(<Markdown>{'<script>alert(1)</script>\n\n<b>x</b>'}</Markdown>);
    expect(container.querySelector('script, b')).toBeNull();
  });
});

describe('withoutLeadingTitle', () => {
  it('drops a leading level-1 heading only', () => {
    expect(withoutLeadingTitle('# Title\n\nBody\n\n# Later')).toBe('Body\n\n# Later');
  });

  it('leaves briefs without one alone', () => {
    expect(withoutLeadingTitle('## Sub\n\nBody')).toBe('## Sub\n\nBody');
  });
});
