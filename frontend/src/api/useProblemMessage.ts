import { useQueryClient } from '@tanstack/react-query';

import { useLexicon } from '../theme/useTheme';
import { problemMessage } from './errors';
import { queryKeys } from './hooks';

/** An older server (or a test) may send no `billing` block: that is billing off. */
type CachedConfig = { billing?: { enabled?: boolean } | null } | undefined;

/** `problemMessage` bound to the current mode's lexicon (and, with billing on, its wording). */
export function useProblemMessage(): (error: unknown) => string {
  const lexicon = useLexicon();
  // Read from the cache, never fetched from here: the app loads the config at start.
  const config = useQueryClient().getQueryData<CachedConfig>(queryKeys.config);
  const words =
    config?.billing?.enabled === true
      ? {
          ...lexicon,
          problems: { ...lexicon.problems, planRequired: lexicon.billing.planRequired },
        }
      : lexicon;
  return (error) => problemMessage(error, words);
}
