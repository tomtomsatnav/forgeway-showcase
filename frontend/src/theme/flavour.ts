import { useQuery } from '@tanstack/react-query';

import { rpgFlavourQuery } from '../api/hooks';
import type { BossFlavour, Mode, PathFlavour, ThemeFlavour } from '../api/types';
import { useTheme } from './useTheme';

export interface ZoneFlavour {
  name: string;
  epithet: string;
  lore: string;
}

/** Themed names for branches and exercises. Empty in a mode with no flavour, or until it loads. */
export interface Flavour {
  zone: (branchId: string) => ZoneFlavour | undefined;
  quest: (exerciseId: string) => string | undefined;
  path: (pathId: string) => PathFlavour | undefined;
  /** The boss behind a capstone exercise, if the flavour names one. */
  boss: (exerciseId: string) => BossFlavour | undefined;
}

const NONE: Flavour = {
  zone: () => undefined,
  quest: () => undefined,
  path: () => undefined,
  boss: () => undefined,
};

const fromData = (data: ThemeFlavour | undefined): Flavour =>
  data === undefined
    ? NONE
    : {
        zone: (branchId) => data.branches[branchId],
        quest: (exerciseId) => data.quests[exerciseId],
        path: (pathId) => data.paths[pathId],
        boss: (exerciseId) => data.bosses[exerciseId],
      };

/** How each mode reads the flavour response; professional deliberately ignores it. */
const READERS: Record<Mode, (data: ThemeFlavour | undefined) => Flavour> = {
  professional: () => NONE,
  rpg: fromData,
};

export function useFlavour(): Flavour {
  const { mode } = useTheme();
  const flavour = useQuery({ ...rpgFlavourQuery, enabled: mode === 'rpg' });
  return READERS[mode](flavour.data);
}
