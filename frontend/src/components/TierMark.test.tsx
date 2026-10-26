import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { withMode } from '../test/render';
import { TierMark } from './TierMark';

describe('TierMark', () => {
  it.each([
    ['professional', 'Capstone', 12],
    ['rpg', 'Boss', 14],
  ] as const)('labels a capstone in %s mode as "%s" with its own glyph', (mode, label, size) => {
    const { container } = render(withMode(mode, <TierMark tier="capstone" />));

    expect(screen.getByText(label)).toBeVisible();
    const svg = container.querySelector('svg');
    expect(svg).toHaveAttribute('aria-hidden', 'true');
    expect(svg).toHaveAttribute('viewBox', `0 0 ${size} ${size}`);
    expect(container.firstElementChild).toHaveClass('text-tier-capstone');
  });

  it.each(['professional', 'rpg'] as const)(
    'draws a capstone differently from every graded tier (%s)',
    (mode) => {
      const markup = (tier: string) =>
        render(withMode(mode, <TierMark tier={tier} />)).container.querySelector('svg')?.innerHTML;
      const capstone = markup('capstone');
      for (const tier of ['beginner', 'intermediate', 'advanced'])
        expect(markup(tier)).not.toBe(capstone);
    },
  );

  it('keeps the word for screen readers when the label is hidden', () => {
    render(withMode('rpg', <TierMark tier="capstone" showLabel={false} />));

    expect(screen.getByText('Boss')).toHaveClass('sr-only');
  });

  it('still marks graded tiers by count', () => {
    const { container } = render(withMode('professional', <TierMark tier="advanced" />));

    expect(screen.getByText('Advanced')).toBeVisible();
    expect(container.querySelectorAll('rect[opacity="1"]')).toHaveLength(3);
  });
});
