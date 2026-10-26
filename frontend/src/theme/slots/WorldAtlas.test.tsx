import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import type { BranchSummary, ThemeFlavour } from '../../api/types';
import { renderInRouter, withMode } from '../../test/render';
import { BranchOverview } from '.';
import {
  NARROW_WORLD,
  PROJECT_COAST,
  WIDE_WORLD,
  hubOf,
  islandLabel,
  planWorld,
  roadPoints,
  type WorldPlan,
} from './worldGeometry';

function branch(
  id: string,
  title: string,
  overrides: Partial<BranchSummary> = {},
  exerciseCount = 2,
): BranchSummary {
  return {
    id,
    title,
    summary: `${title} summary.`,
    unlocked: true,
    requires: id === 'starter' ? [] : ['starter'],
    kind: 'standard',
    pro: false,
    passed_count: 0,
    exercises: Array.from({ length: exerciseCount }, (_, i) => ({
      id: `${id}.exercise-${i + 1}`,
      title: `${title} exercise ${i + 1}`,
      tier: 'beginner' as const,
      xp: 50,
      prerequisites: [],
      skills: [],
      status:
        i === 0 && overrides.unlocked !== false ? ('available' as const) : ('locked' as const),
      pro: false,
      entitled: true,
    })),
    ...overrides,
  };
}

const starter = branch('starter', 'Foundations', { passed_count: 2 });
const retrieval = branch('retrieval', 'Retrieval', { unlocked: false });
const protocols = branch('protocols', 'Protocols');
const orchestration = branch('orchestration', 'Orchestration', { unlocked: false });

/** The Phase 3 graph: six zones from the hub, and Knowledge graphs reached through Retrieval. */
const eight = [
  starter,
  branch('retrieval', 'Retrieval'),
  branch('protocols', 'Protocols'),
  branch('orchestration', 'Orchestration'),
  branch('memory', 'Memory'),
  branch('context-engineering', 'Context engineering'),
  branch('evals', 'Evals and guardrails'),
  branch('knowledge-graphs', 'Knowledge graphs', { requires: ['retrieval'] }),
];

/** A synthetic project graph: the hub, seven zones, and two projects that each require four. */
const seven = Array.from({ length: 7 }, (_, i) => branch(`zone-${i}`, `Zone ${i}`));
const PROJECT_REQUIRES = {
  'project-one': ['zone-0', 'zone-1', 'zone-2', 'zone-3'],
  'project-two': ['zone-3', 'zone-4', 'zone-5', 'zone-6'],
};
const ten = [
  starter,
  branch('project-one', 'Project one', {
    kind: 'project',
    pro: false,
    requires: PROJECT_REQUIRES['project-one'],
  }),
  ...seven,
  branch('project-two', 'Project two', {
    kind: 'project',
    pro: false,
    requires: PROJECT_REQUIRES['project-two'],
    unlocked: false,
  }),
];

/** The real catalogue (content/branches): eight zones and two guided projects, in data order. */
const real = [
  starter,
  branch('retrieval', 'Retrieval'),
  branch('protocols', 'Protocols & tools'),
  branch('orchestration', 'Orchestration'),
  branch('knowledge-graphs', 'Knowledge graphs', { requires: ['retrieval'] }),
  branch('memory', 'Memory'),
  branch('context-engineering', 'Context engineering'),
  branch('evals', 'Evals & guardrails'),
  branch('project-copilot', 'Support copilot', {
    kind: 'project',
    requires: ['retrieval', 'memory', 'context-engineering', 'evals'],
  }),
  branch('project-research', 'Research agent team', {
    kind: 'project',
    requires: ['protocols', 'orchestration', 'knowledge-graphs', 'evals'],
  }),
];
/** The RPG names of the real zones (content/themes/rpg/flavour.yaml). */
const REAL_NAMES = [
  'The Foundry Vale',
  'The Deepstacks',
  "The Conductor's Spire",
  'The Wireworks',
  'The Loomhall',
  'The Hall of Hours',
  'The Mapwright Marches',
  'The Assay Court',
  'The Crossroads Inn',
  'The Lanternwatch Expedition',
];

