import { Link, useNavigate } from '@tanstack/react-router';
import { useMemo, useState } from 'react';

import type { BranchSummary } from '../../api/types';
import { ProMark } from '../../components/ProMark';
import { StatusMark } from '../../components/StatusMark';
import type { Flavour } from '../flavour';
import type { Lexicon } from '../lexicon';
import {
  NARROW_WORLD,
  WIDE_WORLD,
  islandLabel,
  islandPath,
  planWorld,
  type WorldLayout,
  type WorldNode,
} from './worldGeometry';

type ZoneState = 'locked' | 'available' | 'passed';

function stateOf(branch: BranchSummary): ZoneState {
  if (!branch.unlocked) return 'locked';
  return branch.exercises.length > 0 && branch.passed_count === branch.exercises.length
    ? 'passed'
    : 'available';
}

interface WorldMapProps {
  branches: readonly BranchSummary[];
  flavour: Flavour;
  lexicon: Lexicon;
  wide: boolean;
}

/**
 * The world: the hub zone in the middle, a road to every other zone, locked zones under fog.
 * A road leaves each zone its destination requires, so a zone beyond another is reached from
 * that one, and a project on the outer ring from every zone it draws on. The drawing is for the eye and for the pointer; the list beneath it holds the real links, in
 * data order, so keyboard and screen-reader users never meet the map's shapes. Focusing a list
 * entry rings its island, so sighted keyboard users can still see where they are.
 */
export function WorldMap({ branches, flavour, lexicon, wide }: WorldMapProps) {
  const [active, setActive] = useState<string | undefined>();
  const layout: WorldLayout = wide ? WIDE_WORLD : NARROW_WORLD;
  const plan = useMemo(() => planWorld(branches, layout), [branches, layout]);
  const nameOf = (branch: BranchSummary) => flavour.zone(branch.id)?.name ?? branch.title;
  const titleOf = (id: string) => {
    const other = branches.find((branch) => branch.id === id);
    return other === undefined ? id : nameOf(other);
  };
  const stateByRoute = new Map(branches.map((branch) => [branch.id, stateOf(branch)]));

  return (
    <section aria-labelledby="world-heading" className="space-y-6">
      <h2 id="world-heading" className="small-caps-heading m-0 text-center text-2xl sm:text-3xl">
        {lexicon.worldMapTitle}
      </h2>

      <svg
        viewBox={`0 0 ${plan.width} ${plan.height}`}
        width="100%"
        style={{ maxWidth: plan.width }}
        className="mx-auto block h-auto"
        role="img"
        aria-labelledby="world-title"
        aria-describedby="world-desc"
      >
        <title id="world-title">{lexicon.worldMapTitle}</title>
        <desc id="world-desc">{lexicon.worldMapDescription(branches.length)}</desc>
        <defs>
          <filter id="world-fog" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="9" />
          </filter>
          <pattern
            id="world-hatch"
            width="7"
            height="7"
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(35)"
          >
            <line x1="0" y1="0" x2="0" y2="7" className="stroke-line-subtle" strokeWidth="1" />
          </pattern>
        </defs>

        <g aria-hidden="true">
          {plan.routes.map((route) =>
            stateByRoute.get(route.to) === 'locked' ? (
              <path
                key={`${route.from}-${route.to}`}
                d={route.d}
                className="fill-none stroke-ink-muted"
                strokeWidth="2"
                strokeLinecap="butt"
                strokeDasharray="12 9"
                data-route="closed"
                data-route-from={route.from}
                data-route-to={route.to}
              />
            ) : (
              <path
                key={`${route.from}-${route.to}`}
                d={route.d}
                className="fill-none stroke-accent"
                strokeWidth="4"
                strokeLinecap="round"
                strokeDasharray="0.5 9"
                data-route="open"
                data-route-from={route.from}
                data-route-to={route.to}
              />
            ),
          )}
          {plan.nodes.map((node) => (
            <Island
              key={node.branch.id}
              node={node}
              state={stateOf(node.branch)}
              active={active === node.branch.id}
              lines={islandLabel(nameOf(node.branch), layout)}
              onHover={setActive}
            />
          ))}
        </g>
      </svg>

      <nav aria-label={lexicon.branchPlural}>
        {/* A ruled list, not cards: hub first, then the ring clockwise, projects last, the order
            the eye reads the map in. */}
        <ol className="m-0 list-none border-t-2 border-ink p-0">
          {plan.nodes.map(({ branch }) => {
            const zone = flavour.zone(branch.id);
            const state = stateOf(branch);
            return (
              <li key={branch.id} className="border-b border-line-subtle">
                <Link
                  to="/"
                  search={{ zone: branch.id }}
                  id={`world-zone-${branch.id}`}
                  onFocus={() => {
                    setActive(branch.id);
                  }}
                  onBlur={() => {
                    setActive(undefined);
                  }}
                  className="group grid min-h-11 gap-x-4 gap-y-1 py-3 text-ink no-underline sm:grid-cols-[minmax(0,1fr)_auto] sm:items-baseline"
                >
                  <span className="min-w-0">
                    {(branch.kind === 'project' || branch.pro) && (
                      <span className="flex flex-wrap items-center gap-2">
                        {branch.kind === 'project' && (
                          <span className="label-caps text-ink-muted">{lexicon.projectLabel}</span>
                        )}
                        {branch.pro && <ProMark />}
                      </span>
                    )}
                    <span className="block font-medium group-hover:underline">
                      {nameOf(branch)}
                    </span>
                    {zone && <span className="block text-sm text-ink-muted">{branch.title}</span>}
                    {!branch.unlocked && (
                      <span className="block text-sm text-ink-muted">
                        {lexicon.lockedBranch(branch.requires.map(titleOf))}
                      </span>
                    )}
                  </span>
                  <span className="flex flex-wrap items-center gap-x-3 text-sm sm:justify-end">
                    <StatusMark status={state} />
                    <span className="tabular text-ink-secondary">
                      {lexicon.progressLabel(branch.passed_count, branch.exercises.length)}
                    </span>
                  </span>
                </Link>
              </li>
            );
          })}
        </ol>
      </nav>
    </section>
  );
}

