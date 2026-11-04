import { describe, expect, it } from 'vitest';

import { LEXICONS, toBadgeRule } from './lexicon';

describe('lexicon', () => {
  const [professional, rpg] = [LEXICONS.professional, LEXICONS.rpg];

  it('defines the same keys in both modes, with no empty vocabulary', () => {
    expect(Object.keys(rpg).sort()).toEqual(Object.keys(professional).sort());
    for (const lexicon of [professional, rpg]) {
      for (const [key, value] of Object.entries(lexicon)) {
        if (typeof value === 'string') expect(value, key).not.toBe('');
      }
      expect(Object.keys(lexicon.status).sort()).toEqual(['available', 'locked', 'passed']);
      expect(Object.keys(lexicon.tier).sort()).toEqual([
        'advanced',
        'beginner',
        'capstone',
        'intermediate',
      ]);
    }
  });

  it('uses the DESIGN.md vocabulary', () => {
    expect(professional.attemptSubmit).toBe('Run checks');
    expect(rpg.attemptSubmit).toBe('Attempt the quest');
    expect([professional.branch, rpg.branch]).toEqual(['track', 'zone']);
    expect([professional.status.locked, rpg.status.locked]).toEqual(['Locked', 'Shrouded']);
    expect([professional.status.passed, rpg.status.passed]).toEqual(['Completed', 'Conquered']);
  });

  it.each([
    [1, '1 exercise', '1 quest'],
    [3, '3 exercises', '3 quests'],
    [0, '0 exercises', '0 quests'],
  ])('pluralises a count of %i', (n, pro, game) => {
    expect(professional.exerciseCount(n)).toBe(pro);
    expect(rpg.exerciseCount(n)).toBe(game);
  });

  it('names the profile, paths and the talent tree for each mode', () => {
    expect([professional.profile, rpg.profile]).toEqual(['Profile', 'Character sheet']);
    expect([professional.specialisation, rpg.specialisation]).toEqual(['specialisation', 'class']);
    expect([professional.specialisationPlural, rpg.specialisationPlural]).toEqual([
      'specialisations',
      'classes',
    ]);
    expect(professional.pathNames).toEqual({
      generalist: 'Generalist',
      retrieval: 'Retrieval specialist',
      protocols: 'Integration specialist',
      orchestration: 'Systems specialist',
      'knowledge-graphs': 'Knowledge engineer',
      memory: 'Memory engineer',
      'context-engineering': 'Context engineer',
      evals: 'Evaluation engineer',
    });
    expect(Object.keys(rpg.pathNames).sort()).toEqual(Object.keys(professional.pathNames).sort());
    expect([professional.talentTree, rpg.talentTree]).toEqual(['Competency matrix', 'Talent tree']);
    expect([professional.referenceSolution, rpg.referenceSolution]).toEqual([
      'Reference solution',
      "Master's copy",
    ]);
  });

  it('names certificates for each mode, always with the real track', () => {
    expect([professional.certificatesHeading, rpg.certificatesHeading]).toEqual([
      'Certificates',
      'Seals of completion',
    ]);
    for (const lexicon of [professional, rpg]) {
      expect(lexicon.certificateEarned('Retrieval')).toContain(
        'Certificate earned: Retrieval track',
      );
    }
    const shared = (title: string) => ({ title, pathName: null });
    expect(professional.referenceLocked([shared('Guarded builder')])).toBe(
      'A competency unlocks reference solutions for this track. Acquire Guarded builder to unlock it.',
    );
    expect(rpg.referenceLocked([shared('A'), shared('B')])).toBe(
      "A talent unlocks master's copies for this zone. Learn A or B to unlock it.",
    );
    expect(
      rpg.referenceLocked([
        { title: 'A', pathName: 'Artificer' },
        { title: 'B', pathName: 'Artificer' },
      ]),
    ).toBe(
      "A talent unlocks master's copies for this zone. Learn A or B as an Artificer to unlock it.",
    );
    expect(
      professional.referenceLocked([shared('A'), { title: 'B', pathName: 'Memory engineer' }]),
    ).toBe(
      'A competency unlocks reference solutions for this track. Acquire A, or B as a Memory engineer to unlock it.',
    );
    expect(professional.referenceLocked([])).not.toContain('Acquire');
  });

  it('defines every talent state and an action for it', () => {
    for (const lexicon of [professional, rpg]) {
      expect(Object.keys(lexicon.talentState).sort()).toEqual(['allocated', 'available', 'locked']);
      expect(new Set(Object.values(lexicon.talentState)).size).toBe(3);
      expect(lexicon.talentAllocate).not.toBe(lexicon.talentDeallocate);
    }
    expect([professional.talentAllocate, rpg.talentAllocate]).toEqual(['Acquire', 'Learn']);
    expect([professional.respec, rpg.respec]).toEqual(['Reset competencies', 'Respec talents']);
  });

  it('pluralises points, badges and days', () => {
    expect(professional.talentPoints(1, 1)).toBe('1 of 1 competency point available');
    expect(professional.talentPoints(2, 3)).toBe('2 of 3 competency points available');
    expect(rpg.talentPoints(0, 2)).toBe('0 of 2 talent points to spend');
    expect(professional.talentPointsGained(1)).toBe('+1 competency point');
    expect(rpg.talentPointsGained(2)).toBe('+2 talent points');
    expect(professional.badgesAwarded(1)).toBe('1 achievement earned');
    expect(rpg.badgesAwarded(2)).toBe('2 badges won');
    expect(professional.badgesSummary(2, 13)).toBe('2 of 13 earned');
    expect(professional.streakLongest(1)).toBe('Longest: 1 day');
    expect(rpg.streakLongest(7)).toBe('Longest streak: 7 days');
  });

  it('phrases the streak naturally in each mode', () => {
    expect(professional.streakCurrent(3)).toBe('3-day streak');
    expect(rpg.streakCurrent(3)).toBe('Learning streak: 3 days');
    expect(rpg.streakCurrent(1)).toBe('Learning streak: 1 day');
    expect(professional.streakCurrent(0)).toBe('No streak yet');
    expect(rpg.streakCurrent(0)).toBe('No streak yet');
  });

  it('interpolates path changes and requirements', () => {
    expect(
      professional.pathConfirm('Retrieval specialist', ['Index builder', 'Precision search']),
    ).toBe(
      'Switching to Retrieval specialist refunds Index builder, Precision search. The points come back to you.',
    );
    expect(rpg.pathDropped(['Index builder'])).toBe('Unlearned: Index builder.');
    expect(professional.talentRequiresExercises(['A', 'B'])).toBe('Complete: A, B');
    expect(rpg.talentRequiresParents(['A'])).toBe('First learn: A');
    expect(professional.badgeEarned('3 Oct 2026')).toBe('Earned 3 Oct 2026');
    expect(rpg.badgeEarned('3 Oct 2026')).toBe('Won 3 Oct 2026');
  });

  it('pluralises branches and interpolates names and numbers', () => {
    expect(professional.branchCount(1)).toBe('1 track');
    expect(rpg.branchCount(2)).toBe('2 zones');
    expect(professional.passedStrip(60, 2)).toBe('Passed · +60 XP · Level 2');
    expect(rpg.progressLabel(3, 9)).toBe('3 of 9 conquered');
    expect(professional.newlyOpened(1)).toBe('1 exercise now available');
    expect(rpg.newlyOpened(2)).toBe('2 new quests revealed');
  });

  it('names the branches a locked one waits on, without an article and with the verb agreeing', () => {
    expect(rpg.lockedBranch(['The Deepstacks'])).toBe(
      'This zone lies in fog until The Deepstacks is conquered.',
    );
    expect(rpg.lockedBranch(['The Deepstacks', 'The Spire'])).toBe(
      'This zone lies in fog until The Deepstacks and The Spire are conquered.',
    );
    expect(rpg.lockedBranch(['The Deepstacks', 'The Spire', 'The Loomhall'])).toBe(
      'This zone lies in fog until The Deepstacks, The Spire and The Loomhall are conquered.',
    );
    expect(professional.lockedBranch(['Retrieval'])).toBe(
      'This track opens when Retrieval is complete.',
    );
    expect(professional.lockedBranch(['Retrieval', 'Memory'])).toBe(
      'This track opens when Retrieval and Memory are complete.',
    );
    expect(professional.lockedBranch(['Retrieval', 'Memory', 'Evals'])).toBe(
      'This track opens when Retrieval, Memory and Evals are complete.',
    );
    // Callers that still join the names with ", " get the same wording.
    expect(rpg.lockedBranch('The Deepstacks, The Spire')).toBe(
      rpg.lockedBranch(['The Deepstacks', 'The Spire']),
    );
  });

  it('words badge criteria and locked classes in each mode', () => {
    const memory = { kind: 'branch_complete', branchName: 'The Hall of Hours' } as const;
    expect(professional.badgeRequirement({ kind: 'exercises_passed', n: 5 }, false)).toBe(
      'Pass five exercises.',
    );
    expect(rpg.badgeRequirement({ kind: 'exercises_passed', n: 5 }, true)).toBe(
      'Conquered five quests.',
    );
    expect(rpg.badgeRequirement(memory, false)).toBe('Conquer every quest in The Hall of Hours.');
    expect(rpg.badgeRequirement({ kind: 'capstones_passed', n: 1 }, true)).toBe(
      'Defeated one boss.',
    );
    expect(professional.badgeRequirement({ kind: 'capstones_passed', n: 9 }, false)).toBe(
      'Pass nine capstone projects.',
    );
    expect(professional.badgeRequirement({ kind: 'level_reached', n: 10 }, true)).toBe(
      'Reached level 10.',
    );
    for (const kind of ['first_try', 'no_hint_passes', 'streak_days'] as const) {
      expect(rpg.badgeRequirement({ kind, n: 3 }, false)).not.toMatch(/exercise|hint/);
    }
    expect(professional.pathLocked(['Foundations'])).toBe(
      'Complete Foundations to choose this specialisation.',
    );
    expect(rpg.pathLocked(['The Foundry Vale', 'The Deepstacks'])).toBe(
      'Conquer The Foundry Vale and The Deepstacks to take this class.',
    );
  });

  it('turns an API badge requirement into a rule, or null for an unknown kind', () => {
    const name = (id: string, title: string) => `${title} (${id})`;
    expect(toBadgeRule({ kind: 'first_try', n: 3, branch: null }, name)).toEqual({
      kind: 'first_try',
      n: 3,
    });
    expect(
      toBadgeRule({ kind: 'branch_complete', branch: { id: 'memory', title: 'Memory' } }, name),
    ).toEqual({ kind: 'branch_complete', branchName: 'Memory (memory)' });
    expect(toBadgeRule({ kind: 'moon_phase', n: 1 }, name)).toBeNull();
  });

  it('words the capstone in each mode, with a state that is never colour alone', () => {
    expect([professional.tier.capstone, rpg.tier.capstone]).toEqual(['Capstone', 'Boss']);
    expect([professional.capstoneLabel, rpg.capstoneLabel]).toEqual([
      'Capstone project',
      'Boss challenge',
    ]);
    expect(Object.values(professional.capstoneState)).toEqual(['Locked', 'Available', 'Completed']);
    expect(Object.values(rpg.capstoneState)).toEqual(['Sealed', 'Awaiting', 'Defeated']);
    expect(professional.capstoneStrip(400, 5)).toBe('Capstone complete · +400 XP · Level 5');
    expect([professional.capstoneCompletionTitle, rpg.capstoneCompletionTitle]).toEqual([
      'Capstone complete',
      'Boss defeated',
    ]);
  });

  it('names a guided project in each mode and words carried files', () => {
    expect([professional.projectLabel, rpg.projectLabel]).toEqual(['Guided project', 'Expedition']);
    expect(professional.carriedNote('Hybrid retrieval')).toBe(
      'Continuing from your work on Hybrid retrieval.',
    );
    expect(rpg.carriedNote('The Drowned Index')).toBe(
      'You carry your work from The Drowned Index into this quest.',
    );
    expect([professional.carriedReset, rpg.carriedReset]).toEqual([
      'Start from the provided code instead',
      'Start from the provided code instead',
    ]);
    for (const lexicon of [professional, rpg]) {
      // The confirm step says the earlier pass is safe, so a reset is never feared as a loss.
      expect(lexicon.carriedResetConfirm).toMatch(/kept|stands/);
      expect(lexicon.carriedResetAction).not.toBe(lexicon.carriedKeep);
    }
  });

  it('adds the capstone to a certificate announcement only when the track had one', () => {
    expect(professional.certificateEarned('Retrieval', true)).toBe(
      'Certificate earned: Retrieval track, including its capstone project',
    );
    expect(rpg.certificateEarned('Retrieval', true)).toBe(
      'The seal is set. Certificate earned: Retrieval track, including its capstone project',
    );
    for (const lexicon of [professional, rpg]) {
      expect(lexicon.certificateEarned('Retrieval', false)).not.toContain('capstone');
      expect(lexicon.certificateEarned('Retrieval')).not.toContain('capstone');
    }
  });
});
