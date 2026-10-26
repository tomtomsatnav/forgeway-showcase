import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { withMode } from '../../test/render';
import { ResetCode } from './ResetCode';

describe('ResetCode', () => {
  it('resets only after a confirm step that says progress is kept', async () => {
    const onReset = vi.fn();
    const user = userEvent.setup();
    render(withMode('professional', <ResetCode onReset={onReset} />));

    await user.click(screen.getByRole('button', { name: 'Reset code' }));
    expect(onReset).not.toHaveBeenCalled();
    expect(screen.getByText(/Passed attempts and XP are not affected/)).toBeVisible();

    await user.click(screen.getByRole('button', { name: 'Keep my code' }));
    expect(screen.queryByText(/replaced by the starter code/)).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Reset code' }));
    await user.click(screen.getByRole('button', { name: 'Reset to the starter code' }));
    expect(onReset).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button', { name: 'Reset code' })).toBeVisible();
  });

  it('speaks the mode and shows a failed reset even after the confirm closes', () => {
    render(withMode('rpg', <ResetCode onReset={vi.fn()} error="Network error" />));

    expect(screen.getByRole('button', { name: 'Begin anew' })).toBeVisible();
    expect(screen.getByRole('alert')).toHaveTextContent('Network error');
  });
});