/** Islands a road runs over that it neither starts nor ends at. */
function roadsOverIslands(plan: WorldPlan): string[] {
  const over: string[] = [];
  for (const route of plan.routes)
    for (const node of plan.nodes) {
      if (node.branch.id === route.from || node.branch.id === route.to) continue;
      const coast = node.radius * (node.branch.kind === 'project' ? PROJECT_COAST : 1);
      if (roadPoints(route.d).some((p) => Math.hypot(p.x - node.x, p.y - node.y) < coast))
        over.push(`${route.from} to ${route.to} over ${node.branch.id}`);
    }
  return over;
}

const two = [starter, retrieval];
/** Deliberately not starter-first, so the hub must come from the data. */
const four = [retrieval, starter, protocols, orchestration];

const flavour: ThemeFlavour = {
  paths: {},
  bosses: {},
  branches: {
    starter: { name: 'The Foundry Vale', epithet: 'Where journeys begin', lore: 'Old crafts.' },
    retrieval: { name: 'The Sunken Archive', epithet: 'Lost in the deep', lore: 'Drowned stacks.' },
  },
  quests: {},
};

const renderWorld = (branches: readonly BranchSummary[], entry = '/') =>
  renderInRouter(withMode('rpg', <BranchOverview branches={branches} />), flavour, entry);

