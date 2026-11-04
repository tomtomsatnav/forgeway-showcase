import { describe, expect, it } from 'vitest';

import config from '../../tailwind.config';

describe('tailwind theme', () => {
  it('has no colour named like a font size, so `text-<size>` never also sets a colour', () => {
    // A colour called `base` once made `text-base` paint text in the page background colour.
    const colours = Object.keys(config.theme.colors);
    const sizes = Object.keys(config.theme.fontSize);
    expect(colours.filter((name) => sizes.includes(name))).toEqual([]);
  });
});
