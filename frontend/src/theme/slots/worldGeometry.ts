/**
 * Pure geometry for the world map: the hub zone at the centre, every other zone on a ring, and
 * project zones on an outer ring beyond the zones they require.
 */
import type { BranchSummary } from '../../api/types';
import { closedSmoothPath, random, seedFrom, wrapLines, type Point } from './atlasGeometry';

export interface WorldLayout {
  /** Ring radii before the spacing guarantees below scale them up. */
  ringX: number;
  ringY: number;
  hubRadius: number;
  zoneRadius: number;
  /** Characters per line of a zone name inside its island. */
  nameChars: number;
  wide: boolean;
}

export const WIDE_WORLD: WorldLayout = {
  ringX: 250,
  ringY: 170,
  hubRadius: 82,
  zoneRadius: 64,
  nameChars: 15,
  wide: true,
};

/** Tall and slim, so the map is a vertical scroll that still fits a 320px screen unscaled. */
export const NARROW_WORLD: WorldLayout = {
  ringX: 92,
  ringY: 170,
  hubRadius: 66,
  zoneRadius: 52,
  nameChars: 11,
  wide: false,
};

const MARGIN = 28;
/** Open water kept between neighbouring islands, and between the hub and the ring. */
const GAP = 34;

export interface WorldNode {
  branch: BranchSummary;
  hub: boolean;
  x: number;
  y: number;
  radius: number;
}

export interface WorldRoute {
  /** The zone the route leads to. */
  to: string;
  /**
   * The zone it leaves: one of the branches `to` requires (each gets its own road), or the hub
   * when `to` requires nothing on the map.
   */
  from: string;
  d: string;
}

export interface WorldPlan {
  width: number;
  height: number;
  /** The hub first, then each ring zone followed by the zones that grow out of it, projects last. */
  nodes: WorldNode[];
  routes: WorldRoute[];
}

const isProject = (branch: BranchSummary) => branch.kind === 'project';

/** The hub is the branch the most others require (the starter); with no requirements, the first. */
export function hubOf(branches: readonly BranchSummary[]): BranchSummary | undefined {
  const demand = new Map<string, number>();
  for (const branch of branches)
    for (const id of branch.requires) demand.set(id, (demand.get(id) ?? 0) + 1);
  let hub = branches[0];
  for (const branch of branches)
    if ((demand.get(branch.id) ?? 0) > (demand.get(hub?.id ?? '') ?? 0)) hub = branch;
  return hub;
}

/** Degrees for each of `count` ring slots, clockwise from the layout's starting point. */
function ringAngles(count: number, wide: boolean): number[] {
  let start = -90 + (count % 2 === 0 ? 180 / count : 0);
  if (count <= 2) start = wide ? 0 : 90;
  return Array.from({ length: count }, (_, i) => start + (360 * i) / count);
}

const radians = (degrees: number) => (degrees * Math.PI) / 180;
const fixed = (n: number) => n.toFixed(1);

/**
 * Each zone's road leaves the zone it requires: a non-hub requirement when it has one (Knowledge
 * graphs from Retrieval), otherwise the hub. A requirement cycle is cut by sending the zone to the hub.
 * Projects are placed on their own ring, so they are nobody's parent and have none.
 */
function parentsOf(branches: readonly BranchSummary[], hub: BranchSummary): Map<string, string> {
  const ids = new Set(branches.filter((branch) => !isProject(branch)).map((branch) => branch.id));
  const parents = new Map<string, string>();
  for (const branch of branches) {
    if (branch.id === hub.id || isProject(branch)) continue;
    const required = branch.requires.filter((id) => id !== branch.id && ids.has(id));
    parents.set(branch.id, required.find((id) => id !== hub.id) ?? hub.id);
  }
  for (const branch of branches) {
    if (!parents.has(branch.id)) continue;
    const seen = new Set<string>();
    for (let id = branch.id; id !== hub.id; id = parents.get(id) ?? hub.id) {
      if (seen.has(id)) {
        parents.set(branch.id, hub.id);
        break;
      }
      seen.add(id);
    }
  }
  return parents;
}

