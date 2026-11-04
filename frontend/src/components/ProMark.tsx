import { useMe } from '../api/hooks';
import { useLexicon } from '../theme/useTheme';

/**
 * The mark on Pro content: "Pro" (professional) or "Guild · Pro" (RPG), so the plan reads the
 * same in both modes. A small outlined tag in the accent; the words carry the meaning, and screen
 * readers also hear what it stands for. It marks what a plan would add, so a learner whose plan
 * already includes Pro (pro or team) does not see it.
 */
export function ProMark() {
  const lexicon = useLexicon();
  const me = useMe();
  if (me.data != null && me.data.plan !== 'free') return null;
  return (
    <span
      data-pro-mark=""
      title={lexicon.proMarkDescription}
      className="label-caps inline-flex items-center whitespace-nowrap rounded-control border border-accent-strong px-1.5 py-px text-accent-strong"
    >
      {lexicon.proMark}
      <span className="sr-only">{`, ${lexicon.proMarkDescription}`}</span>
    </span>
  );
}
