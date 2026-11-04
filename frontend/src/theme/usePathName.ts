import { useFlavour } from './flavour';
import { useLexicon } from './useTheme';

/**
 * How a path (specialisation) is named in the current mode: the RPG flavour's class name, else
 * the lexicon's, else the title the API gave it.
 */
export function usePathName(): (pathId: string, fallback?: string) => string {
  const flavour = useFlavour();
  const { pathNames } = useLexicon();
  return (pathId, fallback) =>
    flavour.path(pathId)?.name ?? pathNames[pathId] ?? fallback ?? pathId;
}