describe('world layout', () => {
  it('puts the branch the others require at the centre, whatever the data order', () => {
    expect(hubOf(four)?.id).toBe('starter');
    expect(hubOf([retrieval])?.id).toBe('retrieval');
    expect(hubOf([])).toBeUndefined();
  });

  it.each([1, 2, 3, 4, 5, 8, 13])(
    'keeps %i outer zones apart and inside the canvas, the hub first',
    (count) => {
      const outer = Array.from({ length: count }, (_, i) => branch(`zone-${i}`, `Zone ${i}`));
      for (const layout of [WIDE_WORLD, NARROW_WORLD]) {
        const plan = planWorld([starter, ...outer], layout);
        expect(plan.nodes).toHaveLength(count + 1);
        expect(plan.routes).toHaveLength(count);
        for (const [i, a] of plan.nodes.entries()) {
          expect(a.x - a.radius).toBeGreaterThanOrEqual(0);
          expect(a.y - a.radius).toBeGreaterThanOrEqual(0);
          expect(a.x + a.radius).toBeLessThanOrEqual(plan.width);
          expect(a.y + a.radius).toBeLessThanOrEqual(plan.height);
          for (const b of plan.nodes.slice(i + 1))
            expect(Math.hypot(a.x - b.x, a.y - b.y)).toBeGreaterThan(a.radius + b.radius);
        }
        expect(plan.nodes[0]?.branch.id).toBe('starter');
      }
    },
  );

  it.each([
    ['desktop', WIDE_WORLD],
    ['375px', NARROW_WORLD],
  ])('keeps eight zones apart and inside the canvas at %s', (_name, layout) => {
    const plan = planWorld(eight, layout);
    expect(plan.nodes).toHaveLength(8);
    expect(plan.routes).toHaveLength(7);
    for (const [i, a] of plan.nodes.entries()) {
      expect(a.x - a.radius).toBeGreaterThanOrEqual(0);
      expect(a.y - a.radius).toBeGreaterThanOrEqual(0);
      expect(a.x + a.radius).toBeLessThanOrEqual(plan.width);
      expect(a.y + a.radius).toBeLessThanOrEqual(plan.height);
      for (const b of plan.nodes.slice(i + 1))
        expect(Math.hypot(a.x - b.x, a.y - b.y)).toBeGreaterThan(a.radius + b.radius);
    }
  });

  it('keeps the eight-zone map readable on a 375px screen', () => {
    // The SVG scales to its container, so a canvas close to the screen's width keeps text legible.
    expect(planWorld(eight, NARROW_WORLD).width).toBeLessThanOrEqual(480);
  });

  it.each([
    ['desktop', WIDE_WORLD],
    ['375px', NARROW_WORLD],
  ])(
    'draws each road from the zone it requires, and puts that zone outward at %s',
    (_n, layout) => {
      const plan = planWorld(eight, layout);
      const from = Object.fromEntries(plan.routes.map((route) => [route.to, route.from]));
      expect(from['knowledge-graphs']).toBe('retrieval');
      for (const id of ['retrieval', 'protocols', 'orchestration', 'memory', 'evals'])
        expect(from[id]).toBe('starter');
      expect(from['context-engineering']).toBe('starter');

      const at = (id: string) => plan.nodes.find((node) => node.branch.id === id);
      const [hub, parent, child] = [at('starter'), at('retrieval'), at('knowledge-graphs')];
      const away = (node: typeof hub) =>
        Math.hypot((node?.x ?? 0) - (hub?.x ?? 0), (node?.y ?? 0) - (hub?.y ?? 0));
      expect(away(child)).toBeGreaterThan(away(parent));
      // The road leaves the parent's island, not the hub's.
      const road = plan.routes.find((route) => route.to === 'knowledge-graphs');
      expect(road?.d.startsWith(`M${parent?.x.toFixed(1)} ${parent?.y.toFixed(1)}`)).toBe(true);
    },
  );

  it.each([
    ['desktop', WIDE_WORLD],
    ['375px', NARROW_WORLD],
  ])('keeps ten branches with two projects apart and inside the canvas at %s', (_name, layout) => {
    const plan = planWorld(ten, layout);
    expect(plan.nodes).toHaveLength(10);
    for (const [i, a] of plan.nodes.entries()) {
      expect(a.x - a.radius).toBeGreaterThanOrEqual(0);
      expect(a.y - a.radius).toBeGreaterThanOrEqual(0);
      expect(a.x + a.radius).toBeLessThanOrEqual(plan.width);
      expect(a.y + a.radius).toBeLessThanOrEqual(plan.height);
      for (const b of plan.nodes.slice(i + 1))
        expect(Math.hypot(a.x - b.x, a.y - b.y)).toBeGreaterThan(a.radius + b.radius);
    }
  });

  it.each([
    ['desktop', WIDE_WORLD],
    ['375px', NARROW_WORLD],
  ])(
    'draws a road to a project from each zone it requires, and rings projects outside at %s',
    (_name, layout) => {
      const plan = planWorld(ten, layout);
      // One road from the hub to each of the seven zones, and four to each project.
      expect(plan.routes).toHaveLength(7 + 4 + 4);
      for (const [project, required] of Object.entries(PROJECT_REQUIRES)) {
        const from = plan.routes.filter((route) => route.to === project).map((route) => route.from);
        expect(from.sort()).toEqual(required);
      }

      const hub = plan.nodes[0];
      const away = (node: (typeof plan.nodes)[number]) =>
        Math.hypot(node.x - (hub?.x ?? 0), node.y - (hub?.y ?? 0));
      const zones = plan.nodes.filter((node) => node.branch.kind !== 'project');
      for (const project of plan.nodes.filter((node) => node.branch.kind === 'project'))
        for (const zone of zones) expect(away(project)).toBeGreaterThan(away(zone));
    },
  );

  it.each([
    ['desktop', WIDE_WORLD],
    ['375px', NARROW_WORLD],
  ])('fits the planned guided projects beside the eight zones at %s', (_name, layout) => {
    const planned = [
      ...eight,
      branch('project-copilot', 'Support copilot', {
        kind: 'project',
        pro: false,
        requires: ['retrieval', 'memory', 'context-engineering', 'evals'],
      }),
      branch('project-research', 'Research agent team', {
        kind: 'project',
        pro: false,
        requires: ['protocols', 'orchestration', 'knowledge-graphs', 'evals'],
      }),
    ];
    const plan = planWorld(planned, layout);
    expect(plan.routes).toHaveLength(7 + 4 + 4);
    for (const [i, a] of plan.nodes.entries())
      for (const b of plan.nodes.slice(i + 1))
        expect(Math.hypot(a.x - b.x, a.y - b.y)).toBeGreaterThan(a.radius + b.radius);
    if (!layout.wide) expect(plan.width).toBeLessThanOrEqual(480);
  });

  it('lists projects last, after the zones they draw on', () => {
    const order = planWorld(ten, WIDE_WORLD).nodes.map((node) => node.branch.id);
    expect(order[0]).toBe('starter');
    expect(order.slice(-2)).toEqual(['project-one', 'project-two']);
  });

  it('keeps the ten-branch map close to a phone screen wide', () => {
    expect(planWorld(ten, NARROW_WORLD).width).toBeLessThanOrEqual(480);
  });

  it('orders the nodes hub first, then each ring zone followed by the zones beyond it', () => {
    const order = planWorld(eight, WIDE_WORLD).nodes.map((node) => node.branch.id);
    expect(order[0]).toBe('starter');
    expect(order.indexOf('knowledge-graphs')).toBe(order.indexOf('retrieval') + 1);
  });

  it('ignores a requirement cycle and a requirement outside the data', () => {
    const plan = planWorld(
      [
        starter,
        branch('a', 'A', { requires: ['starter', 'b'] }),
        branch('b', 'B', { requires: ['starter', 'a'] }),
        branch('c', 'C', { requires: ['elsewhere'] }),
      ],
      WIDE_WORLD,
    );
    expect(plan.routes).toHaveLength(3);
    expect(plan.routes.find((route) => route.to === 'c')?.from).toBe('starter');
    expect(plan.routes.map((route) => route.from)).toContain('starter');
  });

  it.each([1, 2, 3, 5])(
    'fits the narrow canvas to the islands, with no empty band, for %i outer zones',
    (count) => {
      const outer = Array.from({ length: count }, (_, i) => branch(`zone-${i}`, `Zone ${i}`));
      const plan = planWorld([starter, ...outer], NARROW_WORLD);
      const top = Math.min(...plan.nodes.map((node) => node.y - node.radius));
      const bottom = Math.max(...plan.nodes.map((node) => node.y + node.radius));
      const left = Math.min(...plan.nodes.map((node) => node.x - node.radius));
      const right = Math.max(...plan.nodes.map((node) => node.x + node.radius));
      // The same margin on every side, and nothing else.
      expect(top).toBeLessThanOrEqual(32);
      expect(left).toBeLessThanOrEqual(32);
      expect(plan.height - bottom).toBeCloseTo(top, 0);
      expect(plan.width - right).toBeCloseTo(left, 0);
    },
  );

  it.each([
    ['desktop', WIDE_WORLD],
    ['390px', NARROW_WORLD],
  ])('routes every road of the real catalogue clear of other islands at %s', (_name, layout) => {
    for (const plan of [planWorld(real, layout), planWorld(ten, layout), planWorld(eight, layout)])
      expect(roadsOverIslands(plan)).toEqual([]);
    expect(planWorld(real, layout).routes).toHaveLength(7 + 4 + 4);
  });

  it.each([
    ['desktop', WIDE_WORLD],
    ['390px', NARROW_WORLD],
  ])('crops the real catalogue to what is drawn, with no empty band, at %s', (_name, layout) => {
    const plan = planWorld(real, layout);
    const coast = (node: (typeof plan.nodes)[number]) =>
      node.radius * (node.branch.kind === 'project' ? PROJECT_COAST : 1);
    const points = [
      ...plan.nodes.flatMap((node) => [
        { x: node.x - coast(node), y: node.y - coast(node) },
        { x: node.x + coast(node), y: node.y + coast(node) },
      ]),
      ...plan.routes.flatMap((route) => roadPoints(route.d)),
    ];
    const xs = points.map((p) => p.x);
    const ys = points.map((p) => p.y);
    // Every side is within the margin (28) plus half a road of something drawn.
    expect(Math.min(...xs)).toBeLessThanOrEqual(32);
    expect(Math.min(...ys)).toBeLessThanOrEqual(32);
    expect(plan.width - Math.max(...xs)).toBeLessThanOrEqual(32);
    expect(plan.height - Math.max(...ys)).toBeLessThanOrEqual(32);
    expect(Math.min(...xs)).toBeGreaterThanOrEqual(0);
    expect(Math.min(...ys)).toBeGreaterThanOrEqual(0);
    if (!layout.wide) expect(plan.width).toBeLessThanOrEqual(480);
  });

  it.each([
    ['desktop', WIDE_WORLD],
    ['390px', NARROW_WORLD],
  ])(
    'wraps every real zone name onto at most three lines, never cutting it, at %s',
    (_n, layout) => {
      for (const name of REAL_NAMES) {
        const lines = islandLabel(name, layout);
        expect(lines.join(' ')).toBe(name);
        expect(lines.length).toBeLessThanOrEqual(3);
        expect(lines.some((line) => line.endsWith('…'))).toBe(false);
      }
    },
  );

  it('keeps the narrow map close to a phone screen wide for four branches', () => {
    expect(planWorld(four, NARROW_WORLD).width).toBeLessThanOrEqual(400);
  });
});

