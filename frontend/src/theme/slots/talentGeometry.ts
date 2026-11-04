/** Pure layout for the RPG talent constellation: layers of nodes, one block per subtree. */
import type { TalentNode } from '../../api/types';

/**
 * Sizes for one drawing. `compact` fits a phone and grows downwards; `wide` uses the room a
 * desktop has and grows across, so the tree reads left to right instead of as a tall column.
 */
export interface Metrics {
  /** Layers run across (each a column) rather than down (each a row). */
  horizontal: boolean;
  /** Distance between columns; across, the distance between layers. */
  column: number;
  /** Distance between rows; across, the distance between siblings in a layer. */
  row: number;
  radius: number;
  /** Space under a node taken by its label, which links must clear. */
  labelDrop: number;
  /** Characters per label line, and the line height. */
  labelChars: number;
  line: number;
  minColumns: number;
}

export type ConstellationSize = 'compact' | 'wide';

export const METRICS: Record<ConstellationSize, Metrics> = {
  compact: {
    horizontal: false,
    column: 148,
    row: 150,
    radius: 24,
    labelDrop: 58,
    labelChars: 17,
    line: 17,
    minColumns: 2,
  },
  wide: {
    horizontal: true,
    column: 250,
    row: 170,
    radius: 32,
    labelDrop: 76,
    labelChars: 24,
    line: 22,
    minColumns: 4,
  },
};

export const NODE_RADIUS = METRICS.compact.radius;
const MARGIN = 20;
/** Room above the first layer of a block for its heading. */
const HEADING = 30;

export interface ConstellationNode {
  node: TalentNode;
  x: number;
  y: number;
}

export interface ConstellationLink {
  from: string;
  to: string;
  d: string;
}

export interface ConstellationBlock {
  subtree: string;
  /** Where the block's heading sits. */
  x: number;
  y: number;
}

export interface Constellation {
  metrics: Metrics;
  width: number;
  height: number;
  blocks: ConstellationBlock[];
  nodes: ConstellationNode[];
  links: ConstellationLink[];
}

/** Layer of each node within its own subtree: 0 with no in-subtree parent, else one below its deepest. */
function layers(nodes: readonly TalentNode[]): Map<string, number> {
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const memo = new Map<string, number>();
  const depth = (node: TalentNode, seen: ReadonlySet<string>): number => {
    const known = memo.get(node.id);
    if (known !== undefined) return known;
    let layer = 0;
    for (const parentId of node.parents) {
      const parent = byId.get(parentId);
      // Parents in another subtree draw a link but do not push the node down; `seen` stops cycles.
      if (parent?.subtree === node.subtree && !seen.has(parentId))
        layer = Math.max(layer, depth(parent, new Set([...seen, node.id])) + 1);
    }
    memo.set(node.id, layer);
    return layer;
  };
  for (const node of nodes) depth(node, new Set());
  return memo;
}

const fixed = (n: number) => n.toFixed(1);

/**
 * A smooth link from a parent to its child: down from under the parent's label to the top of the
 * child, or, across, from the parent's right to the child's left (labels sit under the nodes).
 */
export function linkPath(
  from: { x: number; y: number },
  to: { x: number; y: number },
  metrics: Metrics = METRICS.compact,
): string {
  if (metrics.horizontal) {
    const x1 = from.x + metrics.radius + 6;
    const x2 = to.x - metrics.radius - 6;
    const bend = Math.max(10, Math.abs(x2 - x1) / 2);
    return `M${fixed(x1)} ${fixed(from.y)} C${fixed(x1 + bend)} ${fixed(from.y)} ${fixed(x2 - bend)} ${fixed(to.y)} ${fixed(x2)} ${fixed(to.y)}`;
  }
  const y1 = from.y + metrics.radius + metrics.labelDrop;
  const y2 = to.y - metrics.radius;
  const bend = Math.max(10, Math.abs(y2 - y1) / 2);
  return `M${fixed(from.x)} ${fixed(y1)} C${fixed(from.x)} ${fixed(y1 + bend)} ${fixed(to.x)} ${fixed(y2 - bend)} ${fixed(to.x)} ${fixed(y2)}`;
}

/**
 * Lay the nodes out: subtrees stacked top to bottom (the API lists the general subtree first).
 * Compact: each subtree's layers stacked below its heading, siblings spread across the width.
 * Wide: each subtree's layers run left to right, siblings stacked in a column. Within a layer,
 * nodes are ordered by the mean position of their parents (see `ordered`). Links to a parent in
 * another subtree simply run to the child.
 */
