import { Link } from '@tanstack/react-router';

import { useTheme } from '../theme/useTheme';

const PRIMER = 'python-primer';

/** A link to the Python primer: its track in the syllabus, or its zone in the atlas. */
export function PrimerLink() {
  const { mode, lexicon } = useTheme();
  return (
    <Link
      to="/"
      search={mode === 'rpg' ? { zone: PRIMER } : {}}
      hash={mode === 'rpg' ? undefined : `track-${PRIMER}`}
      className="text-accent-strong underline underline-offset-2"
    >
      {lexicon.primerLink}
    </Link>
  );
}
