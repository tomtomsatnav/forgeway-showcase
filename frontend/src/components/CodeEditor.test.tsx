import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { withMode } from '../test/render';
import { CodeEditor } from './CodeEditor';

const renderEditor = (mode: 'professional' | 'rpg') =>
  render(
    withMode(
      mode,
      <CodeEditor
        files={{ 'solution.py': 'def f():\n    return 1\n' }}
        paths={['solution.py']}
        activePath="solution.py"
        onActivePathChange={() => undefined}
        onChange={() => undefined}
      />,
    ),
  );

describe('CodeEditor', () => {
  it('keeps its accessible name and the way out', () => {
    renderEditor('professional');
    expect(screen.getByRole('textbox', { name: 'Code editor for solution.py' })).toBeVisible();
    expect(screen.getByText(/press escape, then tab/i)).toBeInTheDocument();
  });

  it.each([
    ['professional', 'Keyboard shortcuts'],
    ['rpg', "The scribe's shortcuts"],
  ] as const)('lists the keyboard shortcuts in %s mode', (mode, summary) => {
    const { container } = renderEditor(mode);
    expect(screen.getByText(summary).closest('summary')).not.toBeNull();
    const terms = [...container.querySelectorAll('dt')].map((dt) => dt.textContent);
    expect(terms).toContain('Escape, then Tab');
    expect(terms).toContain('Tab / Shift+Tab');
  });
});