describe('world atlas', () => {
  it.each([
    ['two', two],
    ['four', four],
  ])('draws a road from the hub to every other zone with %s branches', async (_name, branches) => {
    await renderWorld(branches);

    const map = await screen.findByRole('img', { name: 'The known world' });
    expect(map).toHaveAccessibleDescription(/starter zone at the centre/);
    expect(map.querySelectorAll('[data-route]')).toHaveLength(branches.length - 1);
    expect(screen.getByRole('heading', { level: 2, name: 'The known world' })).toBeInTheDocument();
  });

  it('draws the road to a zone beyond another from that zone, and lists it after its parent', async () => {
    await renderWorld(eight);

    const map = await screen.findByRole('img', { name: 'The known world' });
    expect(map.querySelectorAll('[data-route]')).toHaveLength(7);
    expect(
      map.querySelector('[data-route-from="retrieval"][data-route-to="knowledge-graphs"]'),
    ).not.toBeNull();
    const links = within(screen.getByRole('navigation', { name: 'zones' })).getAllByRole('link');
    expect(links.map((link) => link.getAttribute('href'))[0]).toBe('/?zone=starter');
    const hrefs = links.map((link) => link.getAttribute('href'));
    expect(hrefs.indexOf('/?zone=knowledge-graphs')).toBe(hrefs.indexOf('/?zone=retrieval') + 1);
  });

  it('names projects as expeditions, last in the list, with a closed road from each zone', async () => {
    await renderWorld(ten);

    const map = await screen.findByRole('img', { name: 'The known world' });
    expect(map.querySelectorAll('[data-route-to="project-two"][data-route="closed"]')).toHaveLength(
      4,
    );
    expect(map.querySelectorAll('[data-route-to="project-one"][data-route="open"]')).toHaveLength(
      4,
    );
    expect(map.querySelectorAll('[data-project-coast]')).toHaveLength(2);
    const links = within(screen.getByRole('navigation', { name: 'zones' })).getAllByRole('link');
    expect(links.slice(-2).map((link) => link.getAttribute('href'))).toEqual([
      '/?zone=project-one',
      '/?zone=project-two',
    ]);
    expect(links.at(-1)).toHaveTextContent(/^Expedition/);
    expect(links[1]).not.toHaveTextContent('Expedition');
  });

  it('heads an expedition with its small labels on one line', async () => {
    await renderWorld(
      [...ten.slice(0, -1), { ...ten[ten.length - 1], pro: true } as BranchSummary],
      '/?zone=project-two',
    );
    const heading = await screen.findByRole('heading', { level: 2, name: 'Project two' });
    const labels = heading.previousElementSibling;
    expect(labels?.tagName).toBe('P');
    expect(labels).toHaveTextContent(/^Expedition · , Guild · Pro.* · , 2 quests$/);
    // Nothing else small and stacked between the labels and the title.
    expect(labels?.parentElement?.querySelectorAll('p.label-caps')).toHaveLength(1);
  });

  it('shows locked zones under fog with closed roads, and says so in words', async () => {
    await renderWorld(four);

    const map = await screen.findByRole('img', { name: 'The known world' });
    expect(map.querySelectorAll('[data-route="closed"]')).toHaveLength(2);
    expect(map.querySelectorAll('[data-route="open"]')).toHaveLength(1);
    expect(map.querySelectorAll('[filter="url(#world-fog)"]')).toHaveLength(2);

    const archive = screen.getByRole('link', { name: /^The Sunken Archive/ });
    expect(archive).toHaveTextContent('Shrouded');
    expect(archive).toHaveTextContent('lies in fog until The Foundry Vale is conquered');
    expect(screen.getByRole('link', { name: /^Protocols/ })).toHaveTextContent('Open');
    expect(screen.getByRole('link', { name: /^The Foundry Vale/ })).toHaveTextContent('Conquered');
  });

  it('offers every zone as a link in an accessible list, hub first then clockwise, with real titles', async () => {
    await renderWorld(four);

    const list = within(await screen.findByRole('navigation', { name: 'zones' }));
    const links = list.getAllByRole('link');
    expect(links.map((link) => link.getAttribute('href'))).toEqual(
      [starter, retrieval, protocols, orchestration].map((zone) => `/?zone=${zone.id}`),
    );
    expect(links[0]).toHaveTextContent('Foundations');
    expect(links[0]).toHaveTextContent('2 of 2 conquered');
  });

  it('selects a zone with the keyboard, shows its route, and returns to the world', async () => {
    const user = userEvent.setup();
    const { router } = await renderWorld(four);

    await screen.findByRole('navigation', { name: 'zones' });
    await user.tab();
    expect(screen.getByRole('link', { name: /^The Foundry Vale/ })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole('link', { name: /^The Sunken Archive/ })).toHaveFocus();
    await user.tab({ shift: true });
    await user.keyboard('{Enter}');

    const zone = await screen.findByRole('region', { name: 'The Foundry Vale' });
    expect(router.state.location.search).toEqual({ zone: 'starter' });
    expect(within(zone).getByRole('link', { name: /Foundations exercise 1/ })).toBeInTheDocument();
    expect(screen.queryByRole('img', { name: 'The known world' })).not.toBeInTheDocument();
    await waitFor(() => {
      expect(within(zone).getByRole('heading', { level: 2 })).toHaveFocus();
    });

    await user.click(screen.getByRole('link', { name: 'Back to the world' }));
    expect(await screen.findByRole('img', { name: 'The known world' })).toBeInTheDocument();
    expect(router.state.location.search).toEqual({});
    await waitFor(() => {
      expect(screen.getByRole('link', { name: /^The Foundry Vale/ })).toHaveFocus();
    });
  });

  it('selects a zone by clicking its island', async () => {
    const user = userEvent.setup();
    const { router } = await renderWorld(two);

    const map = await screen.findByRole('img', { name: 'The known world' });
    const island = map.querySelector('[data-zone="retrieval"]');
    if (island === null) throw new Error('no island link for retrieval');
    await user.click(island);

    expect(await screen.findByRole('region', { name: 'The Sunken Archive' })).toBeInTheDocument();
    expect(router.state.location.search).toEqual({ zone: 'retrieval' });
  });

  it('restores the selection from the URL, and steps back and forward through history', async () => {
    const { router } = await renderWorld(four, '/?zone=protocols');

    expect(await screen.findByRole('region', { name: 'Protocols' })).toBeInTheDocument();

    await router.navigate({ to: '/', search: { zone: 'orchestration' } });
    expect(await screen.findByRole('region', { name: 'Orchestration' })).toBeInTheDocument();

    router.history.back();
    expect(await screen.findByRole('region', { name: 'Protocols' })).toBeInTheDocument();
    router.history.forward();
    expect(await screen.findByRole('region', { name: 'Orchestration' })).toBeInTheDocument();
  });

  it('shows the world for a zone that does not exist', async () => {
    await renderWorld(four, '/?zone=nowhere');

    expect(await screen.findByRole('img', { name: 'The known world' })).toBeInTheDocument();
  });

  it('falls back to the branch title when a zone has no flavour', async () => {
    await renderWorld(four);

    const list = within(await screen.findByRole('navigation', { name: 'zones' }));
    expect(list.getByRole('link', { name: /Orchestration/ })).toBeInTheDocument();
  });

  it('leaves professional mode on the syllabus whatever the URL says', async () => {
    await renderInRouter(
      withMode('professional', <BranchOverview branches={four} />),
      flavour,
      '/?zone=protocols',
    );

    expect(await screen.findByRole('region', { name: 'Orchestration' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Foundations' })).toBeInTheDocument();
    expect(screen.queryByRole('img', { name: 'The known world' })).not.toBeInTheDocument();
  });
});
