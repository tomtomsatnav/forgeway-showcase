import { toTier, type Tier } from '../api/types';
import { useLexicon, useTheme } from '../theme/useTheme';

/** How many bars or diamonds a graded tier fills; the capstone has its own mark instead. */
export const TIER_INDEX: Record<Exclude<Tier, 'capstone'>, number> = {
  beginner: 1,
  intermediate: 2,
  advanced: 3,
};
const TIER_COLOUR: Record<Tier, string> = {
  beginner: 'text-tier-beginner',
  intermediate: 'text-tier-intermediate',
  advanced: 'text-tier-advanced',
  capstone: 'text-tier-capstone',
};

/**
 * One, two or three stacked bars (professional) or diamonds (RPG), plus the tier word. A capstone
 * gets its own mark instead: bars inside a frame (professional) or a fortified tower (RPG).
 */
export function TierMark({ tier, showLabel = true }: { tier: string; showLabel?: boolean }) {
  const value = toTier(tier);
  const { mode } = useTheme();
  const lexicon = useLexicon();
  return (
    <span className={`inline-flex items-center gap-2 ${TIER_COLOUR[value]}`}>
      {value === 'capstone' ? (
        <CapstoneIcon />
      ) : mode === 'rpg' ? (
        <Sigil count={TIER_INDEX[value]} />
      ) : (
        <Bars count={TIER_INDEX[value]} />
      )}
      <span className={showLabel ? 'label-caps' : 'sr-only'}>{lexicon.tier[value]}</span>
    </span>
  );
}

function Bars({ count }: { count: number }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 12 12" className="h-3 w-3 shrink-0">
      {[0, 1, 2].map((i) => (
        <rect
          key={i}
          x="0"
          y={8 - i * 4}
          width="12"
          height="2.5"
          rx="0.5"
          fill="currentColor"
          opacity={i < count ? 1 : 0.28}
        />
      ))}
    </svg>
  );
}

/** Diamond glyphs on a 30x10 grid; also drawn directly inside the atlas SVG. */
export function SigilGlyphs({ count }: { count: number }) {
  return (
    <>
      {[0, 1, 2].map((i) => (
        <path
          key={i}
          d={`M${5 + i * 10} 0.5 L${9.5 + i * 10} 5 L${5 + i * 10} 9.5 L${0.5 + i * 10} 5 Z`}
          fill={i < count ? 'currentColor' : 'none'}
          stroke="currentColor"
          strokeWidth="1"
          opacity={i < count ? 1 : 0.4}
        />
      ))}
    </>
  );
}

function Sigil({ count }: { count: number }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 30 10" className="h-2.5 w-[30px] shrink-0">
      <SigilGlyphs count={count} />
    </svg>
  );
}

/** Three bars inside a frame, on a 12x12 grid: the stack of the track, boxed in as a project. */
export function CapstoneFrameGlyph() {
  return (
    <>
      <rect
        x="0.75"
        y="0.75"
        width="10.5"
        height="10.5"
        rx="1"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      {[0, 1, 2].map((i) => (
        <rect key={i} x="3" y={3 + i * 2.25} width="6" height="1.25" fill="currentColor" />
      ))}
    </>
  );
}

/** A crenellated tower with a gate, on a 14x14 grid; also drawn, enlarged, in the lair. */
export function BossSigilGlyph() {
  return (
    <path
      d="M2 13V4h2v2h1.5V4h3v2H10V4h2v9ZM5.5 13V9.5a1.5 1.5 0 0 1 3 0V13Z"
      fill="currentColor"
      fillRule="evenodd"
    />
  );
}

/** The capstone's mark for the current mode, decorative: the words carry the meaning. */
export function CapstoneIcon() {
  const { mode } = useTheme();
  return mode === 'rpg' ? (
    <svg aria-hidden="true" viewBox="0 0 14 14" className="h-3.5 w-3.5 shrink-0">
      <BossSigilGlyph />
    </svg>
  ) : (
    <svg aria-hidden="true" viewBox="0 0 12 12" className="h-3 w-3 shrink-0">
      <CapstoneFrameGlyph />
    </svg>
  );
}
