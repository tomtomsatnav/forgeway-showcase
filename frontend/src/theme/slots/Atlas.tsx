import { Link, useLinkProps, useSearch } from '@tanstack/react-router';
import { ArrowLeft } from 'lucide-react';
import { useEffect, useRef, useSyncExternalStore } from 'react';

import type { BossFlavour, BranchSummary, ExerciseSummary } from '../../api/types';
import { toTier } from '../../api/types';
import { ProgressRule } from '../../components/ProgressRule';
import { ProMark } from '../../components/ProMark';
import { BossSigilGlyph, SigilGlyphs, TIER_INDEX } from '../../components/TierMark';
import { useFlavour, type Flavour } from '../flavour';
import type { Lexicon } from '../lexicon';
import { useLexicon } from '../useTheme';
import {
  MARGIN_Y,
  NARROW_LAYOUT,
  WIDE_LAYOUT,
  fogBanks,
  regionHeight,
  regionPath,
  routePoints,
  seedFrom,
  smoothPath,
  wrapLines,
  type AtlasLayout,
  type Point,
} from './atlasGeometry';
import type { BranchOverviewProps } from './types';
import { WorldMap } from './WorldMap';

const WIDE_QUERY = '(min-width: 640px)';

function subscribe(onChange: () => void): () => void {
  if (typeof matchMedia !== 'function') return () => undefined;
  const query = matchMedia(WIDE_QUERY);
  query.addEventListener('change', onChange);
  return () => {
    query.removeEventListener('change', onChange);
  };
}

function isWide(): boolean {
  return typeof matchMedia === 'function' && matchMedia(WIDE_QUERY).matches;
}

/**
 * RPG BranchOverview: a world atlas. The world map shows every zone; selecting one (the `zone`
 * search param, so back, forward and reload work) shows that zone's region: its exercises as
 * waypoints along a dotted route, drawn as inline SVG, with locked regions under fog. On a phone
 * the same route is drawn on a narrow canvas so it reads as a vertical scroll. Every waypoint is
 * a real link, in route order, so keyboard and screen-reader users walk the map as a list.
 */
export function Atlas({ branches }: BranchOverviewProps) {
  const lexicon = useLexicon();
  const wide = useSyncExternalStore(subscribe, isWide);
  const flavour = useFlavour();
  const { zone } = useSearch({ strict: false });
  const selected = branches.find((branch) => branch.id === zone);

  // Selecting moves focus to the zone's heading and going back returns it to that zone's link,
  // so a keyboard user is never left on an element that has just disappeared.
  const shown = useRef(selected?.id);
  const selectedId = selected?.id;
  useEffect(() => {
    if (shown.current === selectedId) return;
    const target = selectedId === undefined ? `world-zone-${shown.current}` : `atlas-${selectedId}`;
    shown.current = selectedId;
    document.getElementById(target)?.focus();
  }, [selectedId]);

  if (selected === undefined)
    return <WorldMap branches={branches} flavour={flavour} lexicon={lexicon} wide={wide} />;
  return (
    <div className="space-y-6">
      <Link
        to="/"
        search={{}}
        className="inline-flex min-h-11 items-center gap-2 text-accent-strong underline underline-offset-2"
      >
        <ArrowLeft aria-hidden="true" className="h-4 w-4" />
        {lexicon.backToWorld}
      </Link>
      <Region
        branch={selected}
        branches={branches}
        layout={wide ? WIDE_LAYOUT : NARROW_LAYOUT}
        lexicon={lexicon}
        flavour={flavour}
      />
    </div>
  );
}

interface RegionProps {
  branch: BranchSummary;
  branches: readonly BranchSummary[];
  layout: AtlasLayout;
  lexicon: Lexicon;
  flavour: Flavour;
}

