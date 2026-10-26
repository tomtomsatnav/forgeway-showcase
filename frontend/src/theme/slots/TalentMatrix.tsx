import { Check, CircleDot, Lock, X, type LucideIcon } from 'lucide-react';
import { useState, useSyncExternalStore } from 'react';

import type { TalentNode, TalentState } from '../../api/types';
import { Button } from '../../components/Button';
import { useLexicon } from '../useTheme';
import { talentRequirements, type Requirement } from './talentRequirements';
import type { TalentTreeProps } from './types';

const ICONS: Record<TalentState, LucideIcon> = {
  allocated: Check,
  available: CircleDot,
  locked: Lock,
};

const COLOURS: Record<TalentState, string> = {
  allocated: 'text-success',
  available: 'text-accent',
  locked: 'text-ink-muted',
};

/** The DOM id of a talent's action button, so the constellation can send focus to it. */
export const talentActionId = (nodeId: string) => `talent-action-${nodeId}`;

/** Allocated, available or locked as an icon and a word, never colour alone. */
function TalentStateMark({ state }: { state: TalentState }) {
  const Icon = ICONS[state];
  const lexicon = useLexicon();
  return (
    <span className={`inline-flex items-center gap-1.5 ${COLOURS[state]}`}>
      <Icon aria-hidden="true" className="h-4 w-4 shrink-0" />
      <span className="label-caps">{lexicon.talentState[state]}</span>
    </span>
  );
}

const NARROW_QUERY = '(max-width: 767.98px)';

function subscribe(onChange: () => void): () => void {
  if (typeof matchMedia !== 'function') return () => undefined;
  const query = matchMedia(NARROW_QUERY);
  query.addEventListener('change', onChange);
  return () => {
    query.removeEventListener('change', onChange);
  };
}

/** Below the md breakpoint the table becomes stacked cards; with no matchMedia it stays a table. */
function isNarrow(): boolean {
  return typeof matchMedia === 'function' && matchMedia(NARROW_QUERY).matches;
}

/** The DOM id of a talent's row or card, so a click on its star can land somewhere when it has no button. */
export const talentRowId = (nodeId: string) => `talent-row-${nodeId}`;

function RequirementLine({ requirement }: { requirement: Requirement }) {
  const lexicon = useLexicon();
  const text = {
    level: () => lexicon.talentRequiresLevel(requirement.level),
    parent: () => lexicon.talentRequiresParents([requirement.subject]),
    exercise: () => lexicon.talentRequiresExercises([requirement.subject]),
    other: () => requirement.subject,
  }[requirement.kind]();
  const Glyph = requirement.met ? Check : X;
  return (
    <li className="flex items-start gap-2">
      <Glyph
        aria-hidden="true"
        className={`mt-0.5 h-4 w-4 shrink-0 ${requirement.met ? 'text-success' : 'text-danger'}`}
      />
      <span className={requirement.met ? 'text-ink-secondary' : 'font-medium text-ink'}>
        <span className="sr-only">{requirement.met ? 'Met: ' : 'Not met: '}</span>
        {text}
      </span>
    </li>
  );
}

/** One list: each requirement with a glyph and words for met or not, plus any unmapped reason. */
function Requirements({
  node,
  tree,
  exerciseTitle,
}: { node: TalentNode } & Pick<TalentTreeProps, 'tree' | 'exerciseTitle'>) {
  const requirements = talentRequirements(node, {
    titles: new Map(tree.nodes.map((other) => [other.id, other.title])),
    states: new Map(tree.nodes.map((other) => [other.id, other.state])),
    exerciseTitle,
  });
  return (
    <ul className="m-0 list-none space-y-1 p-0 text-sm">
      {requirements.map((requirement) => (
        <RequirementLine
          key={`${requirement.kind}-${requirement.subject}`}
          requirement={requirement}
        />
      ))}
    </ul>
  );
}

/** Learn when available, release when taken, and nothing at all when locked: the list says why. */
function TalentAction({
  node,
  busy,
  pending,
  onAllocate,
  onDeallocate,
}: {
  node: TalentNode;
  busy: boolean;
  pending: boolean;
  onAllocate: (id: string) => void;
  onDeallocate: (id: string) => void;
}) {
  const lexicon = useLexicon();
  if (node.state === 'locked') return null;
  if (node.state === 'allocated')
    return (
      <Button
        id={talentActionId(node.id)}
        variant="secondary"
        aria-label={`${lexicon.talentDeallocate} ${node.title}`}
        loading={pending}
        disabled={busy}
        onClick={() => {
          onDeallocate(node.id);
        }}
      >
        {lexicon.talentDeallocate}
      </Button>
    );
  return (
    <Button
      id={talentActionId(node.id)}
      aria-label={`${lexicon.talentAllocate} ${node.title}`}
      loading={pending}
      disabled={busy}
      onClick={() => {
        onAllocate(node.id);
      }}
    >
      {lexicon.talentAllocate}
    </Button>
  );
}

