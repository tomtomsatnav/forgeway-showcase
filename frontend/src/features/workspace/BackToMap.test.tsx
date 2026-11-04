import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { renderInRouter, withMode } from '../../test/render';
import { BackToMap } from './BackToMap';

describe('BackToMap', () => {
  it('returns to the exercise zone in RPG mode', async () => {
    await renderInRouter(withMode('rpg', <BackToMap branch="retrieval" />));

    expect(await screen.findByRole('link', { name: 'Back to the atlas' })).toHaveAttribute(
      'href',
      '/?zone=retrieval',
    );
  });

  it('returns to the syllabus in professional mode', async () => {
    await renderInRouter(withMode('professional', <BackToMap branch="retrieval" />));

    expect(await screen.findByRole('link', { name: 'Back to the syllabus' })).toHaveAttribute(
      'href',
      '/',
    );
  });

  it('returns to the world when the branch is unknown', async () => {
    await renderInRouter(withMode('rpg', <BackToMap />));

    expect(await screen.findByRole('link', { name: 'Back to the atlas' })).toHaveAttribute(
      'href',
      '/',
    );
  });
});
