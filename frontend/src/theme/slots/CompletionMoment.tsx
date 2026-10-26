import { animate, motion, useReducedMotion } from 'motion/react';
import { Check, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';

import { Link } from '@tanstack/react-router';

import { Button } from '../../components/Button';
import { BossSigilGlyph } from '../../components/TierMark';
import { useFlavour } from '../flavour';
import { useLexicon } from '../useTheme';
import { ProgressionNews } from './ProgressionNews';
import type { CompletionMomentProps } from './types';

const EASE = [0.2, 0.7, 0.2, 1] as const;

function NextLinks({ unlocked }: Pick<CompletionMomentProps, 'unlocked'>) {
  if (unlocked.length === 0) return null;
  return (
    <ul className="m-0 list-none space-y-1 p-0">
      {unlocked.map((item) => (
        <li key={item.id}>
          <Link
            to="/exercises/$exerciseId"
            params={{ exerciseId: item.id }}
            className="text-accent-strong underline underline-offset-2"
          >
            {item.title}
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** Professional: a quiet inline confirmation strip. */
export function ProfessionalCompletionMoment({
  progression,
  unlocked,
  onDismiss,
  capstone,
}: CompletionMomentProps) {
  const lexicon = useLexicon();
  return (
    <motion.div
      role="status"
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: EASE }}
      className="flex items-start justify-between gap-3 rounded-control border border-success bg-success-soft px-4 py-3"
    >
      <div className="space-y-2">
        <p className="tabular m-0 flex items-center gap-2 font-semibold text-success">
          <Check aria-hidden="true" className="h-5 w-5" />
          {capstone
            ? lexicon.capstoneStrip(progression.xp_awarded, progression.level_after)
            : lexicon.passedStrip(progression.xp_awarded, progression.level_after)}
        </p>
        <ProgressionNews progression={progression} />
        {unlocked.length > 0 && (
          <div className="space-y-1 text-sm text-ink">
            <p className="m-0">{lexicon.newlyOpened(unlocked.length)}</p>
            <NextLinks unlocked={unlocked} />
          </div>
        )}
      </div>
      <Button
        variant="quiet"
        onClick={onDismiss}
        aria-label="Dismiss"
        className="-my-1 -mr-2 min-w-11 px-2"
      >
        <X aria-hidden="true" className="h-4 w-4" />
      </Button>
    </motion.div>
  );
}

/** Counts from zero to `target` over the celebrate duration, or jumps there under reduced motion. */
function useCountUp(target: number): number {
  const reduced = useReducedMotion();
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (reduced) return;
    const controls = animate(0, target, {
      duration: 0.9,
      ease: EASE,
      onUpdate: (latest) => {
        setValue(Math.round(latest));
      },
    });
    return () => {
      controls.stop();
    };
  }, [target, reduced]);
  return reduced ? target : value;
}

const RING_RADIUS = 58;
const RING_LENGTH = 2 * Math.PI * RING_RADIUS;

/** The wax seal: a ring that fills towards the next level, the level number pressed into the wax. */
function Seal({
  level,
  fraction,
  boss = false,
}: {
  level: number;
  fraction: number;
  /** Press the boss's tower into the wax instead of the level number. */
  boss?: boolean;
}) {
  return (
    <motion.div
      initial={{ scale: 1.15, opacity: 0, filter: 'drop-shadow(0 14px 12px rgb(0 0 0 / 0.45))' }}
      animate={{ scale: 1, opacity: 1, filter: 'drop-shadow(0 3px 3px rgb(0 0 0 / 0.35))' }}
      transition={{ duration: 0.9, ease: EASE }}
      className="relative h-32 w-32"
    >
      <svg viewBox="0 0 128 128" className="h-full w-full" aria-hidden="true">
        <circle
          cx="64"
          cy="64"
          r={RING_RADIUS}
          fill="none"
          stroke="var(--border-subtle)"
          strokeWidth="3"
        />
        <g transform="rotate(-90 64 64)">
          <motion.circle
            cx="64"
            cy="64"
            r={RING_RADIUS}
            fill="none"
            stroke="var(--accent-strong)"
            strokeWidth="3"
            strokeLinecap="round"
            strokeDasharray={RING_LENGTH}
            initial={{ strokeDashoffset: RING_LENGTH }}
            animate={{ strokeDashoffset: RING_LENGTH * (1 - fraction) }}
            transition={{ duration: 0.9, ease: EASE, delay: 0.3 }}
          />
        </g>
        <path
          d="M64 14c10 0 14 8 24 9 9 1 17 7 18 17 1 9 8 13 8 24s-7 15-8 24c-1 10-9 16-18 17-10 1-14 9-24 9s-14-8-24-9c-9-1-17-7-18-17-1-9-8-13-8-24s7-15 8-24c1-10 9-16 18-17 10-1 14-9 24-9Z"
          transform="scale(0.78) translate(18 18)"
          fill="var(--accent)"
        />
        <circle
          cx="64"
          cy="64"
          r="34"
          fill="none"
          stroke="var(--text-on-accent)"
          strokeWidth="1.5"
          opacity="0.55"
        />
        {boss ? (
          <g transform="translate(40 40) scale(3.43)" fill="var(--text-on-accent)">
            <BossSigilGlyph />
          </g>
        ) : (
          <text
            x="64"
            y="64"
            textAnchor="middle"
            dominantBaseline="central"
            fill="var(--text-on-accent)"
            style={{ font: '700 34px var(--font-display)' }}
          >
            {level}
          </text>
        )}
      </svg>
      <span className="sr-only">{`Level ${level}`}</span>
    </motion.div>
  );
}

/** RPG: a wax-seal moment. It floats above the page without trapping focus or blocking input. */
export function RpgCompletionMoment({
  progression,
  unlocked,
  onDismiss,
  levelFraction,
  capstone,
}: CompletionMomentProps) {
  const lexicon = useLexicon();
  const flavour = useFlavour();
  const boss = capstone ? flavour.boss(capstone.exerciseId) : undefined;
  const xp = useCountUp(progression.xp_awarded);
  const leveledUp = progression.level_after > progression.level_before;

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onDismiss();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [onDismiss]);

  return createPortal(
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-50 flex justify-center p-4 sm:inset-0 sm:items-center">
      <motion.div
        role="dialog"
        aria-modal="false"
        aria-labelledby="completion-title"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.2 }}
        onClick={onDismiss}
        className="pointer-events-auto relative flex w-full max-w-sm cursor-pointer flex-col items-center gap-4 rounded-panel border border-line-strong bg-raised p-6 text-center shadow-raised outline outline-1 -outline-offset-4 outline-line-subtle"
      >
        <Seal level={progression.level_after} fraction={levelFraction} boss={Boolean(capstone)} />
        <div className="space-y-1">
          <h2 id="completion-title" className="small-caps-heading m-0 text-xl">
            {capstone ? lexicon.capstoneCompletionTitle : lexicon.completionTitle}
          </h2>
          {capstone && (
            <>
              {boss && <p className="m-0 text-lg font-semibold">{boss.name}</p>}
              {boss && (
                <p className="m-0 font-reading text-base italic text-ink-secondary">
                  {boss.defeat}
                </p>
              )}
              <p className="m-0 text-sm text-ink-secondary">{capstone.title}</p>
            </>
          )}
          {leveledUp && (
            <p className="m-0 text-base text-accent-strong">
              {lexicon.levelUp(progression.level_after)} reached
            </p>
          )}
          <p className="tabular m-0 text-lg font-semibold">+{xp} XP</p>
        </div>
        <ProgressionNews progression={progression} />
        {unlocked.length > 0 && (
          <div
            className="space-y-1 text-sm"
            onClick={(event) => {
              event.stopPropagation();
            }}
          >
            <p className="m-0 text-ink-secondary">{lexicon.newlyOpened(unlocked.length)}</p>
            <NextLinks unlocked={unlocked} />
          </div>
        )}
        <Button
          variant="secondary"
          onClick={(event) => {
            event.stopPropagation();
            onDismiss();
          }}
        >
          Close
        </Button>
      </motion.div>
    </div>,
    document.body,
  );
}
