import { vi } from 'vitest';

import type {
  BadgeStatus,
  BranchSummary,
  Certificate,
  ThemeFlavour,
  LearnerMap,
  PathProfile,
  Progression,
  TalentNode,
  TalentTree,
} from '../api/types';
import type { TalentTreeProps } from '../theme/slots/types';

export function talent(overrides: Partial<TalentNode> & { id: string }): TalentNode {
  return {
    title: overrides.id,
    summary: `${overrides.id} summary.`,
    subtree: 'general',
    parents: [],
    min_level: 2,
    required_exercises: [],
    effects: [],
    state: 'locked',
    reasons: [],
    ...overrides,
  };
}

/** A small tree: two general talents (one taken, one open) and a locked class talent. */
export const NODES: TalentNode[] = [
  talent({
    id: 'steady-hands',
    title: 'Steady hands',
    state: 'allocated',
    required_exercises: ['starter.first-completion'],
  }),
  talent({
    id: 'prompt-craft',
    title: 'Prompt craft',
    state: 'available',
    parents: ['steady-hands'],
    required_exercises: ['starter.system-prompts'],
  }),
  talent({
    id: 'index-builder',
    title: 'Index builder',
    subtree: 'retrieval',
    min_level: 3,
    state: 'locked',
    required_exercises: ['retrieval.vector-store'],
    reasons: [{ code: 'level', detail: 'Reach level 3 first.' }],
  }),
];

export function treeOf(overrides: Partial<TalentTree> = {}): TalentTree {
  return {
    path: 'retrieval',
    total_points: 3,
    spent_points: 1,
    available_points: 2,
    nodes: NODES,
    ...overrides,
  };
}

export function treeProps(overrides: Partial<TalentTreeProps> = {}): TalentTreeProps {
  return {
    tree: treeOf(),
    exerciseTitle: (id) => `Title of ${id}`,
    subtreeName: (subtree) => (subtree === 'general' ? 'General' : subtree),
    pendingNode: null,
    respeccing: false,
    problem: null,
    onAllocate: vi.fn(),
    onDeallocate: vi.fn(),
    onRespec: vi.fn(),
    ...overrides,
  };
}

export const PATH_PROFILE: PathProfile = {
  path: 'retrieval',
  time_zone: 'Europe/London',
  titles: ['Prompt engineer'],
  dropped_talents: [],
  paths: [
    {
      id: 'generalist',
      title: 'Generalist',
      summary: 'Walks every road.',
      home_branch: null,
      selectable: true,
      reason: null,
      requires: [],
    },
    {
      id: 'retrieval',
      title: 'Retrieval specialist',
      summary: 'Finds the evidence.',
      home_branch: 'retrieval',
      selectable: true,
      reason: null,
      requires: [],
    },
    {
      id: 'protocols',
      title: 'Integration specialist',
      summary: 'Speaks the wire protocols.',
      home_branch: 'protocols',
      selectable: false,
      reason: 'Complete Foundations first.',
      requires: [{ id: 'starter', title: 'Foundations' }],
    },
  ],
};

export const BADGES: BadgeStatus[] = [
  {
    id: 'getting-going',
    title: 'Getting going',
    description: 'Passed five exercises.',
    criterion: 'Pass 5 exercises.',
    requirement: { kind: 'exercises_passed', n: 5, branch: null },
    earned: false,
    awarded_at: null,
    attempt_id: null,
  },
  {
    id: 'first-steps',
    title: 'First steps',
    description: 'Passed your first exercise.',
    criterion: 'Pass 1 exercise.',
    requirement: { kind: 'exercises_passed', n: 1, branch: null },
    earned: true,
    awarded_at: '2026-10-03T09:00:00Z',
    attempt_id: 'a1',
  },
];

