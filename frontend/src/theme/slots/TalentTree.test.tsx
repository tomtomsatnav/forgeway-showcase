import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { Mode } from '../../api/types';
import { NODES, talent, treeOf, treeProps } from '../../test/fixtures';
import { withMode } from '../../test/render';
import { TalentTree } from '.';
import { NODE_RADIUS, planConstellation } from './talentGeometry';

const renderTree = (mode: Mode, overrides = {}) =>
  render(withMode(mode, <TalentTree {...treeProps(overrides)} />));

const MODES: Mode[] = ['professional', 'rpg'];

describe.each(MODES)('talent tree slot (%s)', (mode) => {
  const words =
    mode === 'rpg'
      ? { taken: 'Learned', open: 'Ready to learn', locked: 'Sealed', allocate: 'Learn' }
      : { taken: 'Acquired', open: 'Available', locked: 'Locked', allocate: 'Acquire' };

  it('shows every talent as a row with its state in words and its requirements', () => {
    renderTree(mode);

    const table = screen.getByRole('table');
    const rows = within(table).getAllByRole('row');
    // Header, two subtree headings and three talents.
    expect(rows).toHaveLength(6);

    const steady = within(table).getByRole('row', { name: /^Steady hands/ });
    expect(within(steady).getByText(words.taken)).toBeVisible();
    expect(steady).toHaveTextContent(
      `${mode === 'rpg' ? 'Conquer' : 'Complete'}: Title of starter.first-completion`,
    );

    const craft = within(table).getByRole('row', { name: /^Prompt craft/ });
    expect(within(craft).getByText(words.open)).toBeVisible();
    expect(craft).toHaveTextContent('Level 2');

    const index = within(table).getByRole('row', { name: /^Index builder/ });
    expect(within(index).getByText(words.locked)).toBeVisible();
    // Level is the one thing the backend says is unmet; the exercise is not named, so it is met.
    expect(within(index).getByText('Not met:').parentElement).toHaveTextContent('Level 3');
    expect(index).not.toHaveTextContent('Blocked');
    // A locked talent has no action at all, not a dimmed one.
    expect(within(index).queryByRole('button')).not.toBeInTheDocument();
  });

  it('lists each requirement once with met or not met in words', () => {
    const nodes = [
      talent({ id: 'root', title: 'Root', state: 'allocated' }),
      talent({ id: 'sibling', title: 'Sibling' }),
      talent({
        id: 'deep',
        title: 'Deep',
        min_level: 4,
        parents: ['root', 'sibling'],
        required_exercises: ['x.one'],
        reasons: [
          { code: 'level', detail: 'Needs level 4.' },
          { code: 'parents', detail: 'Needs Sibling first.' },
          { code: 'exercises', detail: 'Pass Title of x.one first.' },
          { code: 'no_points', detail: 'No talent points to spend.' },
        ],
      }),
    ];
    renderTree(mode, { tree: treeOf({ nodes }) });

    const deep = screen.getByRole('row', { name: /^Deep/ });
    const lines = within(deep)
      .getAllByRole('listitem')
      .map((item) => item.textContent);
    expect(lines).toEqual([
      'Not met: Level 4',
      `Met: ${mode === 'rpg' ? 'First learn' : 'First'}: Root`,
      `Not met: ${mode === 'rpg' ? 'First learn' : 'First'}: Sibling`,
      `Not met: ${mode === 'rpg' ? 'Conquer' : 'Complete'}: Title of x.one`,
      'Not met: No talent points to spend.',
    ]);
    expect(deep).not.toHaveTextContent('Blocked');
    expect(within(deep).queryByRole('button')).not.toBeInTheDocument();
  });

  it('gives an available talent a primary action and a taken one a secondary action', () => {
    renderTree(mode);

    const take = screen.getByRole('button', { name: `${words.allocate} Prompt craft` });
    expect(take).toBeEnabled();
    expect(take.className).toContain('bg-accent');
    const release = screen.getByRole('button', { name: /^(Release|Unlearn) Steady hands/ });
    expect(release.className).not.toContain('bg-accent');
  });

  it('groups talents under their subtree heading', () => {
    renderTree(mode);

    expect(screen.getByRole('rowheader', { name: 'General' })).toBeInTheDocument();
    expect(screen.getByRole('rowheader', { name: 'retrieval' })).toBeInTheDocument();
  });

  it('counts the points in the mode vocabulary', () => {
    renderTree(mode);

    expect(screen.getByRole('status')).toHaveTextContent(
      mode === 'rpg' ? '2 of 3 talent points to spend' : '2 of 3 competency points available',
    );
  });

  it('allocates and deallocates with the keyboard alone', async () => {
    const onAllocate = vi.fn();
    const onDeallocate = vi.fn();
    const user = userEvent.setup();
    renderTree(mode, { onAllocate, onDeallocate });

    screen.getByRole('button', { name: `${words.allocate} Prompt craft` }).focus();
    await user.keyboard('{Enter}');
    expect(onAllocate).toHaveBeenCalledWith('prompt-craft');

    const release = screen.getByRole('button', {
      name: new RegExp(`^${mode === 'rpg' ? 'Unlearn' : 'Release'} Steady hands`),
    });
    release.focus();
    await user.keyboard(' ');
    expect(onDeallocate).toHaveBeenCalledWith('steady-hands');
  });

  it('disables actions while one is in flight', () => {
    renderTree(mode, { pendingNode: 'prompt-craft' });

    const table = screen.getByRole('table');
    for (const button of within(table).getAllByRole('button')) expect(button).toBeDisabled();
  });

  it('shows a 409 reason inline', () => {
    renderTree(mode, { problem: 'Prompt craft: No talent points are left to spend.' });

    expect(screen.getByRole('alert')).toHaveTextContent('No talent points are left to spend.');
  });

  it('puts respec behind a confirm step that states the cost', async () => {
    const onRespec = vi.fn();
    const user = userEvent.setup();
    renderTree(mode, { onRespec });

    await user.click(screen.getByRole('button', { name: /^(Respec talents|Reset competencies)$/ }));
    expect(onRespec).not.toHaveBeenCalled();
    const confirm = screen.getByRole('group', { name: /^(Respec talents|Reset competencies)$/ });
    expect(confirm).toHaveTextContent(/free|costs nothing/);

    await user.click(within(confirm).getByRole('button', { name: /^Keep my/ }));
    expect(screen.queryByRole('group')).not.toBeInTheDocument();
    expect(onRespec).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: /^(Respec talents|Reset competencies)$/ }));
    await user.click(screen.getByRole('button', { name: /^(Respec all|Reset all)$/ }));
    expect(onRespec).toHaveBeenCalledTimes(1);
  });

  it('has nothing to respec before any point is spent', () => {
    renderTree(mode, { tree: treeOf({ spent_points: 0 }) });

    expect(
      screen.getByRole('button', { name: /^(Respec talents|Reset competencies)$/ }),
    ).toBeDisabled();
  });
});

