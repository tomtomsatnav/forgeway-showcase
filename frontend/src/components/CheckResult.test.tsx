import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { CheckResult, splitMessage } from './CheckResult';

describe('CheckResult', () => {
  it('says a check passed in words, not only colour', () => {
    render(
      <CheckResult
        check={{ id: 'a', title: 'Returns the reply', passed: true, message: '', output: '' }}
      />,
    );

    expect(screen.getByRole('heading', { name: 'Returns the reply' })).toBeInTheDocument();
    expect(screen.getByText('Passed')).toBeVisible();
    expect(screen.queryByText('Failed')).not.toBeInTheDocument();
  });

  it('says a check failed in words and shows its message in a well', () => {
    render(
      <CheckResult
        check={{
          id: 'b',
          title: 'Sends the question',
          passed: false,
          message: 'Expected a user message',
          output: '',
        }}
      />,
    );

    expect(screen.getByText('Failed')).toBeVisible();
    expect(screen.getByText('Expected a user message')).toBeVisible();
  });

  it('keeps the learner output collapsed until asked for', async () => {
    render(
      <CheckResult
        check={{
          id: 'c',
          title: 'Prints',
          passed: false,
          message: 'No',
          output: 'hello from my code',
        }}
      />,
    );

    expect(screen.getByText('hello from my code')).not.toBeVisible();
    await userEvent.setup().click(screen.getByText('Your output'));
    expect(screen.getByText('hello from my code')).toBeVisible();
  });

  it('sets the explanation in the UI font and only code-like parts in monospace', () => {
    render(
      <CheckResult
        check={{
          id: 'd',
          title: 'Cites the sources',
          passed: false,
          message: 'Put each source on its own line. Expected:\n[1] a.md\n[2] b.md\nGot:\n[1] a.md',
          output: '',
        }}
      />,
    );

    const prose = screen.getByText(/Put each source on its own line/);
    expect(prose.tagName).toBe('P');
    expect(prose).not.toHaveClass('font-mono');
    const expected = screen.getByText(/\[2\] b\.md/);
    expect(expected.tagName).toBe('PRE');
    expect(expected).toHaveClass('font-mono');
    expect(expected).toHaveTextContent('[1] a.md [2] b.md');
    expect(screen.getByText('Got:').tagName).toBe('P');
  });

  it('keeps a plain sentence as prose and the learner output in monospace', async () => {
    render(
      <CheckResult
        check={{
          id: 'e',
          title: 'Skips what does not fit',
          passed: false,
          message: 'With budget 52, expected 52 tokens and got 27.',
          output: 'debug: 27',
        }}
      />,
    );

    const message = screen.getByText('With budget 52, expected 52 tokens and got 27.');
    expect(message).not.toHaveClass('font-mono');
    expect(document.querySelectorAll('pre')).toHaveLength(1);
    await userEvent.setup().click(screen.getByText('Your output'));
    expect(screen.getByText('debug: 27')).toHaveClass('font-mono');
  });
});

describe('splitMessage', () => {
  it('treats fenced, indented and value lines as code', () => {
    expect(
      splitMessage(
        'Your code raised ValueError: no\n  ask.py, line 3, in ask\nTry again.\nGot: 4\n```\nx = 1\n```',
      ),
    ).toEqual([
      { kind: 'prose', text: 'Your code raised ValueError: no' },
      { kind: 'code', text: '  ask.py, line 3, in ask' },
      { kind: 'prose', text: 'Try again.' },
      { kind: 'code', text: 'Got: 4\nx = 1' },
    ]);
  });

  it('keeps an import failure excerpt in code after its introduction', () => {
    expect(splitMessage('Your code could not be imported:\nSyntaxError: bad')).toEqual([
      { kind: 'prose', text: 'Your code could not be imported:' },
      { kind: 'code', text: 'SyntaxError: bad' },
    ]);
  });
});