export const MAP: LearnerMap = {
  level: { level: 3, total_xp: 250, level_floor: 200, next_level_at: 400, fraction: 0.25 },
  streak: { current: 3, longest: 7 },
  branches: [
    {
      id: 'starter',
      title: 'Foundations',
      summary: '',
      unlocked: true,
      requires: [],
      kind: 'standard',
      pro: false,
      passed_count: 1,
      exercises: [
        {
          id: 'starter.first-completion',
          title: 'Your first completion',
          tier: 'beginner',
          xp: 50,
          prerequisites: [],
          skills: [],
          status: 'passed',
          pro: false,
          entitled: true,
        },
        {
          id: 'starter.system-prompts',
          title: 'System prompts',
          tier: 'beginner',
          xp: 50,
          prerequisites: [],
          skills: [],
          status: 'available',
          pro: false,
          entitled: true,
        },
      ],
    },
  ],
};

/** A branch whose last exercise is a capstone; the capstone's status is the one to vary. */
export function capstoneBranch(
  status: 'locked' | 'available' | 'passed' = 'locked',
): BranchSummary {
  const exercise = (
    id: string,
    title: string,
    tier: string,
    xp: number,
    state: 'locked' | 'available' | 'passed',
  ) => ({
    id: `retrieval.${id}`,
    title,
    tier,
    xp,
    prerequisites: [],
    skills: [],
    status: state,
    pro: false,
    entitled: true,
  });
  return {
    id: 'retrieval',
    title: 'Retrieval',
    summary: 'Search and ranking.',
    unlocked: true,
    requires: ['starter'],
    kind: 'standard',
    pro: false,
    passed_count: status === 'locked' ? 1 : 2,
    exercises: [
      exercise('chunking', 'Fixed-size chunking', 'beginner', 75, 'passed'),
      exercise(
        'hybrid',
        'Hybrid search',
        'advanced',
        125,
        status === 'locked' ? 'available' : 'passed',
      ),
      exercise('search-service', 'Build a search service', 'capstone', 350, status),
    ],
  };
}

export const BOSS_FLAVOUR: ThemeFlavour = {
  branches: {
    retrieval: { name: 'The Sunken Archive', epithet: 'Lost in the deep', lore: 'Drowned stacks.' },
  },
  quests: {},
  paths: {},
  bosses: {
    'retrieval.search-service': {
      name: 'The Index Warden',
      epithet: 'Keeper of every shelf',
      lore: 'It has read everything and forgiven nothing.',
      defeat: 'The Warden lowers its lantern; the shelves fall quiet.',
    },
  },
};

export function progression(overrides: Partial<Progression> = {}): Progression {
  return {
    xp_awarded: 60,
    awards: [],
    level_before: 1,
    level_after: 2,
    unlocked: [],
    badges_awarded: [],
    talent_points_gained: 0,
    streak: null,
    certificates_issued: [],
    ...overrides,
  };
}

export const CERTIFICATE: Certificate = {
  id: 'cert_abc-123',
  branch_id: 'starter',
  branch_title: 'Foundations',
  recipient_name: 'Ada Lovelace',
  exercise_count: 10,
  includes_capstone: false,
  issued_at: '2026-10-25T09:30:00Z',
  is_public: false,
  published_at: null,
  public_url: 'https://forgeway.example/c/cert_abc-123',
  image_url: 'https://forgeway.example/c/cert_abc-123.png',
  linkedin: {
    name: 'Forgeway Foundations track',
    organisation: 'Forgeway',
    issue_year: 2026,
    issue_month: 10,
    credential_id: 'cert_abc-123',
    credential_url: 'https://forgeway.example/c/cert_abc-123',
  },
};

export const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

export const problem = (status: number, detail: string, code = 'conflict') =>
  json({ title: 'Problem', status, detail, code }, status);

type Handler = (request: Request) => Response | Promise<Response>;

/**
 * Stand in for the API: routes are keyed "METHOD /path" (query ignored). Returns the requests
 * seen, so a test can assert on bodies and methods. Unrouted requests fail the test loudly.
 */
export function stubApi(routes: Record<string, Handler>) {
  const seen: Request[] = [];
  const fetchMock = vi.fn(async (request: Request) => {
    seen.push(request.clone());
    const key = `${request.method} ${new URL(request.url).pathname}`;
    const handler = routes[key];
    if (handler === undefined) throw new Error(`Unrouted request: ${key}`);
    return handler(request);
  });
  vi.stubGlobal('fetch', fetchMock);
  return seen;
}