function Region({ branch, branches, layout, lexicon, flavour }: RegionProps) {
  const { exercises } = branch;
  const headingId = `atlas-${branch.id}`;
  const safeId = branch.id.replace(/[^a-z0-9]/gi, '-');
  const seed = seedFrom(branch.id);
  const { width } = layout;
  const hasLair = exercises.some((exercise) => exercise.tier === 'capstone');
  const height = regionHeight(exercises.length, layout, hasLair);
  const points = routePoints(exercises.length, layout).map((point, i) =>
    // The lair sits square on the route's axis, clear of the labels beside it.
    exercises[i]?.tier === 'capstone' ? { ...point, x: layout.routeCentre } : point,
  );
  const coast = regionPath(width, height, seed);
  const lastPassed = exercises.reduce(
    (last, exercise, i) => (exercise.status === 'passed' ? i : last),
    -1,
  );
  const walkedUntil =
    lastPassed < 0 ? 0 : (points[Math.min(lastPassed + 1, points.length - 1)]?.y ?? 0);
  const requires = branch.requires.map(
    (id) => flavour.zone(id)?.name ?? branches.find((other) => other.id === id)?.title ?? id,
  );
  const zone = flavour.zone(branch.id);

  return (
    <section aria-labelledby={headingId} className="mx-auto" style={{ maxWidth: width }}>
      <header className="mb-3 space-y-2 text-center">
        {/* The small labels share one line: expedition, Pro, the real title, the quest count. */}
        <p className="label-caps m-0 flex flex-wrap items-center justify-center gap-x-2 gap-y-1 text-ink-muted">
          {[
            branch.kind === 'project' && (
              <span key="project" className="text-accent-strong">
                {lexicon.projectLabel}
              </span>
            ),
            branch.pro && <ProMark key="pro" />,
            zone && <span key="title">{branch.title}</span>,
            <span key="count">{lexicon.exerciseCount(exercises.length)}</span>,
          ]
            .filter(Boolean)
            .flatMap((item, i) => [
              i > 0 && (
                <span key={`dot-${String(i)}`}>
                  <span aria-hidden="true"> · </span>
                  <span className="sr-only">, </span>
                </span>
              ),
              item,
            ])}
        </p>
        <h2 id={headingId} tabIndex={-1} className="small-caps-heading m-0 text-2xl sm:text-3xl">
          {zone?.name ?? branch.title}
        </h2>
        {zone && (
          <p className="m-0 font-reading text-lg italic text-ink-secondary">{zone.epithet}</p>
        )}
        <p className="m-0 font-reading text-base text-ink-secondary">
          {zone?.lore ?? branch.summary}
        </p>
        {zone && <p className="m-0 text-sm text-ink-muted">{branch.summary}</p>}
        {!branch.unlocked && (
          <p className="m-0 text-sm text-ink-muted">{lexicon.lockedBranch(requires)}</p>
        )}
        <ProgressRule
          value={branch.passed_count}
          max={exercises.length}
          label={`${zone?.name ?? branch.title} progress`}
          caption={lexicon.progressLabel(branch.passed_count, exercises.length)}
        />
      </header>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        className="block h-auto overflow-visible"
        role="group"
        aria-label={`Map of ${zone?.name ?? branch.title}`}
      >
        <defs>
          <clipPath id={`${safeId}-coast`}>
            <path d={coast} />
          </clipPath>
          <clipPath id={`${safeId}-walked`}>
            <rect x="0" y="0" width={width} height={walkedUntil} />
          </clipPath>
          <pattern
            id={`${safeId}-hatch`}
            width="7"
            height="7"
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(35)"
          >
            <line x1="0" y1="0" x2="0" y2="7" className="stroke-line-subtle" strokeWidth="1" />
          </pattern>
          <filter id={`${safeId}-fog`} x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="14" />
          </filter>
        </defs>

        <path d={coast} className="fill-raised stroke-line-strong" strokeWidth="1.5" />
        <path d={coast} fill={`url(#${safeId}-hatch)`} opacity="0.5" />
        <path
          d={coast}
          className="fill-none stroke-line-subtle"
          strokeWidth="1"
          transform={`translate(${width / 2} ${height / 2}) scale(0.96) translate(${-width / 2} ${-height / 2})`}
        />

        <path
          d={smoothPath(points)}
          className="fill-none stroke-ink-muted"
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray="0.5 9"
        />
        <g clipPath={`url(#${safeId}-walked)`}>
          <path
            d={smoothPath(points)}
            className="fill-none stroke-accent"
            strokeWidth="4"
            strokeLinecap="round"
            strokeDasharray="0.5 9"
          />
        </g>

        {!branch.unlocked && (
          <g clipPath={`url(#${safeId}-coast)`} aria-hidden="true">
            <rect x="0" y="0" width={width} height={height} className="fill-page" opacity="0.4" />
            <g filter={`url(#${safeId}-fog)`}>
              {fogBanks(width, height, seed).map((bank, i) => (
                <ellipse key={i} {...bank} className="fill-page" opacity="0.85" />
              ))}
            </g>
          </g>
        )}

        {exercises.map((exercise, i) =>
          exercise.tier === 'capstone' ? (
            <Lair
              key={exercise.id}
              exercise={exercise}
              point={points[i] ?? { x: MARGIN_Y, y: MARGIN_Y }}
              layout={layout}
              lexicon={lexicon}
              boss={flavour.boss(exercise.id)}
            />
          ) : (
            <Waypoint
              key={exercise.id}
              exercise={exercise}
              point={points[i] ?? { x: MARGIN_Y, y: MARGIN_Y }}
              layout={layout}
              lexicon={lexicon}
              quest={flavour.quest(exercise.id)}
            />
          ),
        )}
      </svg>
    </section>
  );
}

