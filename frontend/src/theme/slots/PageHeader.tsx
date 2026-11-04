import { CapstoneIcon } from '../../components/TierMark';
import { useFlavour } from '../flavour';
import { useLexicon } from '../useTheme';
import type { PageHeaderProps } from './types';

/** Professional: title and a one-line summary on a hairline. */
export function ProfessionalPageHeader({ title, summary, capstone, project }: PageHeaderProps) {
  const lexicon = useLexicon();
  return (
    <header className="border-b border-line-strong pb-4">
      {project !== undefined && (
        <p className="label-caps m-0 mb-1 text-ink-muted">
          {lexicon.projectLabel} · {project}
        </p>
      )}
      {capstone && (
        <p className="label-caps m-0 mb-1 flex items-center gap-2 text-tier-capstone">
          <CapstoneIcon />
          {lexicon.capstoneLabel}
        </p>
      )}
      <h1 className="m-0 text-2xl sm:text-3xl">{title}</h1>
      {summary !== undefined && (
        <p className="m-0 mt-1 max-w-measure text-base text-ink-secondary">{summary}</p>
      )}
      {capstone && (
        <p className="m-0 mt-1 max-w-measure text-base text-ink-secondary">
          {lexicon.capstoneNote}
        </p>
      )}
    </header>
  );
}

function Rule() {
  return (
    <svg aria-hidden="true" viewBox="0 0 240 12" className="h-3 w-full max-w-60 text-line-strong">
      <line x1="0" y1="6" x2="104" y2="6" stroke="currentColor" strokeWidth="1" />
      <path d="M120 0.5 L126 6 L120 11.5 L114 6 Z" fill="currentColor" />
      <line x1="136" y1="6" x2="240" y2="6" stroke="currentColor" strokeWidth="1" />
    </svg>
  );
}

/** RPG: title in display small caps between ornamental rules. */
export function RpgPageHeader({ title, summary, exerciseId, capstone, project }: PageHeaderProps) {
  const flavour = useFlavour();
  const lexicon = useLexicon();
  const boss = capstone && exerciseId !== undefined ? flavour.boss(exerciseId) : undefined;
  const quest = boss?.name ?? (exerciseId === undefined ? undefined : flavour.quest(exerciseId));
  return (
    <header className="flex flex-col items-center gap-3 py-2 text-center">
      <Rule />
      {project !== undefined && (
        <p className="label-caps m-0 text-ink-muted">
          {lexicon.projectLabel} · {project}
        </p>
      )}
      {capstone && (
        <p className="label-caps m-0 flex items-center gap-2 text-tier-capstone">
          <CapstoneIcon />
          {lexicon.capstoneLabel}
        </p>
      )}
      <h1 className="small-caps-heading m-0 text-2xl sm:text-3xl">{quest ?? title}</h1>
      {boss && <p className="m-0 font-reading text-lg italic text-ink-secondary">{boss.epithet}</p>}
      {boss && <p className="m-0 max-w-measure font-reading text-base text-ink">{boss.lore}</p>}
      {quest !== undefined && <p className="m-0 text-lg text-ink-secondary">{title}</p>}
      {summary !== undefined && (
        <p className="m-0 max-w-measure text-base text-ink-secondary">{summary}</p>
      )}
      {capstone && (
        <p className="m-0 max-w-measure text-sm text-ink-muted">{lexicon.capstoneNote}</p>
      )}
      <Rule />
    </header>
  );
}