describe('on a phone', () => {
  const stubNarrow = () => {
    vi.stubGlobal('matchMedia', () => ({
      matches: true,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    }));
  };
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it.each(MODES)('stacks each talent as a complete card instead of a table (%s)', (mode) => {
    stubNarrow();
    renderTree(mode);

    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    const cards = within(screen.getByRole('region', { name: /table|list/ })).getAllByRole(
      'listitem',
      { hidden: false },
    );
    const card = (title: string) => {
      const found = cards.find((item) => item.querySelector('p')?.textContent === title);
      if (found === undefined) throw new Error(`no card for ${title}`);
      return found;
    };

    const craft = card('Prompt craft');
    expect(craft).toHaveTextContent('prompt-craft summary.');
    expect(craft).toHaveTextContent('Level 2');
    expect(craft).toHaveTextContent(mode === 'rpg' ? 'Ready to learn' : 'Available');
    expect(within(craft).getByRole('button')).toBeEnabled();

    const index = card('Index builder');
    expect(index).toHaveTextContent(mode === 'rpg' ? 'Sealed' : 'Locked');
    expect(index).toHaveTextContent('Level 3');
    expect(within(index).queryByRole('button')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'General' })).toBeInTheDocument();
  });

  it('still allocates from a card', async () => {
    stubNarrow();
    const onAllocate = vi.fn();
    renderTree('professional', { onAllocate });

    await userEvent.setup().click(screen.getByRole('button', { name: 'Acquire Prompt craft' }));
    expect(onAllocate).toHaveBeenCalledWith('prompt-craft');
  });
});

