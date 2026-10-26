import { useLexicon } from '../theme/useTheme';
import { problemMessage } from './errors';

/** `problemMessage` bound to the current mode's lexicon. */
export function useProblemMessage(): (error: unknown) => string {
  const lexicon = useLexicon();
  return (error) => problemMessage(error, lexicon);
}