/**
 * The zones a road to `branch` leaves from: every zone it requires that is on the map, except one
 * that itself requires `branch`, directly or not, which would close a cycle. Empty means the hub.
 */
function roadSources(branch: BranchSummary, branches: readonly BranchSummary[]): string[] {
  const byId = new Map(branches.map((other) => [other.id, other]));
  const reaches = (from: string, target: string): boolean => {
    const seen = new Set<string>();
    const stack = [from];
    for (let id = stack.pop(); id !== undefined; id = stack.pop()) {
      if (id === target) return true;
      if (seen.has(id)) continue;
      seen.add(id);
      stack.push(...(byId.get(id)?.requires ?? []));
    }
    return false;
  };
  return [...new Set(branch.requires)].filter(
    (id) => id !== branch.id && byId.has(id) && !reaches(id, branch.id),
  );
}

interface Placed {
  branch: BranchSummary;
  parent: string | undefined;
  x: number;
  y: number;
  /** Unit direction the zone lies in from its parent, which its own children continue. */
  dx: number;
  dy: number;
}

/**
 * Lay the world out from data. Zones that require the hub sit on a ring; a zone that requires
 * another zone sits beyond it, further along the same direction from the hub, with siblings side
 * by side. The whole layout is scaled up, never down, until every island clears every other by
 * GAP and every road can be routed clear of the islands it does not serve, so any number of
 * branches fits; the canvas is then cropped to what is drawn, plus a margin.
 */
