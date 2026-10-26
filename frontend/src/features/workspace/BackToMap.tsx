import { Link } from '@tanstack/react-router';
import { ArrowLeft } from 'lucide-react';

import { useTheme } from '../../theme/useTheme';

/** Back to the map; in RPG mode, to the exercise's own zone rather than the whole world. */
export function BackToMap({ branch }: { branch?: string }) {
  const { mode, lexicon } = useTheme();
  const zone = mode === 'rpg' ? branch : undefined;
  return (
    <Link
      to="/"
      search={zone === undefined ? {} : { zone }}
      className="inline-flex min-h-11 items-center gap-2 text-accent-strong underline underline-offset-2"
    >
      <ArrowLeft aria-hidden="true" className="h-4 w-4" />
      {lexicon.backToMap}
    </Link>
  );
}
