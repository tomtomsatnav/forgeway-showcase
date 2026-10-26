import { Check, CircleDot, Lock, type LucideIcon } from 'lucide-react';

import type { ExerciseStatus } from '../api/types';
import { useLexicon } from '../theme/useTheme';

const ICONS: Record<ExerciseStatus, LucideIcon> = {
  locked: Lock,
  available: CircleDot,
  passed: Check,
};

const COLOURS: Record<ExerciseStatus, string> = {
  locked: 'text-ink-muted',
  available: 'text-accent',
  passed: 'text-success',
};

/** Locked, available or passed as an icon and a word, never colour alone. */
export function StatusMark({ status }: { status: ExerciseStatus }) {
  const Icon = ICONS[status];
  const lexicon = useLexicon();
  return (
    <span className={`inline-flex items-center gap-1.5 ${COLOURS[status]}`}>
      <Icon aria-hidden="true" className="h-4 w-4 shrink-0" />
      <span className="label-caps">{lexicon.status[status]}</span>
    </span>
  );
}