export function planWorld(branches: readonly BranchSummary[], layout: WorldLayout): WorldPlan {
  const hub = hubOf(branches);
  if (hub === undefined) return { width: 0, height: 0, nodes: [], routes: [] };
  const parents = parentsOf(branches, hub);
  const others = branches.filter((branch) => branch.id !== hub.id && !isProject(branch));
  const projects = branches.filter((branch) => branch.id !== hub.id && isProject(branch));
  const childrenOf = (id: string) => others.filter((branch) => parents.get(branch.id) === id);
  const ring = childrenOf(hub.id);
  const { zoneRadius, hubRadius } = layout;
  const reach = 2 * zoneRadius + GAP;

  const slots = ringAngles(ring.length, layout.wide).map((degrees) => ({
    x: layout.ringX * Math.cos(radians(degrees)),
    y: layout.ringY * Math.sin(radians(degrees)),
  }));
  let minScale = 1;
  slots.forEach((slot, i) => {
    minScale = Math.max(
      minScale,
      (hubRadius + zoneRadius + GAP) / (Math.hypot(slot.x, slot.y) || 1),
    );
    const next = slots[(i + 1) % slots.length];
    if (next !== undefined && next !== slot)
      minScale = Math.max(
        minScale,
        (2 * zoneRadius + GAP) / (Math.hypot(next.x - slot.x, next.y - slot.y) || 1),
      );
  });

  const radiusOf = (node: Placed) => (node.parent === undefined ? hubRadius : zoneRadius);
  const place = (scale: number): Placed[] => {
    const root: Placed = { branch: hub, parent: undefined, x: 0, y: 0, dx: 0, dy: 0 };
    const placed: Placed[] = [root];
    const grow = (from: Placed) => {
      const kids = childrenOf(from.branch.id);
      kids.forEach((branch, j) => {
        let node: Placed;
        if (from.parent === undefined) {
          const slot = slots[j] ?? { x: 0, y: 0 };
          const length = Math.hypot(slot.x, slot.y) || 1;
          node = {
            branch,
            parent: from.branch.id,
            x: slot.x * scale,
            y: slot.y * scale,
            dx: slot.x / length,
            dy: slot.y / length,
          };
        } else {
          // Beyond the parent, fanned sideways about the line the parent lies on.
          const side = (j - (kids.length - 1) / 2) * reach;
          node = {
            branch,
            parent: from.branch.id,
            x: from.x + from.dx * reach - from.dy * side,
            y: from.y + from.dy * reach + from.dx * side,
            dx: from.dx,
            dy: from.dy,
          };
        }
        placed.push(node);
        grow(node);
      });
    };
    grow(root);
    for (const branch of projects) placed.push(placeProject(branch, placed));
    return placed;
  };
  const clearOf = (node: Placed, placed: readonly Placed[]) =>
    placed.every(
      (other) =>
        other === node ||
        Math.hypot(node.x - other.x, node.y - other.y) >= radiusOf(node) + radiusOf(other) + GAP,
    );
  const clear = (placed: readonly Placed[]) => placed.every((node) => clearOf(node, placed));

  /**
   * A project sits on an outer ring: in the direction of the zones it requires (straight down on
   * a narrow screen, so the map stays a vertical scroll), past every zone already placed, and
   * moved outward until it clears them all, earlier projects included. The ring follows the
   * layout's own ellipse.
   */
  const placeProject = (branch: BranchSummary, placed: readonly Placed[]): Placed => {
    const flat = (node: Placed) => ({ x: node.x / layout.ringX, y: node.y / layout.ringY });
    let sx = 0;
    let sy = 0;
    for (const node of placed)
      if (node.parent !== undefined && branch.requires.includes(node.branch.id)) {
        const { x, y } = flat(node);
        const length = Math.hypot(x, y) || 1;
        sx += x / length;
        sy += y / length;
      }
    const angle = layout.wide && Math.hypot(sx, sy) > 1e-6 ? Math.atan2(sy, sx) : radians(90);
    const ex = layout.ringX * Math.cos(angle);
    const ey = layout.ringY * Math.sin(angle);
    const step = 4 / (Math.hypot(ex, ey) || 1);
    let t =
      Math.max(0, ...placed.map((node) => Math.hypot(flat(node).x, flat(node).y))) +
      (zoneRadius + GAP) / (Math.hypot(ex, ey) || 1);
    const node: Placed = { branch, parent: hub.id, x: 0, y: 0, dx: 0, dy: 0 };
    for (let tries = 0; tries < 1000; tries++, t += step) {
      node.x = t * ex;
      node.y = t * ey;
      if (clearOf(node, placed)) break;
    }
    return node;
  };
  let scale = minScale;
  let placed = place(scale);
  let roads = clear(placed) ? routeRoads(placed) : undefined;
  for (let step = 0; step < 60 && roads === undefined; step++) {
    scale *= 1.06;
    placed = place(scale);
    roads = clear(placed) ? routeRoads(placed) : undefined;
  }
  roads ??= routeRoads(placed, true) ?? [];

  // Fit the canvas to what is drawn: every island (a project's outer coast included) and every
  // road, plus the margin, which also holds an island's focus ring. No symmetric padding, so no empty band of water.
  const drawn = [
    ...placed.map((node) => ({ x: node.x, y: node.y, r: outerRadius(node) })),
    ...roads.flatMap((road) => road.samples.map((p) => ({ ...p, r: ROAD_HALF }))),
  ];
  const left = -Math.min(...drawn.map((p) => p.x - p.r));
  const top = -Math.min(...drawn.map((p) => p.y - p.r));
  const right = Math.max(...drawn.map((p) => p.x + p.r));
  const bottom = Math.max(...drawn.map((p) => p.y + p.r));
  const shift = (p: Point): Point => ({ x: p.x + left + MARGIN, y: p.y + top + MARGIN });
  const nodes: WorldNode[] = placed.map((node) => ({
    branch: node.branch,
    hub: node.parent === undefined,
    ...shift(node),
    radius: radiusOf(node),
  }));
  const routes = roads.map((road) => ({
    to: road.to,
    from: road.from,
    d: cubicPath(road.curve.map((segment) => segment.map(shift) as Cubic)),
  }));
  return {
    width: left + right + 2 * MARGIN,
    height: top + bottom + 2 * MARGIN,
    nodes,
    routes,
  };

  /** The radius an island draws to, a project's dashed outer coast included. */
  function outerRadius(node: Placed): number {
    return radiusOf(node) * (isProject(node.branch) ? PROJECT_COAST : 1);
  }

  /**
   * A road for every requirement, each the cheapest curve that keeps clear of every island but
   * its own two ends. Undefined when some road cannot (the caller spreads the islands out and
   * tries again) unless `anyway`, which takes the least obstructed curve instead.
   */
  function routeRoads(placed: readonly Placed[], anyway = false): Road[] | undefined {
    const byId = new Map(placed.map((node) => [node.branch.id, node]));
    const islands: Isle[] = placed.map((node) => ({
      id: node.branch.id,
      x: node.x,
      y: node.y,
      r: outerRadius(node),
    }));
    const box: Box = {
      minX: Math.min(...islands.map((i) => i.x - i.r)),
      maxX: Math.max(...islands.map((i) => i.x + i.r)),
      minY: Math.min(...islands.map((i) => i.y - i.r)),
      maxY: Math.max(...islands.map((i) => i.y + i.r)),
    };
    const pairs = placed.slice(1).flatMap((node) => {
      const sources = roadSources(node.branch, branches).flatMap((id) => byId.get(id) ?? []);
      return (sources.length > 0 ? sources : placed.slice(0, 1)).map((from) => ({
        from,
        to: node,
      }));
    });
    const done: Road[] = [];
    for (const [i, { from, to }] of pairs.entries()) {
      const others = islands.filter(
        (island) => island.id !== from.branch.id && island.id !== to.branch.id,
      );
      const ends = islands.filter(
        (island) => island.id === from.branch.id || island.id === to.branch.id,
      );
      const ids = { from: from.branch.id, to: to.branch.id };
      const preferred = i % 2 === 0 ? BOW : -BOW;
      let best = bestCurve(ids, from, to, others, ends, done, box, preferred, false);
      // No single curve both clears the islands and stays within them: thread the water between.
      if (best === undefined || best.outside > 0) {
        const water = waterRoad(ids, from, to, others, done, box);
        if (water !== undefined) best = { road: water, cost: 0, outside: 0 };
      }
      if (best === undefined && anyway)
        best = bestCurve(ids, from, to, others, ends, done, box, preferred, true);
      if (best === undefined) return undefined;
      done.push(best.road);
    }
    return done;
  }
}

