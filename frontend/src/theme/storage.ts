import type { ColourScheme, Mode } from '../api/types';

const KEY = 'lattice.theme';

export interface ThemePreference {
  mode: Mode;
  scheme: ColourScheme;
}

export const DEFAULT_PREFERENCE: ThemePreference = { mode: 'professional', scheme: 'system' };

/** Local fallback used before sign-in. Storage can be blocked, so every access is guarded. */
export function readPreference(): ThemePreference {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw === null) return DEFAULT_PREFERENCE;
    const parsed = JSON.parse(raw) as Partial<ThemePreference>;
    return {
      mode: parsed.mode === 'rpg' ? 'rpg' : 'professional',
      scheme: parsed.scheme === 'light' || parsed.scheme === 'dark' ? parsed.scheme : 'system',
    };
  } catch {
    return DEFAULT_PREFERENCE;
  }
}

export function writePreference(preference: ThemePreference): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(preference));
  } catch {
    /* storage unavailable: the choice lasts for this page view only */
  }
}
