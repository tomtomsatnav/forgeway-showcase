import { Link } from '@tanstack/react-router';
import { Award, FileBadge, Flame, Sparkles } from 'lucide-react';

import type { Progression } from '../../api/types';
import { useLexicon } from '../useTheme';

/** True when a graded attempt moved anything beyond XP: a badge, a certificate, a talent point or the streak. */
export function hasNews(progression: Progression): boolean {
  return (
    progression.badges_awarded.length > 0 ||
    progression.certificates_issued.length > 0 ||
    progression.talent_points_gained > 0 ||
    (progression.streak?.current ?? 0) > 0
  );
}

/**
 * Badges won, certificates earned, talent points gained and the streak, as a few short lines each with an icon and
 * words. Shared by both completion moments and the results panel, so a failed attempt that
 * earned a badge says so too.
 */
export function ProgressionNews({ progression }: { progression: Progression }) {
  const lexicon = useLexicon();
  if (!hasNews(progression)) return null;
  const {
    badges_awarded: badges,
    certificates_issued: certificates,
    talent_points_gained: points,
    streak,
  } = progression;
  return (
    <ul aria-label="What else changed" className="m-0 list-none space-y-1 p-0 text-sm text-ink">
      {badges.map((badge) => (
        <li key={badge.id} className="flex items-start gap-2">
          <Award aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
          <span>
            <span className="font-semibold">{lexicon.badgeAwarded(badge.title)}</span>
            <span className="text-ink-secondary"> · {badge.description}</span>
          </span>
        </li>
      ))}
      {certificates.map((certificate) => (
        <li key={certificate.id} className="flex items-start gap-2">
          <FileBadge aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
          <span>
            <span className="font-semibold">
              {lexicon.certificateEarned(certificate.branch_title, certificate.includes_capstone)}
            </span>
            {' · '}
            <Link
              to="/profile"
              hash="certificates"
              className="text-accent-strong underline underline-offset-2"
            >
              {lexicon.certificatesLink}
            </Link>
          </span>
        </li>
      ))}
      {points > 0 && (
        <li className="flex items-center gap-2">
          <Sparkles aria-hidden="true" className="h-4 w-4 shrink-0 text-accent" />
          <span className="tabular">{lexicon.talentPointsGained(points)}</span>
        </li>
      )}
      {streak != null && streak.current > 0 && (
        <li className="flex items-center gap-2">
          <Flame aria-hidden="true" className="h-4 w-4 shrink-0 text-accent" />
          <span className="tabular">{lexicon.streakCurrent(streak.current)}</span>
        </li>
      )}
    </ul>
  );
}
