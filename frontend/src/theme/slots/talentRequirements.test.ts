import { describe, expect, it } from 'vitest';

import { talent } from '../../test/fixtures';
import { talentRequirements } from './talentRequirements';

const root = talent({ id: 'root', title: 'Root', state: 'allocated' });
const other = talent({ id: 'other', title: 'Other', state: 'locked' });
const context = {
  titles: new Map([root, other].map((n) => [n.id, n.title])),
  states: new Map([root, other].map((n) => [n.id, n.state])),
  exerciseTitle: (id: string) => `Title of ${id}`,
};

const summary = (node: ReturnType<typeof talent>) =>
  talentRequirements(node, context).map((r) => `${r.met ? 'met' : 'unmet'}:${r.kind}:${r.subject}`);

describe('talentRequirements', () => {
  it('marks only the unmet items, from the backend reasons', () => {
    const node = talent({
      id: 'x',
      min_level: 4,
      parents: ['root', 'other'],
      required_exercises: ['a.one', 'a.two'],
      reasons: [
        { code: 'parents', detail: 'Needs Other first.' },
        { code: 'exercises', detail: 'Pass Title of a.two first.' },
      ],
    });

    expect(summary(node)).toEqual([
      'met:level:',
      'met:parent:Root',
      'unmet:parent:Other',
      'met:exercise:Title of a.one',
      'unmet:exercise:Title of a.two',
    ]);
  });

  it('marks the level unmet when the backend says so', () => {
    const node = talent({ id: 'x', reasons: [{ code: 'level', detail: 'Needs level 2.' }] });
    expect(talentRequirements(node, context)[0]).toMatchObject({ kind: 'level', met: false });
  });

  it('keeps a reason with no requirement as its own unmet line', () => {
    const node = talent({
      id: 'x',
      reasons: [
        { code: 'no_points', detail: 'No talent points to spend.' },
        { code: 'other_path', detail: 'Needs the Retrieval path.' },
      ],
    });

    expect(summary(node)).toEqual([
      'met:level:',
      'unmet:other:No talent points to spend.',
      'unmet:other:Needs the Retrieval path.',
    ]);
  });

  it('never reads a requirement as met when the reason does not name it', () => {
    const node = talent({
      id: 'x',
      required_exercises: ['a.one'],
      reasons: [{ code: 'exercises', detail: 'Pass something else first.' }],
    });
    expect(summary(node)).toContain('unmet:exercise:Title of a.one');
  });

  it('treats a taken talent as having met everything', () => {
    const node = talent({
      id: 'x',
      state: 'allocated',
      parents: ['other'],
      required_exercises: ['a.one'],
      reasons: [{ code: 'already_allocated', detail: 'Already taken.' }],
    });
    expect(summary(node).every((line) => line.startsWith('met:'))).toBe(true);
    expect(summary(node)).toHaveLength(3);
  });
});