type Cubic = [Point, Point, Point, Point];

interface Road {
  from: string;
  to: string;
  /** One or more cubic segments, end to end. */
  curve: Cubic[];
  samples: Point[];
}

interface Isle {
  id: string;
  x: number;
  y: number;
  r: number;
}

interface Box {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
}

const clearOfIsles = (p: Point, isles: readonly Isle[]) =>
  isles.every((isle) => Math.hypot(p.x - isle.x, p.y - isle.y) >= isle.r + CLEARANCE);

/**
 * The cheapest single curve between two islands: shortest, nearest the road's usual bow, inside
 * the islands' box and not running alongside a road already drawn. Only curves clear of every
 * other island count, unless `anyway`, which takes the least obstructed.
 */
function bestCurve(
  ids: { from: string; to: string },
  from: Point,
  to: Point,
  others: readonly Isle[],
  ends: readonly Isle[],
  done: readonly Road[],
  box: Box,
  preferred: number,
  anyway: boolean,
): { road: Road; cost: number; outside: number } | undefined {
  let best: { road: Road; cost: number; outside: number } | undefined;
  // A single bow first; the S-curves only when no bow stays clear and inside the map.
  for (const sCurves of [false, true]) {
    if (sCurves && best?.outside === 0) break;
    for (const { curve, bend } of candidateCurves(from, to, sCurves)) {
      const samples = sampleCubic(curve);
      let blocked = 0;
      for (const p of samples) {
        for (const isle of others)
          blocked += Math.max(0, isle.r + CLEARANCE - Math.hypot(p.x - isle.x, p.y - isle.y));
        if (blocked > 0 && !anyway) break;
      }
      if (blocked > 0 && !anyway) continue;
      let length = 0;
      let outside = 0;
      samples.forEach((p, k) => {
        const prev = samples[k - 1];
        if (prev !== undefined) length += Math.hypot(p.x - prev.x, p.y - prev.y);
        outside = Math.max(outside, box.minX - p.x, p.x - box.maxX, box.minY - p.y, p.y - box.maxY);
      });
      const span = Math.hypot(to.x - from.x, to.y - from.y) || 1;
      let cost = length + 20 * outside + 0.5 * span * Math.abs(bend - preferred) + 1e4 * blocked;
      if (best !== undefined && cost >= best.cost) continue;
      // Running alongside a road already drawn reads as one road: count the stretch it shares.
      for (const p of samples) {
        if (!clearOfIsles(p, ends)) continue;
        if (nearRoad(p, done)) cost += 6;
      }
      if (best === undefined || cost < best.cost)
        best = { road: { ...ids, curve: [curve], samples }, cost, outside };
    }
  }
  return best;
}