describe('the two renderers', () => {
  it('draw the constellation only in RPG mode, with the table as its equivalent', () => {
    const { unmount } = renderTree('professional');
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    expect(screen.getByRole('table')).toBeInTheDocument();
    unmount();

    renderTree('rpg');
    const sky = screen.getByRole('img', { name: 'Talent tree' });
    expect(sky).toHaveAccessibleDescription(/table beneath lists the same talents/);
    expect(sky.querySelectorAll('[data-node]')).toHaveLength(NODES.length);
    expect(screen.getByRole('table')).toBeInTheDocument();
  });

  it('give the constellation a state glyph and a state word for every talent', () => {
    renderTree('rpg');

    const sky = screen.getByRole('img', { name: 'Talent tree' });
    const states = new Map(
      [...sky.querySelectorAll('[data-node]')].map((star) => [
        star.getAttribute('data-node') ?? '',
        star.textContent,
      ]),
    );
    expect(states.get('steady-hands')).toContain('Learned');
    expect(states.get('prompt-craft')).toContain('Ready to learn');
    expect(states.get('index-builder')).toContain('Sealed');
    // A tick, a ringed dot and a padlock: three different shapes, not three colours.
    const glyphs = [...sky.querySelectorAll('[data-node]')].map(
      (star) => star.firstElementChild?.outerHTML,
    );
    expect(new Set(glyphs).size).toBe(3);
  });

  it('send focus to the talent button when a star is clicked', async () => {
    renderTree('rpg');

    const sky = screen.getByRole('img', { name: 'Talent tree' });
    const star = sky.querySelector('[data-node="prompt-craft"]');
    if (star === null) throw new Error('no star');
    await userEvent.setup().click(star);

    expect(screen.getByRole('button', { name: 'Learn Prompt craft' })).toHaveFocus();
  });

  it('draw a taken link only between two taken talents', () => {
    const nodes = [
      talent({ id: 'a', state: 'allocated' }),
      talent({ id: 'b', parents: ['a'], state: 'allocated' }),
      talent({ id: 'c', parents: ['b'], state: 'available' }),
    ];
    renderTree('rpg', { tree: treeOf({ nodes }) });

    const sky = screen.getByRole('img', { name: 'Talent tree' });
    expect(sky.querySelectorAll('[data-link="taken"]')).toHaveLength(1);
    expect(sky.querySelectorAll('[data-link="open"]')).toHaveLength(1);
  });
});