interface WaypointProps {
  exercise: ExerciseSummary;
  point: Point;
  layout: AtlasLayout;
  lexicon: Lexicon;
  /** The themed quest title; when present it leads and the real title becomes secondary. */
  quest: string | undefined;
}

const NODE_RADIUS = 15;
const LINE_HEIGHT = 19;
const SECONDARY_LINE_HEIGHT = 17;

function Waypoint({ exercise, point, layout, lexicon, quest }: WaypointProps) {
  const linkProps = useLinkProps({
    to: '/exercises/$exerciseId',
    params: { exerciseId: exercise.id },
  });
  const tier = toTier(exercise.tier);
  const lines = wrapLines(quest ?? exercise.title, layout.labelChars, quest ? 2 : 3);
  const realLines = quest ? wrapLines(exercise.title, layout.labelChars + 6, 2) : [];
  const status = lexicon.status[exercise.status];
  const meta = `${lexicon.tier[tier]} · ${lexicon.xpLabel(exercise.xp)} · ${status}${proSuffix(exercise, lexicon)}`;
  const realY = point.y - 6 + lines.length * LINE_HEIGHT;
  const metaY = realY + realLines.length * SECONDARY_LINE_HEIGHT + 2;
  const muted = exercise.status === 'locked';

  return (
    <a {...linkProps} className="group">
      <rect
        x="4"
        y={point.y - 34}
        width={layout.width - 8}
        height={metaY + 22 - (point.y - 34)}
        rx="6"
        className="fill-transparent group-hover:fill-accent-soft group-focus-visible:fill-accent-soft"
      />
      <g transform={`translate(${point.x} ${point.y})`}>
        {exercise.status === 'passed' && (
          <>
            <circle r={NODE_RADIUS} className="fill-success" />
            <path
              d="M-6 0.5 L-2 4.5 L6 -4"
              className="fill-none stroke-raised"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </>
        )}
        {exercise.status === 'available' && (
          <>
            <circle r={NODE_RADIUS + 6} className="fill-none stroke-accent" strokeWidth="1.5" />
            <circle r={NODE_RADIUS} className="fill-accent" />
            <circle r="5" className="fill-on-accent" />
          </>
        )}
        {muted && (
          <>
            <circle r={NODE_RADIUS} className="fill-sunken stroke-line-strong" strokeWidth="1.5" />
            <rect x="-5" y="-1" width="10" height="8" rx="1.5" className="fill-ink-muted" />
            <path
              d="M-3 -1 V-4 a3 3 0 0 1 6 0 V-1"
              className="fill-none stroke-ink-muted"
              strokeWidth="1.8"
            />
          </>
        )}
      </g>
      {/* Lines end in a space so the link's text content reads as words. */}
      <text
        x={layout.labelX}
        y={point.y - 6}
        className={`text-base font-medium ${muted ? 'fill-ink-secondary' : 'fill-ink'}`}
      >
        {lines.map((line, i) => (
          <tspan key={line} x={layout.labelX} dy={i === 0 ? 0 : LINE_HEIGHT}>
            {`${line} `}
          </tspan>
        ))}
      </text>
      {realLines.length > 0 && (
        <text x={layout.labelX} y={realY} className="fill-ink-secondary text-sm">
          {realLines.map((line, i) => (
            <tspan key={line} x={layout.labelX} dy={i === 0 ? 0 : SECONDARY_LINE_HEIGHT}>
              {`${line} `}
            </tspan>
          ))}
        </text>
      )}
      <g transform={`translate(${layout.labelX} ${metaY})`} className={tierClass(tier)}>
        <SigilGlyphs count={tier === 'capstone' ? 0 : TIER_INDEX[tier]} />
      </g>
      <text x={layout.labelX + 38} y={metaY + 9} className="fill-ink-muted text-xs">
        {meta}
      </text>
    </a>
  );
}

interface LairProps {
  exercise: ExerciseSummary;
  point: Point;
  layout: AtlasLayout;
  lexicon: Lexicon;
  /** The boss; when present its name leads and the real title stays visible beneath it. */
  boss: BossFlavour | undefined;
}

const LAIR_RADIUS = 27;

/**
 * The capstone's lair: the zone's last waypoint, drawn larger as a fortified tower inside a
 * double ring. Sealed, awaiting or defeated is told by a padlock, an open ring or a tick as well
 * as by the word in its label, and the link carries the boss name, the real title and the state.
 */
