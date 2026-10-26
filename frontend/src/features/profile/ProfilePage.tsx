import { Flame } from 'lucide-react';
import { useEffect, useState, type ReactNode } from 'react';

import { errorMessage } from '../../api/errors';
import {
  useBadges,
  useCertificates,
  useLearnerMap,
  usePathProfile,
  useTalentActions,
  useTalents,
} from '../../api/hooks';
import type { LearnerMap, TalentTree as Tree } from '../../api/types';
import { ProgressRule } from '../../components/ProgressRule';
import { PageHeader, TalentTree } from '../../theme/slots';
import { usePathName } from '../../theme/usePathName';
import { useLexicon } from '../../theme/useTheme';
import { AccountData } from './AccountData';
import { BadgeList } from './BadgeList';
import { Certificates } from './Certificates';
import { PathChoice } from './PathChoice';
import { TimeZoneField } from './TimeZoneField';

function Section({
  id,
  title,
  anchor,
  children,
}: {
  id: string;
  title: string;
  /** Makes the section a link target, such as /profile#certificates. */
  anchor?: string;
  children: ReactNode;
}) {
  return (
    <section
      id={anchor}
      aria-labelledby={id}
      className="space-y-4 border-t border-line-subtle pt-6"
    >
      <h2 id={id} className="m-0 text-xl first-letter:uppercase">
        {title}
      </h2>
      {children}
    </section>
  );
}

function LevelSection({ level }: { level: LearnerMap['level'] }) {
  const lexicon = useLexicon();
  const span = level.next_level_at === null ? 0 : level.next_level_at - level.level_floor;
  return (
    // The level itself is named once, in the summary above; this is the way to the next one.
    <div className="max-w-md">
      <ProgressRule
        value={span === 0 ? 1 : level.total_xp - level.level_floor}
        max={span === 0 ? 1 : span}
        label={`Experience towards ${lexicon.level} ${level.level + 1}`}
        caption={
          level.next_level_at === null
            ? lexicon.xpLabel(level.total_xp)
            : `${level.total_xp} / ${level.next_level_at} XP`
        }
      />
    </div>
  );
}

function StreakSection({ streak }: { streak: LearnerMap['streak'] }) {
  const lexicon = useLexicon();
  return (
    <div className="space-y-1">
      <p className="tabular m-0 flex items-center gap-2 text-lg font-semibold">
        <Flame aria-hidden="true" className="h-5 w-5 text-accent" />
        {lexicon.streakCurrent(streak.current)}
      </p>
      <p className="tabular m-0 text-sm text-ink-secondary">
        {lexicon.streakLongest(streak.longest)}
      </p>
    </div>
  );
}

/** Allocation, deallocation and respec for the talent tree slot, with a 409 shown inline. */
function TalentSection({ tree, map }: { tree: Tree; map: LearnerMap }) {
  const lexicon = useLexicon();
  const pathName = usePathName();
  const { allocate, deallocate, respec } = useTalentActions();
  const [problem, setProblem] = useState<string | null>(null);

  const exercises = new Map(
    map.branches.flatMap((branch) => branch.exercises).map((exercise) => [exercise.id, exercise]),
  );
  const titleOf = (nodeId: string) => tree.nodes.find((n) => n.id === nodeId)?.title ?? nodeId;

  const run = (nodeId: string, action: typeof allocate) => {
    setProblem(null);
    action.mutate(nodeId, {
      onError: (error) => {
        setProblem(`${titleOf(nodeId)}: ${errorMessage(error)}`);
      },
    });
  };

  const pendingNode = allocate.isPending
    ? allocate.variables
    : deallocate.isPending
      ? deallocate.variables
      : null;

  return (
    <TalentTree
      tree={tree}
      exerciseTitle={(id) => exercises.get(id)?.title ?? id}
      subtreeName={(subtree) => (subtree === 'general' ? lexicon.talentGeneral : pathName(subtree))}
      pendingNode={pendingNode}
      respeccing={respec.isPending}
      problem={problem}
      onAllocate={(nodeId) => {
        run(nodeId, allocate);
      }}
      onDeallocate={(nodeId) => {
        run(nodeId, deallocate);
      }}
      onRespec={() => {
        setProblem(null);
        respec.mutate(undefined, {
          onError: (error) => {
            setProblem(errorMessage(error));
          },
        });
      }}
    />
  );
}

/**
 * The profile (RPG: the character sheet): level, path, titles, streak, badges, certificates,
 * talents, then settings (the time zone, and downloading or deleting your data).
 */
export function ProfilePage() {
  const lexicon = useLexicon();
  const map = useLearnerMap();
  const profile = usePathProfile();
  const talents = useTalents();
  const badges = useBadges();
  const certificates = useCertificates();
  const pathName = usePathName();

  const ready = Boolean(
    map.data && profile.data && talents.data && badges.data && certificates.data,
  );
  // The sections arrive after the first render, so the browser cannot scroll to the anchor itself.
  useEffect(() => {
    if (ready && window.location.hash === '#certificates') {
      document.getElementById('certificates')?.scrollIntoView();
    }
  }, [ready]);

  const failed = [map, profile, talents, badges, certificates].find((query) => query.isError);
  if (failed?.error) {
    return (
      <p role="alert" className="mx-auto max-w-page px-4 py-12 text-danger sm:px-6">
        {errorMessage(failed.error)}
      </p>
    );
  }
  if (!map.data || !profile.data || !talents.data || !badges.data || !certificates.data) {
    return (
      <p role="status" className="mx-auto max-w-page px-4 py-12 text-ink-muted sm:px-6">
        Loading…
      </p>
    );
  }

  const earned = badges.data.badges.filter((badge) => badge.earned).length;
  return (
    <div className="mx-auto max-w-page space-y-10 px-4 py-8 sm:px-6">
      <PageHeader
        title={lexicon.profile}
        summary={`${pathName(profile.data.path)}. ${lexicon.profileSummary(map.data.level.level)}`}
      />
      <LevelSection level={map.data.level} />
      <Section id="path-heading" title={lexicon.specialisation}>
        <PathChoice profile={profile.data} tree={talents.data} />
      </Section>
      <Section id="titles-heading" title={lexicon.titlesHeading}>
        {profile.data.titles.length === 0 ? (
          <p className="m-0 text-ink-secondary">{lexicon.titlesNone}</p>
        ) : (
          <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
            {profile.data.titles.map((title) => (
              <li
                key={title}
                className="rounded-control border border-line-strong bg-raised px-3 py-1 text-sm font-medium"
              >
                {title}
              </li>
            ))}
          </ul>
        )}
      </Section>
      <Section id="streak-heading" title={lexicon.streak}>
        <StreakSection streak={map.data.streak} />
      </Section>
      <Section id="badges-heading" title={lexicon.badgePlural}>
        <p className="tabular m-0 text-sm text-ink-secondary">
          {lexicon.badgesSummary(earned, badges.data.badges.length)}
        </p>
        <BadgeList badges={badges.data.badges} />
      </Section>
      <Section id="certificates-heading" anchor="certificates" title={lexicon.certificatesHeading}>
        <Certificates certificates={certificates.data.certificates} />
      </Section>
      <Section id="talents-heading" title={lexicon.talentTree}>
        <p className="m-0 max-w-measure text-sm text-ink-secondary">{lexicon.talentTreeSummary}</p>
        <TalentSection tree={talents.data} map={map.data} />
      </Section>
      <Section id="settings-heading" title={lexicon.settingsHeading}>
        <TimeZoneField key={profile.data.time_zone} current={profile.data.time_zone} />
        <AccountData />
      </Section>
    </div>
  );
}