const nearRoad = (p: Point, done: readonly Road[]) =>
  done.some((road) => road.samples.some((q) => Math.hypot(p.x - q.x, p.y - q.y) < ROAD_SPACING));

/** Grid step for threading a road through the water, in map units. */
const CELL = 6;

/**
 * A road threaded through the water between islands, kept inside the islands' box: the shortest
 * path on a coarse grid (avoiding roads already drawn where it can), pulled taut, then smoothed
 * as far as it stays clear. Undefined when the islands wall the two ends off from each other.
 */
function waterRoad(
  ids: { from: string; to: string },
  from: Point,
  to: Point,
  others: readonly Isle[],
  done: readonly Road[],
  box: Box,
): Road | undefined {
  const cols = Math.ceil((box.maxX - box.minX) / CELL) + 1;
  const rows = Math.ceil((box.maxY - box.minY) / CELL) + 1;
  const at = (cell: number): Point => ({
    x: box.minX + (cell % cols) * CELL,
    y: box.minY + Math.floor(cell / cols) * CELL,
  });
  const cellOf = (p: Point) =>
    Math.min(rows - 1, Math.max(0, Math.round((p.y - box.minY) / CELL))) * cols +
    Math.min(cols - 1, Math.max(0, Math.round((p.x - box.minX) / CELL)));
  const free = new Uint8Array(cols * rows);
  const crowded = new Uint8Array(cols * rows);
  for (let cell = 0; cell < free.length; cell++) {
    const p = at(cell);
    free[cell] = clearOfIsles(p, others) ? 1 : 0;
    crowded[cell] = free[cell] === 1 && nearRoad(p, done) ? 1 : 0;
  }
  const start = cellOf(from);
  const goal = cellOf(to);
  const goalAt = at(goal);
  const cost = new Float64Array(cols * rows).fill(Number.POSITIVE_INFINITY);
  const came = new Int32Array(cols * rows).fill(-1);
  cost[start] = 0;
  // A small binary heap of [priority, cell].
  const heap: [number, number][] = [[0, start]];
  const push = (item: [number, number]) => {
    heap.push(item);
    for (let i = heap.length - 1; i > 0;) {
      const parent = (i - 1) >> 1;
      const [a, b] = [heap[parent], heap[i]];
      if (a === undefined || b === undefined || a[0] <= b[0]) break;
      [heap[parent], heap[i]] = [b, a];
      i = parent;
    }
  };
  const pop = () => {
    const top = heap[0];
    const last = heap.pop();
    if (heap.length > 0 && last !== undefined) {
      heap[0] = last;
      for (let i = 0; ;) {
        const [l, r] = [2 * i + 1, 2 * i + 2];
        let m = i;
        if ((heap[l]?.[0] ?? Infinity) < (heap[m]?.[0] ?? Infinity)) m = l;
        if ((heap[r]?.[0] ?? Infinity) < (heap[m]?.[0] ?? Infinity)) m = r;
        if (m === i) break;
        const [a, b] = [heap[i], heap[m]];
        if (a === undefined || b === undefined) break;
        [heap[i], heap[m]] = [b, a];
        i = m;
      }
    }
    return top;
  };
  for (let item = pop(); item !== undefined; item = pop()) {
    const [, cell] = item;
    if (cell === goal) break;
    const cx = cell % cols;
    const cy = Math.floor(cell / cols);
    for (let ox = -1; ox <= 1; ox++)
      for (let oy = -1; oy <= 1; oy++) {
        const nx = cx + ox;
        const ny = cy + oy;
        if ((ox === 0 && oy === 0) || nx < 0 || ny < 0 || nx >= cols || ny >= rows) continue;
        const next = ny * cols + nx;
        if (free[next] !== 1 && next !== goal) continue;
        const step = Math.hypot(ox, oy) * CELL * (crowded[next] === 1 ? 2 : 1);
        const total = (cost[cell] ?? 0) + step;
        if (total >= (cost[next] ?? Infinity)) continue;
        cost[next] = total;
        came[next] = cell;
        const p = at(next);
        push([total + Math.hypot(p.x - goalAt.x, p.y - goalAt.y), next]);
      }
  }
  if (came[goal] === -1 && goal !== start) return undefined;
  const cells: Point[] = [];
  for (let cell = goal; cell !== -1; cell = came[cell] ?? -1) cells.unshift(at(cell));
  cells[0] = from;
  cells[cells.length - 1] = to;

  // Pull the path taut: from each point, jump to the farthest one in a clear straight line.
  const visible = (a: Point, b: Point) => {
    const steps = Math.ceil(Math.hypot(b.x - a.x, b.y - a.y) / 3);
    for (let k = 1; k < steps; k++) {
      const t = k / steps;
      if (!clearOfIsles({ x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t }, others))
        return false;
    }
    return true;
  };
  const taut: Point[] = [from];
  for (let i = 0; i < cells.length - 1;) {
    let j = cells.length - 1;
    while (j > i + 1 && !visible(cells[i] ?? from, cells[j] ?? to)) j--;
    taut.push(cells[j] ?? to);
    i = j;
  }

  // Round the corners as much as stays clear; straight segments always do.
  for (const tension of [1 / 6, 1 / 9, 1 / 14, 0]) {
    const curve = smoothThrough(taut, tension);
    const samples = curve.flatMap((segment, k) => sampleCubic(segment).slice(k === 0 ? 0 : 1));
    if (tension === 0 || samples.every((p) => clearOfIsles(p, others)))
      return { ...ids, curve, samples };
  }
  return undefined;
}