describe('constellation layout', () => {
  const chain = [
    talent({ id: 'root' }),
    talent({ id: 'left', parents: ['root'] }),
    talent({ id: 'right', parents: ['root'] }),
    talent({ id: 'leaf', parents: ['left', 'right'] }),
    talent({ id: 'cross', subtree: 'retrieval', parents: ['root'] }),
  ];

  it('puts children below their parents and siblings side by side', () => {
    const plan = planConstellation(chain);
    const at = (id: string) => plan.nodes.find((entry) => entry.node.id === id);

    expect(at('left')?.y).toBeGreaterThan(at('root')?.y ?? Infinity);
    expect(at('left')?.y).toBe(at('right')?.y);
    expect(at('left')?.x).not.toBe(at('right')?.x);
    expect(at('leaf')?.y).toBeGreaterThan(at('left')?.y ?? Infinity);
    // A parent in another subtree draws a link but does not push the child down.
    expect(at('cross')?.y).toBeGreaterThan(at('leaf')?.y ?? Infinity);
    expect(plan.links).toHaveLength(5);
  });

  it('keeps every node inside the canvas and clear of its neighbours', () => {
    const plan = planConstellation(chain);

    for (const [i, a] of plan.nodes.entries()) {
      expect(a.x - NODE_RADIUS).toBeGreaterThanOrEqual(0);
      expect(a.x + NODE_RADIUS).toBeLessThanOrEqual(plan.width);
      expect(a.y + NODE_RADIUS).toBeLessThanOrEqual(plan.height);
      for (const b of plan.nodes.slice(i + 1))
        expect(Math.hypot(a.x - b.x, a.y - b.y)).toBeGreaterThan(2 * NODE_RADIUS);
    }
  });

  /**
   * The shape of the shipped content: a general trunk whose two branches each grow one more talent,
   * then a path that forks twice. (A talent reached by a link that skips a layer is not covered:
   * that needs routing around the layer in between.)
   */
  const content = [
    talent({ id: 'steady-hands' }),
    talent({ id: 'prompt-craft', parents: ['steady-hands'] }),
    talent({ id: 'context-keeper', parents: ['steady-hands'] }),
    talent({ id: 'resilient-caller', parents: ['context-keeper'] }),
    talent({ id: 'guarded-builder', parents: ['prompt-craft'] }),
    talent({ id: 'index-builder', subtree: 'retrieval' }),
    talent({ id: 'precision-search', subtree: 'retrieval', parents: ['index-builder'] }),
    talent({ id: 'grounded-generation', subtree: 'retrieval', parents: ['index-builder'] }),
    talent({ id: 'hybrid-ranking', subtree: 'retrieval', parents: ['precision-search'] }),
    talent({ id: 'retrieval-evaluator', subtree: 'retrieval', parents: ['precision-search'] }),
  ];

  interface Pt {
    x: number;
    y: number;
  }
  const side = (a: Pt, b: Pt, c: Pt) =>
    Math.sign((b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x));
  const crosses = (a: Pt, b: Pt, c: Pt, d: Pt) =>
    side(a, b, c) !== side(a, b, d) && side(c, d, a) !== side(c, d, b);

  it.each(['compact', 'wide'] as const)(
    'orders each layer so no two parent links cross (%s)',
    (size) => {
      const plan = planConstellation(content, size);
      const at = new Map(plan.nodes.map((entry) => [entry.node.id, entry]));
      const segments = plan.links.map((link) => {
        const from = at.get(link.from);
        const to = at.get(link.to);
        if (from === undefined || to === undefined) throw new Error('dangling link');
        return { link, from, to };
      });

      const crossing = [];
      for (const [i, a] of segments.entries())
        for (const b of segments.slice(i + 1)) {
          // Links that share a talent meet at it; that is a join, not a crossing.
          if ([b.link.from, b.link.to].some((id) => id === a.link.from || id === a.link.to))
            continue;
          if (crosses(a.from, a.to, b.from, b.to))
            crossing.push(`${a.link.from}>${a.link.to} x ${b.link.from}>${b.link.to}`);
        }
      expect(crossing).toEqual([]);
    },
  );

  it('is deterministic and keeps API order when parents give no preference', () => {
    const first = planConstellation(content);
    expect(planConstellation(content)).toEqual(first);
    const order = (id: string) => first.nodes.find((entry) => entry.node.id === id)?.x ?? 0;
    expect(order('precision-search')).toBeLessThan(order('grounded-generation'));
  });

  it('uses more of the width, with bigger nodes, in the wide drawing', () => {
    const compact = planConstellation(content, 'compact');
    const wide = planConstellation(content, 'wide');
    expect(wide.width).toBeGreaterThan(compact.width * 2);
    expect(wide.metrics.radius).toBeGreaterThan(compact.metrics.radius);
    // The compact drawing must still fit a 375px screen without scaling below legibility.
    expect(compact.width).toBeLessThanOrEqual(343 * 1.25);
  });

  it('runs the wide drawing across: children to the right, siblings stacked, wider than tall', () => {
    const plan = planConstellation(content, 'wide');
    const at = (id: string) => plan.nodes.find((entry) => entry.node.id === id);
    expect(at('prompt-craft')?.x).toBeGreaterThan(at('steady-hands')?.x ?? Infinity);
    expect(at('guarded-builder')?.x).toBeGreaterThan(at('prompt-craft')?.x ?? Infinity);
    expect(at('prompt-craft')?.x).toBe(at('context-keeper')?.x);
    expect(at('prompt-craft')?.y).not.toBe(at('context-keeper')?.y);
    // The class's band sits below the general one, not beside it.
    expect(at('index-builder')?.y).toBeGreaterThan(at('context-keeper')?.y ?? Infinity);
    expect(plan.width).toBeGreaterThan(plan.height);
    for (const [i, a] of plan.nodes.entries()) {
      expect(a.y - plan.metrics.radius).toBeGreaterThanOrEqual(0);
      expect(a.y + plan.metrics.radius + plan.metrics.labelDrop).toBeLessThanOrEqual(plan.height);
      for (const b of plan.nodes.slice(i + 1))
        // Neither node nor label overlaps another.
        expect(
          Math.abs(a.x - b.x) >= plan.metrics.column || Math.abs(a.y - b.y) >= plan.metrics.row,
        ).toBe(true);
    }
  });

  it('survives a cycle and an empty tree', () => {
    const loop = [talent({ id: 'x', parents: ['y'] }), talent({ id: 'y', parents: ['x'] })];
    expect(planConstellation(loop).nodes).toHaveLength(2);
    expect(planConstellation([]).nodes).toEqual([]);
  });
});
