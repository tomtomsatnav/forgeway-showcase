import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { withMode } from '../../test/render';
import { CarriedFiles } from './CarriedFiles';

describe('CarriedFiles', () => {
  it('names the earlier exercise and resets only after a confirm step', async () => {
    const onReset = vi.fn();
    const user = userEvent.setup();
    render(withMode('professional', <CarriedFiles title="Hybrid retrieval" onReset={onReset} />));

    expect(screen.getByRole('note')).toHaveTextContent(
      'Continuing from your work on Hybrid retrieval.',
    );
    await user.click(screen.getByRole('button', { name: 'Start from the provided code instead' }));
    expect(onReset).not.toHaveBeenCalled();
    expect(screen.getByText(/replaced by the provided starter code/)).toBeVisible();

    await user.click(screen.getByRole('button', { name: 'Keep my code' }));
    expect(screen.queryByText(/replaced by the provided/)).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Start from the provided code instead' }));
    await user.click(screen.getByRole('button', { name: 'Use the provided code' }));
    expect(onReset).toHaveBeenCalledTimes(1);
  });

  it('uses the mode vocabulary and shows a failed reset', async () => {
    render(
      withMode(
        'rpg',
        <CarriedFiles title="The Drowned Index" onReset={vi.fn()} error="Network error" />,
      ),
    );

    expect(screen.getByRole('note')).toHaveTextContent(
      'You carry your work from The Drowned Index into this quest.',
    );
    await userEvent
      .setup()
      .click(screen.getByRole('button', { name: 'Start from the provided code instead' }));
    expect(screen.getByRole('button', { name: 'Set it down' })).toBeVisible();
    expect(screen.getByRole('alert')).toHaveTextContent('Network error');
  });

  it('offers the starter as a bordered secondary button, not as plain text', () => {
    render(withMode('professional', <CarriedFiles title="Hybrid retrieval" onReset={vi.fn()} />));

    const reset = screen.getByRole('button', { name: 'Start from the provided code instead' });
    expect(reset).toHaveClass('border-line-strong');
    expect(reset).not.toHaveClass('text-ink-secondary');
  });
});
