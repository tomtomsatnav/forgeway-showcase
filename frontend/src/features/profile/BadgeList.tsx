import { Award, ChevronRight, CircleDashed } from 'lucide-react';

import type { BadgeStatus } from '../../api/types';
import { useFlavour } from '../../theme/flavour';
import { toBadgeRule } from '../../theme/lexicon';
import { useLexicon } from '../../theme/useTheme';

const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });

/** Earned badges first, newest first, each with its date; the rest say how they are earned. */
export function sortBadges(badges: readonly BadgeStatus[]): BadgeStatus[] {
  const earned = badges
    .filter((badge) => badge.earned)
    .sort((a, b) => (b.awarded_at ?? '').localeCompare(a.awarded_at ?? ''));
  return [...earned, ...badges.filter((badge) => !badge.earned)];
}

const LIST = 'm-0 list-none border-t border-line-subtle p-0';

/** One badge as a ruled row: a glyph and a word say whether it is earned, never colour alone. */
function BadgeRow({ badge }: { badge: BadgeStatus }) {
  const lexicon = useLexicon();
  const flavour = useFlavour();
  // Worded by the mode from the criterion, so RPG says quests and bosses, not exercises.
  const rule = toBadgeRule(badge.requirement, (id, title) => flavour.zone(id)?.name ?? title);
  const requirement =
    rule !== null
      ? lexicon.badgeRequirement(rule, badge.earned)
      : badge.earned
        ? badge.description
        : badge.criterion;
  const Icon = badge.earned ? Award : CircleDashed;
  return (
    <li
      data-earned={badge.earned}
      className="grid grid-cols-[1.25rem_minmax(0,1fr)] gap-x-3 gap-y-1 border-b border-line-subtle py-3 sm:grid-cols-[1.25rem_minmax(0,1fr)_auto] sm:gap-x-4"
    >
      <Icon
        aria-hidden="true"
        className={`mt-0.5 h-5 w-5 ${badge.earned ? 'text-accent' : 'text-ink-muted'}`}
      />
      <div className="min-w-0">
        <h3 className="m-0 text-base">{badge.title}</h3>
        <p className="m-0 text-sm text-ink-secondary">{requirement}</p>
      </div>
      {badge.earned && badge.awarded_at !== null ? (
        <p className="tabular col-start-2 m-0 text-sm font-medium text-accent-strong sm:col-start-auto sm:text-right">
          {lexicon.badgeEarned(formatDate(badge.awarded_at))}
        </p>
      ) : (
        <p className="col-start-2 m-0 text-sm font-medium text-ink-secondary sm:col-start-auto sm:text-right">
          {lexicon.badgeNotEarned}
        </p>
      )}
    </li>
  );
}

/**
 * The badges as a ruled list: those earned first, newest first; the rest folded under a
 * disclosure ("12 more to earn") so the earned ones are not lost among them.
 */
export function BadgeList({ badges }: { badges: readonly BadgeStatus[] }) {
  const lexicon = useLexicon();
  const sorted = sortBadges(badges);
  const earned = sorted.filter((badge) => badge.earned);
  const rest = sorted.filter((badge) => !badge.earned);
  return (
    <div className="space-y-3">
      {earned.length > 0 && (
        <ul className={LIST}>
          {earned.map((badge) => (
            <BadgeRow key={badge.id} badge={badge} />
          ))}
        </ul>
      )}
      {rest.length > 0 && (
        <details className="group">
          <summary className="inline-flex min-h-11 cursor-pointer list-none items-center gap-2 font-medium text-ink hover:underline [&::-webkit-details-marker]:hidden">
            <ChevronRight
              aria-hidden="true"
              className="h-4 w-4 transition-transform duration-fast group-open:rotate-90"
            />
            <span className="tabular">{lexicon.badgesToEarn(rest.length)}</span>
          </summary>
          <ul className={LIST}>
            {rest.map((badge) => (
              <BadgeRow key={badge.id} badge={badge} />
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
