import { createContext, useContext } from 'react';

import type { ColourScheme, Mode } from '../api/types';
import type { Lexicon } from './lexicon';

export interface ThemeContextValue {
  mode: Mode;
  /** The learner's choice, which may be "system". */
  scheme: ColourScheme;
  /** What is actually applied to the page. */
  resolvedScheme: 'light' | 'dark';
  lexicon: Lexicon;
  setMode: (mode: Mode) => void;
  setScheme: (scheme: ColourScheme) => void;
}

export const ThemeContext = createContext<ThemeContextValue | null>(null);

export function useTheme(): ThemeContextValue {
  const value = useContext(ThemeContext);
  if (value === null) throw new Error('useTheme must be used inside <ThemeProvider>');
  return value;
}

export function useLexicon(): Lexicon {
  return useTheme().lexicon;
}