export function planConstellation(
  nodes: readonly TalentNode[],
  size: ConstellationSize = 'compact',
): Constellation {
  const metrics = METRICS[size];
  if (nodes.length === 0) return { metrics, width: 0, height: 0, blocks: [], nodes: [], links: [] };
  const layerOf = layers(nodes);
  const subtrees = [...new Set(nodes.map((node) => node.subtree))];

  const grouped = subtrees.map((subtree) => {
    const members = nodes.filter((node) => node.subtree === subtree);
    const rows = new Map<number, TalentNode[]>();
    for (const node of members) {
      const layer = layerOf.get(node.id) ?? 0;
      rows.set(layer, [...(rows.get(layer) ?? []), node]);
    }
    return { subtree, rows: [...rows.entries()].sort(([a], [b]) => a - b).map(([, row]) => row) };
  });
  if (metrics.horizontal) return finish(metrics, ...across(grouped, metrics));
  const columns = Math.max(
    metrics.minColumns,
    ...grouped.flatMap((group) => group.rows.map((r) => r.length)),
  );
  const width = columns * metrics.column + 2 * MARGIN;
  const slot = (i: number, count: number) => width / 2 + (i - (count - 1) / 2) * metrics.column;

  const placed: ConstellationNode[] = [];
  const xOf = new Map<string, number>();
  const blocks: ConstellationBlock[] = [];
  let top = MARGIN;
  for (const group of grouped) {
    blocks.push({ subtree: group.subtree, x: width / 2, y: top + 14 });
    top += HEADING;
    for (const row of ordered(group.rows, xOf, slot)) {
      row.forEach((node, i) => {
        const x = slot(i, row.length);
        xOf.set(node.id, x);
        placed.push({ node, x, y: top + metrics.row / 2 - 8 });
      });
      top += metrics.row;
    }
    top += 8;
  }
  return finish(metrics, width, top + MARGIN - 8, blocks, placed);
}

interface Group {
  subtree: string;
  rows: TalentNode[][];
}

/**
 * Each layer in turn, ordered by the mean position of its placed parents (the barycentre
 * heuristic, ties kept in API order), so sibling branches stay beside their own parents and links
 * do not cross. The caller fills `positionOf` as it places each layer.
 */
function* ordered(
  rows: readonly TalentNode[][],
  positionOf: ReadonlyMap<string, number>,
  slot: (i: number, count: number) => number,
): Generator<TalentNode[]> {
  for (const unordered of rows) {
    const keyed = unordered.map((node, i) => {
      const parents = node.parents.flatMap((id) => positionOf.get(id) ?? []);
      const key =
        parents.length === 0
          ? slot(i, unordered.length)
          : parents.reduce((sum, x) => sum + x, 0) / parents.length;
      return { node, key, i };
    });
    yield keyed.sort((a, b) => a.key - b.key || a.i - b.i).map((entry) => entry.node);
  }
}

/**
 * The wide drawing: each subtree a band, its layers as columns from left to right and siblings
 * stacked in a column, the bands one under the other.
 */
function across(
  grouped: readonly Group[],
  metrics: Metrics,
): [number, number, ConstellationBlock[], ConstellationNode[]] {
  const columns = Math.max(metrics.minColumns, ...grouped.map((group) => group.rows.length));
  const width = columns * metrics.column + 2 * MARGIN;
  const placed: ConstellationNode[] = [];
  const yOf = new Map<string, number>();
  const blocks: ConstellationBlock[] = [];
  let top = MARGIN;
  for (const group of grouped) {
    blocks.push({ subtree: group.subtree, x: width / 2, y: top + 14 });
    top += HEADING;
    const tallest = Math.max(...group.rows.map((row) => row.length));
    const height = tallest * metrics.row;
    // Centre each node together with the label hanging below it in its slot.
    const middle = top + height / 2 - metrics.labelDrop / 2 + 8;
    const slot = (i: number, count: number) => middle + (i - (count - 1) / 2) * metrics.row;
    const left = width / 2 - (group.rows.length * metrics.column) / 2;
    let layer = 0;
    for (const row of ordered(group.rows, yOf, slot)) {
      const x = left + (layer + 0.5) * metrics.column;
      row.forEach((node, i) => {
        const y = slot(i, row.length);
        yOf.set(node.id, y);
        placed.push({ node, x, y });
      });
      layer += 1;
    }
    top += height + 8;
  }
  return [width, top + MARGIN - 8, blocks, placed];
}

function finish(
  metrics: Metrics,
  width: number,
  height: number,
  blocks: ConstellationBlock[],
  placed: ConstellationNode[],
): Constellation {
  const at = new Map(placed.map((entry) => [entry.node.id, entry]));
  const links = placed.flatMap((child) =>
    child.node.parents.flatMap((parentId) => {
      const parent = at.get(parentId);
      return parent === undefined
        ? []
        : [{ from: parentId, to: child.node.id, d: linkPath(parent, child, metrics) }];
    }),
  );
  return { metrics, width, height, blocks, nodes: placed, links };
}