function Lair({ exercise, point, layout, lexicon, boss }: LairProps) {
  const linkProps = useLinkProps({
    to: '/exercises/$exerciseId',
    params: { exerciseId: exercise.id },
  });
  const lines = wrapLines(boss?.name ?? exercise.title, layout.labelChars, 2);
  const realLines = boss ? wrapLines(exercise.title, layout.labelChars + 6, 2) : [];
  const meta = `${lexicon.tier.capstone} · ${lexicon.xpLabel(exercise.xp)} · ${lexicon.capstoneState[exercise.status]}${proSuffix(exercise, lexicon)}`;
  const captionY = point.y - 24;
  const nameY = point.y - 4;
  const realY = nameY + lines.length * LINE_HEIGHT;
  const metaY = realY + realLines.length * SECONDARY_LINE_HEIGHT + 2;
  const { status } = exercise;

  return (
    <a {...linkProps} className="group" data-lair={status}>
      <rect
        x="4"
        y={point.y - 40}
        width={layout.width - 8}
        height={metaY + 22 - (point.y - 40)}
        rx="6"
        className="fill-transparent group-hover:fill-accent-soft group-focus-visible:fill-accent-soft"
      />
      <g transform={`translate(${point.x} ${point.y})`}>
        <circle
          r={LAIR_RADIUS + 6}
          className={`fill-none ${status === 'locked' ? 'stroke-ink-muted' : 'stroke-accent'}`}
          strokeWidth="1.5"
          strokeDasharray={status === 'locked' ? '4 4' : undefined}
        />
        <circle
          r={LAIR_RADIUS}
          className={
            status === 'passed'
              ? 'fill-success'
              : status === 'available'
                ? 'fill-accent'
                : 'fill-sunken stroke-line-strong'
          }
          strokeWidth="1.5"
        />
        <g
          transform="translate(-17.5 -17.5) scale(2.5)"
          className={
            status === 'locked'
              ? 'text-ink-muted'
              : status === 'passed'
                ? 'text-raised'
                : 'text-on-accent'
          }
        >
          <BossSigilGlyph />
        </g>
        <g transform={`translate(${LAIR_RADIUS - 4} ${LAIR_RADIUS - 4})`}>
          <circle r="9" className="fill-raised stroke-line-strong" strokeWidth="1.2" />
          {status === 'passed' && (
            <path
              d="M-4 0.3 L-1.3 3 L4 -2.6"
              className="fill-none stroke-success"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}
          {status === 'available' && <circle r="3.2" className="fill-accent" />}
          {status === 'locked' && (
            <>
              <rect x="-3.5" y="-1" width="7" height="5.5" rx="1" className="fill-ink-muted" />
              <path
                d="M-2 -1 V-2.6 a2 2 0 0 1 4 0 V-1"
                className="fill-none stroke-ink-muted"
                strokeWidth="1.4"
              />
            </>
          )}
        </g>
      </g>
      <text x={layout.labelX} y={captionY} className="label-caps fill-tier-capstone text-xs">
        {`${lexicon.capstoneLabel} `}
      </text>
      <text
        x={layout.labelX}
        y={nameY}
        className={`text-lg font-semibold ${status === 'locked' ? 'fill-ink-secondary' : 'fill-ink'}`}
      >
        {lines.map((line, i) => (
          <tspan key={line} x={layout.labelX} dy={i === 0 ? 0 : LINE_HEIGHT}>
            {`${line} `}
          </tspan>
        ))}
      </text>
      {realLines.length > 0 && (
        <text x={layout.labelX} y={realY} className="fill-ink-secondary text-sm">
          {realLines.map((line, i) => (
            <tspan key={line} x={layout.labelX} dy={i === 0 ? 0 : SECONDARY_LINE_HEIGHT}>
              {`${line} `}
            </tspan>
          ))}
        </text>
      )}
      <g transform={`translate(${layout.labelX} ${metaY - 1})`} className="text-tier-capstone">
        <g transform="scale(0.85)">
          <BossSigilGlyph />
        </g>
      </g>
      <text x={layout.labelX + 18} y={metaY + 9} className="fill-ink-muted text-xs">
        {meta}
      </text>
    </a>
  );
}

/** The Pro mark as words in a waypoint's meta line, where an SVG label cannot hold a tag. */
function proSuffix(exercise: ExerciseSummary, lexicon: Lexicon): string {
  return exercise.pro ? ` · ${lexicon.proMark}` : '';
}

function tierClass(tier: ReturnType<typeof toTier>): string {
  return {
    beginner: 'text-tier-beginner',
    intermediate: 'text-tier-intermediate',
    advanced: 'text-tier-advanced',
    capstone: 'text-tier-capstone',
  }[tier];
}
