import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { withMode } from '../test/render';
import { HintReveal } from './HintReveal';

describe('HintReveal', () => {
  it('asks for confirmation, stating the bonus cost, before the first reveal', async () => {
    const onReveal = vi.fn();
    const user = userEvent.setup();
    render(withMode('professional', <HintReveal revealed={[]} total={2} onReveal={onReveal} />));

    await user.click(screen.getByRole('button', { name: /Reveal a hint/ }));
    expect(onReveal).not.toHaveBeenCalled();
    expect(screen.getByText(/forfeits the \+20% no-hint bonus/)).toBeVisible();

    await user.click(screen.getByRole('button', { name: 'Keep trying' }));
    expect(screen.queryByText(/forfeits/)).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Reveal a hint/ }));
    await user.click(screen.getByRole('button', { name: 'Reveal anyway' }));
    expect(onReveal).toHaveBeenCalledTimes(1);
  });

  it('uses the mode vocabulary', async () => {
    render(withMode('rpg', <HintReveal revealed={[]} total={1} onReveal={vi.fn()} />));

    await userEvent
      .setup()
      .click(screen.getByRole('button', { name: /Unroll a scroll of insight/ }));
    expect(screen.getByText(/Unrolling a scroll of insight forfeits/)).toBeVisible();
  });

  it('shows revealed hints and reveals the next one without asking again', async () => {
    const onReveal = vi.fn();
    render(
      withMode(
        'professional',
        <HintReveal revealed={['Use a `Message`.']} total={2} onReveal={onReveal} />,
      ),
    );

    expect(screen.getByText('Message')).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole('button', { name: /Reveal a hint/ }));
    expect(onReveal).toHaveBeenCalledTimes(1);
  });

  it('offers nothing once every hint is revealed', () => {
    render(
      withMode('professional', <HintReveal revealed={['one']} total={1} onReveal={vi.fn()} />),
    );

    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });
});
