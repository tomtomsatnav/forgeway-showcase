import { useEffect, useRef, useState, useSyncExternalStore, type ReactNode } from 'react';

import { useMe, useUpdateProfile } from '../api/hooks';
import type { ColourScheme, Mode, Profile } from '../api/types';
import { LEXICONS } from './lexicon';
import { readPreference, writePreference, type ThemePreference } from './storage';
import { ThemeContext } from './useTheme';

const DARK_QUERY = '(prefers-color-scheme: dark)';

function subscribeToSystemScheme(onChange: () => void): () => void {
  if (typeof matchMedia !== 'function') return () => undefined;
  const query = matchMedia(DARK_QUERY);
  query.addEventListener('change', onChange);
  return () => {
    query.removeEventListener('change', onChange);
  };
}

function systemPrefersDark(): boolean {
  return typeof matchMedia === 'function' && matchMedia(DARK_QUERY).matches;
}

function fromProfile(profile: Profile): ThemePreference {
  return {
    mode: profile.mode === 'rpg' ? 'rpg' : 'professional',
    scheme:
      profile.colour_scheme === 'light' || profile.colour_scheme === 'dark'
        ? profile.colour_scheme
        : 'system',
  };
}

/**
 * Owns mode and colour scheme. The choice is written to <html data-mode data-scheme>, kept in
 * localStorage as the pre-sign-in fallback, and saved to the profile when signed in. The stored
 * profile is adopted when it loads, except for anything the learner chose before it arrived:
 * `/api/auth/me` can resolve after the header toggles are usable, and an explicit choice must
 * not be reverted by it. Those choices are kept and then saved to the profile.
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const me = useMe();
  const updateProfile = useUpdateProfile();
  const [preference, setPreference] = useState<ThemePreference>(readPreference);
  const [syncedUserId, setSyncedUserId] = useState<string | null>(null);
  // Choices made while no profile was loaded: they win over it, and are saved once it is.
  const [early, setEarly] = useState<Partial<ThemePreference>>({});
  const [toSave, setToSave] = useState<Partial<ThemePreference> | null>(null);
  const saved = useRef<Partial<ThemePreference> | null>(null);
  const systemDark = useSyncExternalStore(subscribeToSystemScheme, systemPrefersDark);

  const user = me.data;
  if (user && user.id !== syncedUserId) {
    setSyncedUserId(user.id);
    setPreference({ ...fromProfile(user.profile), ...early });
    setToSave(early);
    setEarly({});
  }

  const resolvedScheme =
    preference.scheme === 'system' ? (systemDark ? 'dark' : 'light') : preference.scheme;

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.mode = preference.mode;
    root.dataset.scheme = resolvedScheme;
    writePreference(preference);
  }, [preference, resolvedScheme]);

  const signedIn = user != null;
  const { mutate } = updateProfile;

  useEffect(() => {
    if (toSave === null || saved.current === toSave) return;
    saved.current = toSave;
    if (toSave.mode !== undefined || toSave.scheme !== undefined)
      mutate({ mode: toSave.mode, colour_scheme: toSave.scheme });
  }, [toSave, mutate]);

  const setMode = (mode: Mode) => {
    setPreference((current) => ({ ...current, mode }));
    if (signedIn) mutate({ mode });
    else setEarly((current) => ({ ...current, mode }));
  };
  const setScheme = (scheme: ColourScheme) => {
    setPreference((current) => ({ ...current, scheme }));
    if (signedIn) mutate({ colour_scheme: scheme });
    else setEarly((current) => ({ ...current, scheme }));
  };

  return (
    <ThemeContext.Provider
      value={{
        mode: preference.mode,
        scheme: preference.scheme,
        resolvedScheme,
        lexicon: LEXICONS[preference.mode],
        setMode,
        setScheme,
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
}