/** Respec behind a confirm step, in the same pattern as HintReveal. */
function Respec({
  disabled,
  loading,
  onRespec,
}: Pick<TalentTreeProps, 'onRespec'> & { disabled: boolean; loading: boolean }) {
  const lexicon = useLexicon();
  const [confirming, setConfirming] = useState(false);
  if (confirming) {
    return (
      <div
        role="group"
        aria-label={lexicon.respec}
        className="space-y-3 rounded-control border border-warning bg-warning-soft p-3"
      >
        <p className="m-0 text-sm text-ink">{lexicon.respecCost}</p>
        <div className="flex flex-wrap gap-2">
          <Button
            onClick={() => {
              setConfirming(false);
              onRespec();
            }}
          >
            {lexicon.respecConfirm}
          </Button>
          <Button
            variant="quiet"
            onClick={() => {
              setConfirming(false);
            }}
          >
            {lexicon.respecKeep}
          </Button>
        </div>
      </div>
    );
  }
  return (
    <Button
      variant="secondary"
      disabled={disabled}
      loading={loading}
      onClick={() => {
        setConfirming(true);
      }}
    >
      {lexicon.respec}
    </Button>
  );
}

/**
 * The competency matrix: an accessible table of skills with their requirements, state and an
 * action. It is the professional talent tree and the RPG constellation's accessible equivalent,
 * and the only place either mode allocates from.
 */
export function TalentMatrix(props: TalentTreeProps) {
  const { tree, exerciseTitle, subtreeName, pendingNode, respeccing, problem } = props;
  const lexicon = useLexicon();
  const busy = pendingNode !== null || respeccing;
  const subtrees = [...new Set(tree.nodes.map((node) => node.subtree))];
  const narrow = useSyncExternalStore(subscribe, isNarrow);
  const actions = (node: TalentNode) => ({
    busy,
    pending: pendingNode === node.id,
    onAllocate: props.onAllocate,
    onDeallocate: props.onDeallocate,
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p role="status" className="tabular m-0 font-semibold">
          {lexicon.talentPoints(tree.available_points, tree.total_points)}
        </p>
        <Respec
          disabled={tree.spent_points === 0 || busy}
          loading={respeccing}
          onRespec={props.onRespec}
        />
      </div>
      {problem !== null && (
        <p
          role="alert"
          className="m-0 rounded-control bg-danger-soft px-3 py-2 text-sm text-danger"
        >
          {problem}
        </p>
      )}
      {narrow ? (
        <div role="region" aria-label={`${lexicon.talentTree} list`} className="space-y-4">
          {subtrees.map((subtree) => (
            <section key={subtree} aria-labelledby={`talent-group-${subtree}`}>
              <h3 id={`talent-group-${subtree}`} className="label-caps m-0 mb-2 text-ink-secondary">
                {subtreeName(subtree)}
              </h3>
              <ul className="m-0 list-none space-y-3 p-0">
                {tree.nodes
                  .filter((node) => node.subtree === subtree)
                  .map((node) => (
                    <li
                      key={node.id}
                      id={talentRowId(node.id)}
                      tabIndex={-1}
                      className="space-y-3 rounded-panel border border-line-subtle p-3 outline-none"
                    >
                      <div>
                        <p className="m-0 font-semibold">{node.title}</p>
                        <p className="m-0 text-sm text-ink-secondary">{node.summary}</p>
                      </div>
                      <Requirements node={node} tree={tree} exerciseTitle={exerciseTitle} />
                      <TalentStateMark state={node.state} />
                      <TalentAction node={node} {...actions(node)} />
                    </li>
                  ))}
              </ul>
            </section>
          ))}
        </div>
      ) : (
        <div
          role="region"
          aria-label={`${lexicon.talentTree} table`}
          tabIndex={0}
          className="relative overflow-x-auto rounded-panel border border-line-subtle"
        >
          <table className="w-full border-collapse text-left">
            <caption className="sr-only">
              {lexicon.talentTree}. {lexicon.talentTreeSummary}
            </caption>
            <thead>
              <tr className="border-b border-line-strong text-sm">
                <th scope="col" className="px-3 py-2 font-semibold capitalize">
                  {lexicon.talent}
                </th>
                <th scope="col" className="px-3 py-2 font-semibold">
                  {lexicon.talentRequirements}
                </th>
                <th scope="col" className="px-3 py-2 font-semibold">
                  State
                </th>
                <th scope="col" className="px-3 py-2 font-semibold">
                  <span className="sr-only">Action</span>
                </th>
              </tr>
            </thead>
            {subtrees.map((subtree) => (
              <tbody key={subtree}>
                <tr className="bg-sunken">
                  <th
                    scope="rowgroup"
                    colSpan={4}
                    className="label-caps px-3 py-2 text-ink-secondary"
                  >
                    {subtreeName(subtree)}
                  </th>
                </tr>
                {tree.nodes
                  .filter((node) => node.subtree === subtree)
                  .map((node) => (
                    <tr
                      key={node.id}
                      id={talentRowId(node.id)}
                      tabIndex={-1}
                      className="border-t border-line-subtle align-top outline-none"
                    >
                      <th scope="row" className="max-w-64 px-3 py-3 text-left font-normal">
                        <span className="block font-semibold">{node.title}</span>
                        <span className="block text-sm text-ink-secondary">{node.summary}</span>
                      </th>
                      <td className="px-3 py-3">
                        <Requirements node={node} tree={tree} exerciseTitle={exerciseTitle} />
                      </td>
                      <td className="px-3 py-3">
                        <TalentStateMark state={node.state} />
                      </td>
                      <td className="px-3 py-3">
                        <TalentAction node={node} {...actions(node)} />
                      </td>
                    </tr>
                  ))}
              </tbody>
            ))}
          </table>
        </div>
      )}
    </div>
  );
}