interface IslandProps {
  node: WorldNode;
  state: ZoneState;
  active: boolean;
  lines: readonly string[];
  onHover: (id: string | undefined) => void;
}

const NAME_LINE = 18;

function Island({ node, state, active, lines, onHover }: IslandProps) {
  const { branch, x, y, radius } = node;
  const navigate = useNavigate();
  const safeId = `world-${branch.id.replace(/[^a-z0-9]/gi, '-')}`;
  const coast = islandPath(x, y, radius, branch.id);
  const blockHeight = 26 + lines.length * NAME_LINE + 18;
  const top = y - blockHeight / 2;
  const locked = state === 'locked';

  return (
    // Not a link: a focusable child would nest an interactive control inside the map's role="img".
    // The list beneath holds the real links.
    <g
      data-zone={branch.id}
      className="group cursor-pointer"
      onClick={() => {
        void navigate({ to: '/', search: { zone: branch.id } });
      }}
      onMouseEnter={() => {
        onHover(branch.id);
      }}
      onMouseLeave={() => {
        onHover(undefined);
      }}
    >
      <clipPath id={`${safeId}-coast`}>
        <path d={coast} />
      </clipPath>
      {active && (
        <circle
          cx={x}
          cy={y}
          r={radius + 9}
          className="fill-none stroke-focus"
          strokeWidth="3"
          strokeDasharray="6 5"
        />
      )}
      {branch.kind === 'project' && (
        // A project's island has a second, outer coast: a region of its own, not one more zone.
        <path
          d={coast}
          className="fill-none stroke-line-strong"
          strokeWidth="1"
          strokeDasharray="3 4"
          transform={`translate(${x} ${y}) scale(1.12) translate(${-x} ${-y})`}
          data-project-coast=""
        />
      )}
      <path
        d={coast}
        className="fill-raised stroke-line-strong group-hover:fill-accent-soft"
        strokeWidth="1.5"
      />
      <path d={coast} fill="url(#world-hatch)" opacity="0.5" />
      <path
        d={coast}
        className="fill-none stroke-line-subtle"
        strokeWidth="1"
        transform={`translate(${x} ${y}) scale(0.9) translate(${-x} ${-y})`}
      />
      {locked && (
        <g clipPath={`url(#${safeId}-coast)`}>
          <rect
            x={x - radius}
            y={y - radius}
            width={radius * 2}
            height={radius * 2}
            className="fill-page"
            opacity="0.4"
          />
          <g filter="url(#world-fog)">
            {[-0.45, 0.05, 0.5].map((offset, i) => (
              <ellipse
                key={offset}
                cx={x + (i % 2 === 0 ? -1 : 1) * radius * 0.2}
                cy={y + offset * radius}
                rx={radius * 0.95}
                ry={radius * 0.3}
                className="fill-page"
                opacity="0.85"
              />
            ))}
          </g>
        </g>
      )}
      <g transform={`translate(${x} ${top + 11})`}>
        <ZoneGlyph state={state} />
      </g>
      <text
        textAnchor="middle"
        className={`text-base font-medium ${locked ? 'fill-ink-secondary' : 'fill-ink'}`}
      >
        {lines.map((line, i) => (
          <tspan key={line} x={x} y={top + 26 + 14 + i * NAME_LINE}>
            {line}
          </tspan>
        ))}
      </text>
      <text
        x={x}
        y={top + 26 + lines.length * NAME_LINE + 12}
        textAnchor="middle"
        className="fill-ink-secondary text-sm tabular"
      >
        {branch.passed_count}/{branch.exercises.length}
      </text>
    </g>
  );
}

/** Shape, not colour, carries the state: a padlock, an open ring, or a tick in a disc. */
function ZoneGlyph({ state }: { state: ZoneState }) {
  if (state === 'passed')
    return (
      <>
        <circle r="11" className="fill-success" />
        <path
          d="M-5 0.5 L-1.5 4 L5 -3.5"
          className="fill-none stroke-raised"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </>
    );
  if (state === 'available')
    return (
      <>
        <circle r="11" className="fill-none stroke-accent" strokeWidth="1.5" />
        <circle r="7" className="fill-accent" />
        <circle r="3" className="fill-on-accent" />
      </>
    );
  return (
    <>
      <circle r="11" className="fill-sunken stroke-line-strong" strokeWidth="1.5" />
      <rect x="-4" y="-1" width="8" height="6.5" rx="1.2" className="fill-ink-muted" />
      <path
        d="M-2.4 -1 V-3 a2.4 2.4 0 0 1 4.8 0 V-1"
        className="fill-none stroke-ink-muted"
        strokeWidth="1.6"
      />
    </>
  );
}