/** Catmull-Rom through the points as cubic segments; `tension` 0 gives straight segments. */
function smoothThrough(points: readonly Point[], tension: number): Cubic[] {
  const get = (i: number) => points[Math.max(0, Math.min(points.length - 1, i))] ?? { x: 0, y: 0 };
  return points.slice(0, -1).map((_, i) => {
    const [p0, p1, p2, p3] = [get(i - 1), get(i), get(i + 1), get(i + 2)];
    return [
      p1,
      { x: p1.x + (p2.x - p0.x) * tension, y: p1.y + (p2.y - p0.y) * tension },
      { x: p2.x - (p3.x - p1.x) * tension, y: p2.y - (p3.y - p1.y) * tension },
      p2,
    ];
  });
}

/** The project's dashed outer coast is drawn at this multiple of its radius. */
export const PROJECT_COAST = 1.12;
/** Open water kept between a road and any island it does not start or end at. */
const CLEARANCE = 5;
/** Roads closer than this read as one; the router steers them apart where it can. */
const ROAD_SPACING = 10;
/** Half the widest road stroke, so the canvas never clips a road. */
const ROAD_HALF = 3;
/** The gentle bow of an unobstructed road, as a share of its length. */
const BOW = 0.12;
const SAMPLES = 40;

/**
 * The curves a road may take, gentlest first: a single bow either side, then an S through two
 * offsets, so a road can swing round an island or thread the water between two.
 */
