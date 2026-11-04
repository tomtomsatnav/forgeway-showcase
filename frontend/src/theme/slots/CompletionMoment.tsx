import { animate, motion, useReducedMotion } from 'motion/react';
import { Check, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

import { Link } from '@tanstack/react-router';

import { Button } from '../../components/Button';
import { BossSigilGlyph } from '../../components/TierMark';
import { useFlavour } from '../flavour';
import { useLexicon } from '../useTheme';
import { FlyingXp, Particles, useLandingShake } from './Celebration';
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

function CertificateLink({ progression }: Pick<CompletionMomentProps, 'progression'>) {
  const lexicon = useLexicon();
  if (progression.certificates_issued.length === 0) return null;
  return (
    <Link
      to="/profile"
      hash="certificates"
      className="font-semibold text-accent-strong underline underline-offset-2"
    >
      {lexicon.celebrationCertificate}
    </Link>
  );
}

/** A capstone or certificate, professionally: a card over the page, with confetti. */
function CompletionOverlay({
  progression,
  capstone,
}: Pick<CompletionMomentProps, 'progression' | 'capstone'>) {
  const lexicon = useLexicon();
  const xp = useCountUp(progression.xp_awarded);
  const [open, setOpen] = useState(true);
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
    };
  }, []);
  if (!open) return null;
  const certificate = progression.certificates_issued.at(0);
  return createPortal(
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-40 flex justify-center p-4 sm:inset-0 sm:items-center">
      <Particles kind="confetti" count={70} />
      <motion.div
        role="dialog"
        aria-modal="false"
        aria-labelledby="celebration-title"
        initial={{ opacity: 0, scale: 0.92, y: 12 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.35, ease: EASE }}
        onClick={() => {
          setOpen(false);
        }}
        className="pointer-events-auto flex w-full max-w-md cursor-pointer flex-col items-center gap-3 rounded-control border border-success bg-raised p-8 text-center shadow-lg"
      >
        <Check aria-hidden="true" className="h-10 w-10 text-success" />
        <h2 id="celebration-title" className="m-0 text-2xl">
          {capstone ? lexicon.capstoneCompletionTitle : lexicon.certificateCompletionTitle}
        </h2>
        <p className="m-0 text-ink-secondary">{capstone?.title ?? certificate?.branch_title}</p>
        <p className="tabular m-0 text-lg font-semibold">+{xp} XP</p>
        <div
          className="flex flex-wrap items-center justify-center gap-4"
          onClick={(event) => {
            event.stopPropagation();
          }}
        >
          <CertificateLink progression={progression} />
          <Button
            variant="secondary"
            onClick={() => {
              setOpen(false);
            }}
          >
            Close
          </Button>
        </div>
      </motion.div>
    </div>,
    document.body,
  );
}

/** Professional: a confirmation strip that catches the eye, then gets out of the way. */
export function ProfessionalCompletionMoment({
  progression,
  unlocked,
  onDismiss,
  capstone,
}: CompletionMomentProps) {
  const lexicon = useLexicon();
  const strip = useRef<HTMLDivElement>(null);
  const big = Boolean(capstone) || progression.certificates_issued.length > 0;
  return (
    <motion.div
      ref={strip}
      role="status"
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: EASE }}
      className="relative flex items-start justify-between gap-3 overflow-hidden rounded-control border border-success bg-success-soft px-4 py-3"
    >
      <motion.div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-success"
        initial={{ x: '-100%', opacity: 0.3 }}
        animate={{ x: '100%', opacity: 0 }}
        transition={{ duration: 0.7, ease: 'easeOut' }}
      />
      <div className="relative space-y-2">
        <p className="tabular m-0 flex items-center gap-2 font-semibold text-success">
          <motion.span
            className="inline-flex"
            initial={{ scale: 0 }}
            animate={{ scale: [0, 1.35, 1] }}
            transition={{ duration: 0.4, ease: EASE }}
          >
            <Check aria-hidden="true" className="h-5 w-5" />
          </motion.span>
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
        className="relative -my-1 -mr-2 min-w-11 px-2"
      >
        <X aria-hidden="true" className="h-4 w-4" />
      </Button>
      <FlyingXp xp={progression.xp_awarded} from={strip} />
      {big && <CompletionOverlay progression={progression} capstone={capstone} />}
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

/** Hairlines from the seal's centre, drawn just before it breaks open. */
const CRACKS = [
  'M64 64 L44 34 L38 18',
  'M64 64 L92 50 L108 44',
  'M64 64 L72 96 L66 112',
  'M64 64 L34 78 L20 88',
];

const RING_RADIUS = 58;
const RING_LENGTH = 2 * Math.PI * RING_RADIUS;

/** The wax seal: a ring that fills towards the next level, the level number pressed into the wax. */
function Seal({
  level,
  levelBefore,
  fraction,
  boss = false,
}: {
  level: number;
  /** Below `level` on a level up: the seal shows this, cracks, then shows `level`. */
  levelBefore: number;
  fraction: number;
  /** Press the boss's tower into the wax instead of the level number. */
  boss?: boolean;
}) {
  const reduced = useReducedMotion();
  const leveledUp = level > levelBefore && !boss;
  const [broken, setBroken] = useState(false);
  useEffect(() => {
    if (reduced || (!leveledUp && !boss)) return;
    const timer = window.setTimeout(() => {
      setBroken(true);
    }, 750);
    return () => {
      window.clearTimeout(timer);
    };
  }, [reduced, leveledUp, boss]);
  const shownLevel = leveledUp && !broken && !reduced ? levelBefore : level;
  useLandingShake(0.16);
  return (
    <motion.div
      initial={{ scale: 1.7, opacity: 0, filter: 'drop-shadow(0 18px 14px rgb(0 0 0 / 0.5))' }}
      animate={
        broken
          ? { scale: [1, 1.18, 1], opacity: 1, filter: 'drop-shadow(0 3px 3px rgb(0 0 0 / 0.35))' }
          : { scale: 1, opacity: 1, filter: 'drop-shadow(0 3px 3px rgb(0 0 0 / 0.35))' }
      }
      transition={{ duration: broken ? 0.35 : 0.22, ease: 'easeIn' }}
      className="relative h-32 w-32"
    >
      <Particles kind="sparks" count={12} />
      {broken && <Particles kind="embers" count={boss ? 34 : 26} />}
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
            {shownLevel}
          </text>
        )}
        {(leveledUp || boss) && !reduced && !broken && (
          <g stroke="var(--text-on-accent)" strokeWidth="2" fill="none" strokeLinecap="round">
            {CRACKS.map((crack) => (
              <motion.path
                key={crack}
                d={crack}
                initial={{ pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: 0.28, delay: 0.42, ease: 'easeIn' }}
              />
            ))}
          </g>
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
        {(capstone !== null && capstone !== undefined) ||
        progression.certificates_issued.length > 0 ? (
          <Particles kind="gold" count={60} />
        ) : null}
        <Seal
          level={progression.level_after}
          levelBefore={progression.level_before}
          fraction={levelFraction}
          boss={Boolean(capstone)}
        />
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
        <CertificateLink progression={progression} />
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
