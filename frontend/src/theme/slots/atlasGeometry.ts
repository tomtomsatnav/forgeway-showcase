/** Pure geometry for the atlas: deterministic, so a branch always draws the same coast. */

export interface Point {
  x: number;
  y: number;
}

export interface AtlasLayout {
  width: number;
  step: number;
  routeCentre: number;
  routeSway: number;
  labelX: number;
  labelChars: number;
}

export const NARROW_LAYOUT: AtlasLayout = {
  width: 360,
  step: 132,
  routeCentre: 68,
  routeSway: 26,
  labelX: 124,
  labelChars: 28,
};

export const WIDE_LAYOUT: AtlasLayout = {
  width: 600,
  step: 116,
  routeCentre: 104,
  routeSway: 56,
  labelX: 208,
  labelChars: 46,
};

export const MARGIN_Y = 56;
/** Room below the last waypoint for its label, secondary title and meta line. */
const MARGIN_BOTTOM = 104;

export function seedFrom(text: string): number {
  let hash = 2166136261;
  for (const char of text) {
    hash ^= char.codePointAt(0) ?? 0;
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

/** mulberry32: a tiny seeded generator returning floats in [0, 1). */
export function random(seed: number): () => number {
  let state = seed;
  return () => {
    state = (state + 0x6d2b79f5) | 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Extra room below a lair, whose label carries a caption, a boss name and the real title. */
const LAIR_EXTRA = 40;

export function regionHeight(count: number, layout: AtlasLayout, lair = false): number {
  return MARGIN_Y + MARGIN_BOTTOM + Math.max(count - 1, 0) * layout.step + (lair ? LAIR_EXTRA : 0);
}

/** Waypoints wind down the region in a gentle S. */
export function routePoints(count: number, layout: AtlasLayout): Point[] {
  return Array.from({ length: count }, (_, i) => ({
    x: layout.routeCentre + layout.routeSway * Math.sin(i * 1.15),
    y: MARGIN_Y + i * layout.step,
  }));
}

const fixed = (n: number) => n.toFixed(1);

/** A smooth open curve through the points (Catmull-Rom converted to cubic Beziers). */
export function smoothPath(points: readonly Point[]): string {
  const [first] = points;
  if (first === undefined) return '';
  let d = `M${fixed(first.x)} ${fixed(first.y)}`;
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[Math.max(i - 1, 0)] ?? first;
    const p1 = points[i] ?? first;
    const p2 = points[i + 1] ?? p1;
    const p3 = points[Math.min(i + 2, points.length - 1)] ?? p2;
    d += ` C${fixed(p1.x + (p2.x - p0.x) / 6)} ${fixed(p1.y + (p2.y - p0.y) / 6)} ${fixed(p2.x - (p3.x - p1.x) / 6)} ${fixed(p2.y - (p3.y - p1.y) / 6)} ${fixed(p2.x)} ${fixed(p2.y)}`;
  }
  return d;
}

export function closedSmoothPath(points: readonly Point[]): string {
  const n = points.length;
  const at = (i: number): Point => points[((i % n) + n) % n] ?? { x: 0, y: 0 };
  let d = `M${fixed(at(0).x)} ${fixed(at(0).y)}`;
  for (let i = 0; i < n; i++) {
    const p0 = at(i - 1);
    const p1 = at(i);
    const p2 = at(i + 1);
    const p3 = at(i + 2);
    d += ` C${fixed(p1.x + (p2.x - p0.x) / 6)} ${fixed(p1.y + (p2.y - p0.y) / 6)} ${fixed(p2.x - (p3.x - p1.x) / 6)} ${fixed(p2.y - (p3.y - p1.y) / 6)} ${fixed(p2.x)} ${fixed(p2.y)}`;
  }
  return `${d} Z`;
}

/** An organic coastline: the region's rectangle with each edge point nudged inwards. */
export function regionPath(width: number, height: number, seed: number): string {
  const next = random(seed);
  const inset = () => 10 + next() * 14;
  const across = Math.max(Math.round(width / 100), 3);
  const down = Math.max(Math.round(height / 100), 3);
  const points: Point[] = [];
  for (let i = 0; i < across; i++) points.push({ x: 20 + ((width - 40) * i) / across, y: inset() });
  for (let i = 0; i < down; i++)
    points.push({ x: width - inset(), y: 20 + ((height - 40) * i) / down });
  for (let i = across; i > 0; i--)
    points.push({ x: 20 + ((width - 40) * i) / across, y: height - inset() });
  for (let i = down; i > 0; i--) points.push({ x: inset(), y: 20 + ((height - 40) * i) / down });
  return closedSmoothPath(points);
}

/** Soft blobs of fog scattered across a region. */
export function fogBanks(
  width: number,
  height: number,
  seed: number,
): { cx: number; cy: number; rx: number; ry: number }[] {
  const next = random(seed ^ 0x9e3779b9);
  const count = Math.max(Math.round(height / 90), 4);
  return Array.from({ length: count }, (_, i) => ({
    cx: next() * width,
    cy: ((i + 0.5) / count) * height,
    rx: width * (0.25 + next() * 0.2),
    ry: 46 + next() * 30,
  }));
}

/** Break a title into lines of at most `max` characters, never splitting a word. */
export function wrapLines(text: string, max: number, maxLines = 3): string[] {
  const lines: string[] = [];
  let line = '';
  for (const word of text.split(/\s+/)) {
    if (line !== '' && `${line} ${word}`.length > max) {
      lines.push(line);
      line = word;
    } else {
      line = line === '' ? word : `${line} ${word}`;
    }
  }
  if (line !== '') lines.push(line);
  if (lines.length > maxLines) {
    const kept = lines.slice(0, maxLines);
    kept[maxLines - 1] = `${kept[maxLines - 1] ?? ''}…`;
    return kept;
  }
  return lines;
}
