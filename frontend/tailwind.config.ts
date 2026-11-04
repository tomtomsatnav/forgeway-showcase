import type { Config } from 'tailwindcss';

/** Every colour, font and radius resolves to a semantic CSS variable from src/styles/tokens.css. */
const token = (name: string) => `var(--${name})`;

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    colors: {
      transparent: 'transparent',
      current: 'currentColor',
      page: token('surface-base'),
      raised: token('surface-raised'),
      sunken: token('surface-sunken'),
      ink: token('text-primary'),
      'ink-secondary': token('text-secondary'),
      'ink-muted': token('text-muted'),
      'line-subtle': token('border-subtle'),
      'line-strong': token('border-strong'),
      accent: token('accent'),
      'accent-strong': token('accent-strong'),
      'accent-soft': token('accent-soft'),
      'on-accent': token('text-on-accent'),
      success: token('success'),
      'success-soft': token('success-soft'),
      danger: token('danger'),
      'danger-soft': token('danger-soft'),
      warning: token('warning'),
      'warning-soft': token('warning-soft'),
      'tier-beginner': token('tier-beginner'),
      'tier-intermediate': token('tier-intermediate'),
      'tier-advanced': token('tier-advanced'),
      'tier-capstone': token('tier-capstone'),
      focus: token('focus-ring'),
    },
    fontFamily: {
      display: token('font-display'),
      ui: token('font-ui'),
      reading: token('font-reading'),
      mono: token('font-mono'),
    },
    fontSize: {
      xs: ['0.75rem', { lineHeight: '1.25rem' }],
      sm: ['0.875rem', { lineHeight: '1.375rem' }],
      base: ['1rem', { lineHeight: '1.5rem' }],
      lg: ['1.25rem', { lineHeight: '1.6' }],
      xl: ['1.5625rem', { lineHeight: '1.3' }],
      '2xl': ['1.9375rem', { lineHeight: '1.2' }],
      '3xl': ['2.4375rem', { lineHeight: '1.15' }],
      '4xl': ['3.0625rem', { lineHeight: '1.1' }],
    },
    borderRadius: {
      none: '0',
      control: token('radius-control'),
      panel: token('radius-panel'),
      full: '9999px',
    },
    boxShadow: { raised: token('shadow-raised'), none: 'none' },
    transitionDuration: {
      fast: token('dur-fast'),
      base: token('dur-base'),
    },
    transitionTimingFunction: { DEFAULT: token('ease') },
    extend: {
      spacing: { 18: '4.5rem' },
      maxWidth: { measure: '68ch', page: '1200px' },
      letterSpacing: { label: '0.06em' },
      screens: { xs: '480px', xl: '1280px' },
    },
  },
  plugins: [],
} satisfies Config;
