import { useSyncExternalStore } from 'react';

import type { TalentState } from '../../api/types';
import { wrapLines } from './atlasGeometry';
import { useLexicon } from '../useTheme';
import {
  METRICS,
  NODE_RADIUS,
  planConstellation,
  type ConstellationNode,
  type Metrics,
} from './talentGeometry';
import { TalentMatrix, talentActionId, talentRowId } from './TalentMatrix';
import type { TalentTreeProps } from './types';

const WIDE_QUERY = '(min-width: 768px)';

function subscribe(onChange: () => void): () => void {
  if (typeof matchMedia !== 'function') return () => undefined;
  const query = matchMedia(WIDE_QUERY);
  query.addEventListener('change', onChange);
  return () => {
    query.removeEventListener('change', onChange);
  };
}

/** The bigger drawing on tablets and desktops; the compact one (and in tests) otherwise. */
function isWide(): boolean {
  return typeof matchMedia === 'function' && matchMedia(WIDE_QUERY).matches;
}

/** Shape, not colour, carries the state: a tick in a disc, a ringed dot, or a padlock. */
function Glyph({ state }: { state: TalentState }) {
  if (state === 'allocated')
    return (
      <>
        <circle r={NODE_RADIUS} className="fill-success" />
        <path
          d="M-9 1 L-3 7 L9 -6"
          className="fill-none stroke-raised"
          strokeWidth="3.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </>
    );
  if (state === 'available')
    return (
      <>
        <circle r={NODE_RADIUS} className="fill-raised stroke-accent" strokeWidth="2.5" />
        <circle r="14" className="fill-none stroke-accent" strokeWidth="1.2" />
        <circle r="7" className="fill-accent" />
      </>
    );
  return (
    <>
      <circle
        r={NODE_RADIUS}
        className="fill-sunken stroke-line-strong"
        strokeWidth="1.5"
        strokeDasharray="4 3"
      />
      <rect x="-7" y="-2" width="14" height="11" rx="2" className="fill-ink-muted" />
      <path
        d="M-4.5 -2 V-5 a4.5 4.5 0 0 1 9 0 V-2"
        className="fill-none stroke-ink-muted"
        strokeWidth="2.4"
      />
    </>
  );
}

function Star({
  entry,
  state,
  metrics,
  onSelect,
}: {
  entry: ConstellationNode;
  state: string;
  metrics: Metrics;
  onSelect: (id: string) => void;
}) {
  const { node, x, y } = entry;
  const { radius, line: lineHeight } = metrics;
  const lines = wrapLines(node.title, metrics.labelChars, 2);
  const wide = metrics === METRICS.wide;
  return (
    <g
      transform={`translate(${x} ${y})`}
      data-node={node.id}
      data-state={node.state}
      className="cursor-pointer"
      onClick={() => {
        onSelect(node.id);
      }}
    >
      <g transform={`scale(${(radius / NODE_RADIUS).toFixed(3)})`}>
        <Glyph state={node.state} />
      </g>
      <text
        textAnchor="middle"
        className={`fill-ink font-medium ${wide ? 'text-base' : 'text-sm'}`}
      >
        {lines.map((line, i) => (
          <tspan key={line} x={0} y={radius + 18 + i * lineHeight}>
            {line}
          </tspan>
        ))}
      </text>
      <text
        x={0}
        y={radius + 18 + lines.length * lineHeight}
        textAnchor="middle"
        className={`fill-ink-secondary ${wide ? 'text-sm' : 'text-xs'}`}
      >
        {state}
      </text>
    </g>
  );
}

/**
 * RPG: the talents as a constellation, general talents above and the class's below. It is for the
 * eye and the pointer; the competency table beneath is the equivalent that screen readers and
 * keyboards use, so the drawing is a labelled image and a click only moves focus to that
 * talent's button there.
 */
export function TalentConstellation(props: TalentTreeProps) {
  const lexicon = useLexicon();
  const wide = useSyncExternalStore(subscribe, isWide);
  const plan = planConstellation(props.tree.nodes, wide ? 'wide' : 'compact');
  const select = (id: string) => {
    // A locked talent has no button: land on its row, which says what it still needs.
    (
      document.getElementById(talentActionId(id)) ?? document.getElementById(talentRowId(id))
    )?.focus();
  };

  return (
    <div className="space-y-6">
      <svg
        viewBox={`0 0 ${plan.width} ${plan.height}`}
        width="100%"
        style={{ maxWidth: plan.width }}
        className="mx-auto block h-auto"
        role="img"
        aria-labelledby="talent-sky-title"
        aria-describedby="talent-sky-desc"
      >
        <title id="talent-sky-title">{lexicon.talentTree}</title>
        <desc id="talent-sky-desc">
          {lexicon.talentTreeSummary} The table beneath lists the same {lexicon.talentPlural}.
        </desc>
        <g aria-hidden="true">
          {plan.links.map((link) => {
            const both =
              props.tree.nodes.find((n) => n.id === link.from)?.state === 'allocated' &&
              props.tree.nodes.find((n) => n.id === link.to)?.state === 'allocated';
            return both ? (
              <path
                key={`${link.from}-${link.to}`}
                d={link.d}
                data-link="taken"
                className="fill-none stroke-accent"
                strokeWidth="3"
                strokeLinecap="round"
              />
            ) : (
              <path
                key={`${link.from}-${link.to}`}
                d={link.d}
                data-link="open"
                className="fill-none stroke-ink-muted"
                strokeWidth="1.5"
                strokeDasharray="3 7"
                strokeLinecap="round"
              />
            );
          })}
          {plan.blocks.map((block) => (
            <text
              key={block.subtree}
              x={block.x}
              y={block.y}
              textAnchor="middle"
              className={`fill-ink-secondary font-semibold uppercase tracking-label ${plan.metrics === METRICS.wide ? 'text-sm' : 'text-xs'}`}
            >
              {props.subtreeName(block.subtree)}
            </text>
          ))}
          {plan.nodes.map((entry) => (
            <Star
              key={entry.node.id}
              entry={entry}
              state={lexicon.talentState[entry.node.state]}
              metrics={plan.metrics}
              onSelect={select}
            />
          ))}
        </g>
      </svg>
      <TalentMatrix {...props} />
    </div>
  );
}