function candidateCurves(
  from: Point,
  to: Point,
  sCurves: boolean,
): { curve: Cubic; bend: number }[] {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const span = Math.hypot(dx, dy) || 1;
  const nx = -dy / span;
  const ny = dx / span;
  const at = (t: number, off: number): Point => ({
    x: from.x + dx * t + nx * off * span,
    y: from.y + dy * t + ny * off * span,
  });
  const out: { curve: Cubic; bend: number }[] = [];
  if (sCurves) {
    const offsets = [0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.65, 0.8].flatMap((o) =>
      o === 0 ? [0] : [o, -o],
    );
    for (const a of offsets)
      for (const b of offsets)
        if (a !== b) out.push({ curve: [from, at(1 / 3, a), at(2 / 3, b), to], bend: (a + b) / 2 });
    return out;
  }
  for (const bow of [0, 0.06, 0.12, 0.2, 0.3, 0.42, 0.56, 0.72].flatMap((b) =>
    b === 0 ? [0] : [b, -b],
  )) {
    // A quadratic with its control point `bow` off the midpoint, as a cubic.
    const q = at(0.5, 2 * bow);
    out.push({
      curve: [
        from,
        { x: from.x + (2 / 3) * (q.x - from.x), y: from.y + (2 / 3) * (q.y - from.y) },
        { x: to.x + (2 / 3) * (q.x - to.x), y: to.y + (2 / 3) * (q.y - to.y) },
        to,
      ],
      bend: bow,
    });
  }
  return out;
}

function sampleCubic([p0, p1, p2, p3]: Cubic): Point[] {
  return Array.from({ length: SAMPLES + 1 }, (_, i) => {
    const t = i / SAMPLES;
    const u = 1 - t;
    const a = u * u * u;
    const b = 3 * u * u * t;
    const c = 3 * u * t * t;
    const d = t * t * t;
    return {
      x: a * p0.x + b * p1.x + c * p2.x + d * p3.x,
      y: a * p0.y + b * p1.y + c * p2.y + d * p3.y,
    };
  });
}

function cubicPath(curve: readonly Cubic[]): string {
  const [first] = curve;
  if (first === undefined) return '';
  const p = (point: Point) => `${fixed(point.x)} ${fixed(point.y)}`;
  return `M${p(first[0])}${curve.map(([, c1, c2, end]) => ` C${p(c1)} ${p(c2)} ${p(end)}`).join('')}`;
}

/** Sample a road's path (a move, then cubic segments) back into points, for tests. */
export function roadPoints(d: string): Point[] {
  const n = d.match(/-?\d+(?:\.\d+)?/g)?.map(Number) ?? [];
  const points: Point[] = [];
  for (let i = 2; i + 5 < n.length; i += 6) {
    const pt = (k: number): Point => ({ x: n[k] ?? 0, y: n[k + 1] ?? 0 });
    points.push(...sampleCubic([pt(i - 2), pt(i), pt(i + 2), pt(i + 4)]));
  }
  return points;
}

/** Lines of a zone's name inside its island: wrapped, never cut short. */
export function islandLabel(name: string, layout: WorldLayout): string[] {
  return wrapLines(name, layout.nameChars, Number.POSITIVE_INFINITY);
}

/** An organic island outline around (cx, cy), deterministic per branch. */
export function islandPath(cx: number, cy: number, radius: number, id: string): string {
  const next = random(seedFrom(id));
  const count = 11;
  const points = Array.from({ length: count }, (_, i) => {
    const angle = (2 * Math.PI * i) / count;
    const r = radius * (0.86 + next() * 0.14);
    return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
  });
  return closedSmoothPath(points);
}
