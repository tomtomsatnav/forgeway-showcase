import { animate, motion, useReducedMotion } from 'motion/react';
import { useEffect, useState, type RefObject } from 'react';
import { createPortal } from 'react-dom';

const EASE = [0.2, 0.7, 0.2, 1] as const;

type ParticleKind = 'confetti' | 'gold' | 'sparks' | 'embers';

const COLOURS: Record<ParticleKind, readonly string[]> = {
  confetti: ['var(--accent)', 'var(--accent-strong)', 'var(--success)', 'var(--tier-capstone)'],
  gold: ['var(--tier-capstone)', 'var(--accent-strong)'],
  sparks: ['var(--accent-strong)', 'var(--text-on-accent)'],
  embers: ['var(--tier-capstone)', 'var(--accent)'],
};

const between = (low: number, high: number) => low + Math.random() * (high - low);

function pieces(kind: ParticleKind, count: number) {
  const colours = COLOURS[kind];
  return Array.from({ length: count }, (_, index) => ({
    id: index,
    colour: colours[index % colours.length],
    angle: between(0, Math.PI * 2),
    reach: kind === 'embers' ? between(70, 190) : between(45, 110),
    left: between(0, 100),
    drift: between(-8, 8),
    spin: between(-540, 540),
    delay: between(0, 0.35),
    duration: between(1.5, 2.5),
    size: between(4, 9),
  }));
}

/**
 * One-shot decoration, drawn with plain elements so it needs no canvas or library. `confetti` and
 * `gold` fall over the whole window; `sparks` and `embers` burst from the middle of the parent,
 * which must be positioned. Renders nothing under reduced motion.
 */
export function Particles({ kind, count = 24 }: { kind: ParticleKind; count?: number }) {
  const reduced = useReducedMotion();
  const [items] = useState(() => pieces(kind, count));
  const [done, setDone] = useState(false);
  const rain = kind === 'confetti' || kind === 'gold';
  useEffect(() => {
    const timer = window.setTimeout(
      () => {
        setDone(true);
      },
      rain ? 3200 : 1100,
    );
    return () => {
      window.clearTimeout(timer);
    };
  }, [rain]);
  if (reduced || done) return null;

  if (rain) {
    return createPortal(
      <div aria-hidden="true" className="pointer-events-none fixed inset-0 z-50 overflow-hidden">
        {items.map((item) => (
          <motion.span
            key={item.id}
            className="absolute top-0 block rounded-[1px]"
            style={{
              left: `${item.left}%`,
              width: item.size,
              height: item.size * 1.6,
              background: item.colour,
            }}
            initial={{ y: '-5vh', opacity: 1, rotate: 0 }}
            animate={{ y: '105vh', x: `${item.drift}vw`, rotate: item.spin }}
            transition={{ duration: item.duration, delay: item.delay, ease: 'easeIn' }}
          />
        ))}
      </div>,
      document.body,
    );
  }
  return (
    <div aria-hidden="true" className="pointer-events-none absolute left-1/2 top-1/2 h-0 w-0">
      {items.map((item) => (
        <motion.span
          key={item.id}
          className="absolute block rounded-full"
          style={{ width: item.size, height: item.size, background: item.colour }}
          initial={{ x: 0, y: 0, opacity: 1, scale: 1 }}
          animate={{
            x: Math.cos(item.angle) * item.reach,
            y: Math.sin(item.angle) * item.reach,
            opacity: 0,
            scale: 0.3,
          }}
          transition={{ duration: 0.75, delay: item.delay / 4, ease: EASE }}
        />
      ))}
    </div>
  );
}

/** Nudges the page, once, as something lands on it. Does nothing under reduced motion. */
export function useLandingShake(delaySeconds: number, enabled = true) {
  const reduced = useReducedMotion();
  useEffect(() => {
    const root = document.getElementById('root');
    if (reduced || !enabled || root === null) return;
    const controls = animate(
      root,
      { x: [0, -4, 3, -2, 0], y: [0, 2, -2, 1, 0] },
      { duration: 0.28, delay: delaySeconds },
    );
    return () => {
      controls.stop();
      root.style.transform = '';
    };
  }, [delaySeconds, enabled, reduced]);
}

/** The XP won, flying from `from` up into the level bar in the header. */
export function FlyingXp({ xp, from }: { xp: number; from: RefObject<HTMLElement | null> }) {
  const reduced = useReducedMotion();
  const [path, setPath] = useState<{ x0: number; y0: number; x1: number; y1: number } | null>(null);
  useEffect(() => {
    if (reduced) return;
    // Measure after the strip has been laid out.
    const frame = window.requestAnimationFrame(() => {
      const target = document.querySelector('[data-xp-target]')?.getBoundingClientRect();
      const start = from.current?.getBoundingClientRect();
      // The bar is folded away on small screens; there is nowhere to fly to.
      if (!target || !start || target.width === 0) return;
      setPath({
        x0: start.left,
        y0: start.top,
        x1: target.left + target.width / 2,
        y1: target.top + target.height / 2,
      });
    });
    return () => {
      window.cancelAnimationFrame(frame);
    };
  }, [from, reduced]);
  if (path === null) return null;
  return createPortal(
    <motion.span
      aria-hidden="true"
      className="tabular pointer-events-none fixed left-0 top-0 z-50 rounded-full bg-success px-2 py-0.5 text-sm font-semibold text-on-accent"
      initial={{ x: path.x0, y: path.y0, scale: 1, opacity: 0 }}
      animate={{
        x: path.x1,
        y: path.y1,
        scale: [1, 1.25, 0.6],
        opacity: [0, 1, 1, 0],
      }}
      transition={{ duration: 0.85, delay: 0.2, ease: 'easeInOut' }}
    >
      +{xp} XP
    </motion.span>,
    document.body,
  );
}
