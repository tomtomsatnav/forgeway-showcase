import type { ExerciseStatus, Mode, TalentState, Tier } from '../api/types';

/**
 * The vocabulary of a mode. Keys are domain concepts; values may be functions where a count or
 * a name is interpolated. `Record<Mode, Lexicon>` below makes TypeScript reject a mode that
 * leaves any key undefined.
 */
export interface Lexicon {
  appName: string;
  branch: string;
  branchPlural: string;
  exercise: string;
  capstone: string;
  level: string;
  hint: string;
  hintPlural: string;
  mapTitle: string;
  backToMap: string;
  backToWorld: string;
  worldMapTitle: string;
  worldMapDescription: (branches: number) => string;
  mapSummary: (branches: number, exercises: number) => string;
  branchCount: (n: number) => string;
  exerciseCount: (n: number) => string;
  levelLabel: (level: number) => string;
  xpLabel: (xp: number) => string;
  progressLabel: (passed: number, total: number) => string;
  attemptSubmit: string;
  attemptRunning: string;
  status: Record<ExerciseStatus, string>;
  tier: Record<Tier, string>;
  /** The capstone as a framed heading: "Capstone project" or "Boss challenge". */
  capstoneLabel: string;
  /** One line on what a capstone draws on. */
  capstoneNote: string;
  /** A capstone's state, worded for the mode (the RPG's lair is sealed, awaiting or defeated). */
  capstoneState: Record<ExerciseStatus, string>;
  capstoneStrip: (xp: number, level: number) => string;
  capstoneCompletionTitle: string;
  /** A `kind: project` branch, as a label above its title: "Guided project" or "Expedition". */
  projectLabel: string;
  /** Said when the workspace opened on the learner's files from an earlier exercise. */
  carriedNote: (title: string) => string;
  carriedReset: string;
  carriedResetConfirm: string;
  carriedResetAction: string;
  carriedKeep: string;
  resetCode: string;
  resetCodeConfirm: string;
  resetCodeAction: string;
  /** The editor's list of keyboard shortcuts. */
  editorShortcuts: string;
  hintRevealAction: string;
  hintConfirmCost: string;
  /**
   * Why a branch is locked, naming the branches it waits on. Names arrive as a list or, from
   * older callers, joined with ", "; either way they read "A", "A and B" or "A, B and C".
   */
  lockedBranch: (requires: string | readonly string[]) => string;
  lockedExercise: string;
  lockedByExercises: string;
  passedStrip: (xp: number, level: number) => string;
  completionTitle: string;
  levelUp: (level: number) => string;
  newlyOpened: (n: number) => string;
  signIn: string;
  register: string;
  /** After registering: the verification email is on its way. */
  checkInboxTitle: string;
  checkInboxBody: (email: string) => string;
  /** Continue into the app without verifying yet. */
  checkInboxContinue: string;
  /** Shown to signed-in learners whose email is not verified yet. */
  unverifiedBanner: string;
  resendVerification: string;
  verificationResent: (email: string) => string;
  verifyingEmail: string;
  emailVerifiedTitle: string;
  emailVerifiedBody: string;
  forgotPassword: string;
  forgotPasswordTitle: string;
  forgotPasswordSent: string;
  resetPasswordTitle: string;
  resetPasswordDone: string;
  /** One line under the sign-in and register headings. */
  authSummary: string;
  /** The secret's name, so a field never says "password" under a "passphrase" heading. */
  passwordLabel: string;
  newPasswordLabel: string;
  forgotPasswordAction: string;
  resetPasswordAction: string;
  /** A reset link that no longer works, then the words linking to a fresh request. */
  resetLinkInvalid: string;
  resetLinkRequest: string;

  /** The profile page: "Profile" or "Character sheet". */
  profile: string;
  profileSummary: (level: number) => string;
  path: string;
  pathPlural: string;
  /** What a path is called when it is a specialisation: "specialisation" or "class". */
  specialisation: string;
  specialisationPlural: string;
  /** Names for paths the API does not name itself; RPG flavour overrides these. */
  pathNames: Record<string, string>;
  pathCurrent: string;
  pathChoose: string;
  pathChangeWarning: string;
  pathConfirm: (name: string, dropped: readonly string[]) => string;
  pathDropped: (titles: readonly string[]) => string;
  /** Why a specialisation cannot be chosen yet, naming the branches still to complete. */
  pathLocked: (branchNames: readonly string[]) => string;
  titlesHeading: string;
  titlesNone: string;
  timeZone: string;
  timeZoneHint: string;
  timeZoneSave: string;

  talent: string;
  talentPlural: string;
  talentTree: string;
  talentTreeSummary: string;
  /** Heading for the subtree every path shares. */
  talentGeneral: string;
  talentPoint: string;
  talentPointPlural: string;
  talentPoints: (available: number, total: number) => string;
  talentPointsGained: (n: number) => string;
  talentState: Record<TalentState, string>;
  talentAllocate: string;
  talentDeallocate: string;
  talentRequirements: string;
  talentRequiresLevel: (level: number) => string;
  talentRequiresParents: (titles: readonly string[]) => string;
  talentRequiresExercises: (titles: readonly string[]) => string;
  respec: string;
  respecCost: string;
  respecConfirm: string;
  respecKeep: string;

  badge: string;
  badgePlural: string;
  badgeEarned: (date: string) => string;
  badgeNotEarned: string;
  badgeAwarded: (title: string) => string;
  badgesAwarded: (n: number) => string;
  badgesSummary: (earned: number, total: number) => string;
  /** How a badge is earned ("Pass five exercises.") or, once it is, what was done. */
  badgeRequirement: (rule: BadgeRule, earned: boolean) => string;

  streak: string;
  streakCurrent: (days: number) => string;
  streakLongest: (days: number) => string;

  referenceSolution: string;
  referenceNotes: string;
  /**
   * The reference-solution lock, worded with this mode's word for a talent. Each talent that
   * unlocks it comes with the name of the specialisation it belongs to, or null if shared.
   */
  referenceLocked: (talents: readonly LockingTalent[]) => string;

  certificatesHeading: string;
  certificatesNone: string;
  /** Announces an earned certificate; always names the real track. */
  certificateEarned: (branchTitle: string, includesCapstone?: boolean) => string;
  /** Said of a certificate whose track had a capstone when it was issued. */
  certificateIncludesCapstone: string;
  certificatesLink: string;

  /** The mark on Pro content. Always contains "Pro", so the plan is clear in both modes. */
  proMark: string;
  /** Says what the mark means, for its tooltip and for screen readers. */
  proMarkDescription: string;
  /** Pro content as a learner on the free plan sees it, in place of the run button. */
  proCtaTitle: string;
  proCtaBody: string;
  proJoin: string;
  proJoined: string;
  proLearnMore: string;
  /** The /pro page. */
  proPageTitle: string;
  proPageSummary: string;
  proIncludesHeading: string;
  proIncludes: readonly string[];
  proFreeHeading: string;
  proFree: (perTrack: number) => string;
  proNoBilling: string;
  proHasPlan: string;
  /** "What's new" (RPG: the Chronicle) and its unread marker. */
  whatsNew: string;
  whatsNewSummary: string;
  whatsNewUnread: string;
  whatsNewNone: string;
  releaseAdded: string;
  releaseUpdated: string;
  releaseFixed: string;
  releaseDate: (date: string) => string;

  // --- Layout review additions: new keys only, kept together to ease merging. ---
  /** The profile's settings section (time zone). */
  settingsHeading: string;
  /** The disclosure holding the badges not yet earned: "12 more to earn". */
  badgesToEarn: (n: number) => string;
  /** Beside a certificate's Private / Public control, for a learner without Pro. */
  certificatePublishPro: string;
  /** In place of the sharing actions on a private certificate, for a learner without Pro. */
  certificateActionsPro: string;
  /** Beside the Public control of a private certificate, for a learner whose email is unverified. */
  certificatePublishUnverified: string;

  // --- Server refusals, disabled controls and account copy. ---
  /** What the server's problem codes mean to the learner, worded for the mode. */
  problems: {
    planRequired: string;
    emailUnverified: string;
    challengeFailed: string;
    attemptInFlight: string;
    rateLimited: string;
    attemptDailyCap: (limit: number | null) => string;
    gradingBudget: (budgetMinutes: number | null) => string;
    busy: string;
  };
  /** Beside the disabled Run button, while the learner's email is unverified. */
  attemptNeedsVerified: string;
  /** The human check on the registration form. */
  humanCheckTitle: string;
  humanCheckBody: string;
  humanCheckPending: string;
  verifyEmailTitle: string;
  verifyLinkIncomplete: string;
  /** The profile's "your data" section. The policy link sits between the two halves. */
  accountData: {
    exportHeading: string;
    exportBodyBefore: string;
    exportPolicyLink: string;
    exportBodyAfter: string;
    exportAction: string;
    deleteHeading: string;
    deleteBody: string;
    deletePasswordLabel: string;
    deleteConfirm: string;
    deleteKeep: string;
    deleteStart: string;
  };
}

/** A badge's criterion as the lexicon words it: a branch to complete, or a count to reach. */
export type BadgeRule =
  | { kind: 'branch_complete'; branchName: string }
  | {
      kind:
        | 'exercises_passed'
        | 'first_try'
        | 'no_hint_passes'
        | 'streak_days'
        | 'level_reached'
        | 'capstones_passed';
      n: number;
    };

const COUNT_KINDS = new Set<string>([
  'exercises_passed',
  'first_try',
  'no_hint_passes',
  'streak_days',
  'level_reached',
  'capstones_passed',
]);

/** The API's badge requirement as a rule, or null for a kind this client does not know. */
export function toBadgeRule(
  requirement: { kind: string; n?: number | null; branch?: { id: string; title: string } | null },
  branchName: (id: string, title: string) => string,
): BadgeRule | null {
  if (requirement.kind === 'branch_complete' && requirement.branch != null)
    return {
      kind: 'branch_complete',
      branchName: branchName(requirement.branch.id, requirement.branch.title),
    };
  if (COUNT_KINDS.has(requirement.kind) && typeof requirement.n === 'number')
    return {
      kind: requirement.kind as Exclude<BadgeRule, { kind: 'branch_complete' }>['kind'],
      n: requirement.n,
    };
  return null;
}

const WORDS = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'];
/** "one exercise", "five exercises", "12 exercises". */
const counted = (n: number, one: string, other: string) =>
  `${WORDS[n] ?? String(n)} ${n === 1 ? one : other}`;

/** A talent that unlocks something, and the display name of the path it belongs to, if any. */
export interface LockingTalent {
  title: string;
  pathName: string | null;
}

const plural = (n: number, one: string, other: string) => `${n} ${n === 1 ? one : other}`;
const list = (items: readonly string[]) => items.join(', ');
/** "A", "A and B", "A, B and C". */
export const andList = (items: readonly string[]) =>
  items.length <= 1 ? items.join('') : `${items.slice(0, -1).join(', ')} and ${items.at(-1) ?? ''}`;
const branchNames = (requires: string | readonly string[]) =>
  (typeof requires === 'string' ? requires.split(', ') : requires).filter((n) => n !== '');
/** The branches a locked one waits on, with the verb agreeing: "A is", "A and B are". */
const waitingOn = (requires: string | readonly string[]) => {
  const names = branchNames(requires);
  return `${andList(names)} ${names.length > 1 ? 'are' : 'is'}`;
};
const INCLUDING_CAPSTONE = 'including its capstone project';
const withArticle = (name: string) => `${/^[aeiou]/i.test(name) ? 'an' : 'a'} ${name}`;
/** "Kid", "Kid or Deep", "Deep as a Loremaster", "Kid, or Deep as a Loremaster". */
const unlockingTalents = (talents: readonly LockingTalent[]) => {
  const paths = new Set(talents.map((t) => t.pathName));
  const [only] = paths;
  if (paths.size === 1 && only != null)
    return `${talents.map((t) => t.title).join(' or ')} as ${withArticle(only)}`;
  return talents
    .map((t) => (t.pathName === null ? t.title : `${t.title} as ${withArticle(t.pathName)}`))
    .join(paths.size > 1 && talents.length > 1 ? ', or ' : ' or ');
};
const PRO_FREE = (n: number) =>
  `The foundations and the first ${n} exercises of every track stay free, with every check, hint and badge.`;
const PRO_NO_BILLING =
  'Pro is not on sale yet and nothing is charged. Joining the waitlist records your email address so we can tell you when it opens.';

const professional: Lexicon = (() => {
  const branchCount = (n: number) => plural(n, 'track', 'tracks');
  const exerciseCount = (n: number) => plural(n, 'exercise', 'exercises');
  return {
    appName: 'Forgeway',
    branch: 'track',
    branchPlural: 'tracks',
    exercise: 'exercise',
    capstone: 'capstone project',
    level: 'level',
    hint: 'hint',
    hintPlural: 'hints',
    mapTitle: 'Syllabus',
    backToMap: 'Back to the syllabus',
    backToWorld: 'Back to all tracks',
    worldMapTitle: 'All tracks',
    worldMapDescription: (n) => `${branchCount(n)}, each opening from the first.`,
    mapSummary: (branches, exercises) =>
      `${branchCount(branches)} covering ${exerciseCount(exercises)}, each graded by automated checks.`,
    branchCount,
    exerciseCount,
    levelLabel: (level) => `Level ${level}`,
    xpLabel: (xp) => `${xp} XP`,
    progressLabel: (passed, total) => `${passed} of ${total} completed`,
    attemptSubmit: 'Run checks',
    attemptRunning: 'Running checks',
    status: { locked: 'Locked', available: 'Available', passed: 'Completed' },
    tier: {
      beginner: 'Beginner',
      intermediate: 'Intermediate',
      advanced: 'Advanced',
      capstone: 'Capstone',
    },
    capstoneLabel: 'Capstone project',
    capstoneNote: 'This project draws on the whole track.',
    capstoneState: { locked: 'Locked', available: 'Available', passed: 'Completed' },
    capstoneStrip: (xp, level) => `Capstone complete · +${xp} XP · Level ${level}`,
    capstoneCompletionTitle: 'Capstone complete',
    projectLabel: 'Guided project',
    carriedNote: (title) => `Continuing from your work on ${title}.`,
    carriedReset: 'Start from the provided code instead',
    carriedResetConfirm:
      'Your code here is replaced by the provided starter code. Your passing attempt at the earlier exercise is kept.',
    carriedResetAction: 'Use the provided code',
    carriedKeep: 'Keep my code',
    resetCode: 'Reset code',
    resetCodeConfirm:
      'Your code in this exercise is replaced by the starter code. Passed attempts and XP are not affected.',
    resetCodeAction: 'Reset to the starter code',
    editorShortcuts: 'Keyboard shortcuts',
    hintRevealAction: 'Reveal a hint',
    hintConfirmCost: 'Revealing a hint forfeits the +20% no-hint bonus.',
    lockedBranch: (requires) => `This track opens when ${waitingOn(requires)} complete.`,
    lockedExercise: 'This exercise is locked.',
    lockedByExercises: 'Complete these exercises first:',
    passedStrip: (xp, level) => `Passed · +${xp} XP · Level ${level}`,
    completionTitle: 'Passed',
    levelUp: (level) => `Level ${level}`,
    newlyOpened: (n) => `${plural(n, 'exercise', 'exercises')} now available`,
    signIn: 'Sign in',
    register: 'Create account',
    checkInboxTitle: 'Check your inbox',
    checkInboxBody: (email) =>
      `We have sent a link to ${email}. Follow it within 24 hours to verify your email address. You can look around in the meantime; running checks needs a verified address.`,
    checkInboxContinue: 'Continue to the syllabus',
    unverifiedBanner:
      'Verify your email address to run checks and publish certificates. Follow the link we sent you.',
    resendVerification: 'Send a new link',
    verificationResent: (email) => `A new link is on its way to ${email}.`,
    verifyingEmail: 'Verifying your email address…',
    emailVerifiedTitle: 'Email address verified',
    emailVerifiedBody: 'Thank you. You can now run checks and publish certificates.',
    forgotPassword: 'Forgot your password?',
    forgotPasswordTitle: 'Reset your password',
    forgotPasswordSent:
      'If an account uses that address, we have sent it a link to reset the password. The link works for 15 minutes.',
    resetPasswordTitle: 'Choose a new password',
    resetPasswordDone:
      'Your password has been changed and every session signed out. Sign in with the new password.',
    authSummary:
      'Learn AI engineering by building it. Every exercise is graded by automated checks.',
    passwordLabel: 'Password',
    newPasswordLabel: 'New password',
    forgotPasswordAction: 'Send reset link',
    resetPasswordAction: 'Set new password',
    resetLinkInvalid: 'This link has expired or has already been used:',
    resetLinkRequest: 'ask for a new one',

    profile: 'Profile',
    profileSummary: (level) =>
      `Level ${level}. Your specialisation, competencies and achievements.`,
    path: 'path',
    pathPlural: 'paths',
    specialisation: 'specialisation',
    specialisationPlural: 'specialisations',
    pathNames: {
      generalist: 'Generalist',
      retrieval: 'Retrieval specialist',
      protocols: 'Integration specialist',
      orchestration: 'Systems specialist',
      'knowledge-graphs': 'Knowledge engineer',
      memory: 'Memory engineer',
      'context-engineering': 'Context engineer',
      evals: 'Evaluation engineer',
    },
    pathCurrent: 'Current',
    pathChoose: 'Choose',
    pathChangeWarning:
      'Changing specialisation refunds the competency points you spent in the old specialisation. General competencies are kept.',
    pathConfirm: (name, dropped) =>
      `Switching to ${name} refunds ${list(dropped)}. The points come back to you.`,
    pathDropped: (titles) => `Refunded: ${list(titles)}.`,
    pathLocked: (names) => `Complete ${andList(names)} to choose this specialisation.`,
    titlesHeading: 'Titles',
    titlesNone: 'No titles yet. Acquire competencies to earn them.',
    timeZone: 'Time zone',
    timeZoneHint: 'Your streak counts days in this time zone.',
    timeZoneSave: 'Save time zone',

    talent: 'competency',
    talentPlural: 'competencies',
    talentTree: 'Competency matrix',
    talentTreeSummary: 'Each competency is earned by level and by passing the named exercises.',
    talentGeneral: 'General competencies',
    talentPoint: 'competency point',
    talentPointPlural: 'competency points',
    talentPoints: (available, total) =>
      `${available} of ${plural(total, 'competency point', 'competency points')} available`,
    talentPointsGained: (n) => `+${plural(n, 'competency point', 'competency points')}`,
    talentState: { allocated: 'Acquired', available: 'Available', locked: 'Locked' },
    talentAllocate: 'Acquire',
    talentDeallocate: 'Release',
    talentRequirements: 'Requirements',
    talentRequiresLevel: (level) => `Level ${level}`,
    talentRequiresParents: (titles) => `First: ${list(titles)}`,
    talentRequiresExercises: (titles) => `Complete: ${list(titles)}`,
    respec: 'Reset competencies',
    respecCost: 'Resetting refunds every point. It is free and you can do it as often as you like.',
    respecConfirm: 'Reset all',
    respecKeep: 'Keep my competencies',

    badge: 'achievement',
    badgePlural: 'achievements',
    badgeEarned: (date) => `Earned ${date}`,
    badgeNotEarned: 'Not yet earned',
    badgeAwarded: (title) => `Achievement earned: ${title}`,
    badgesAwarded: (n) => `${plural(n, 'achievement', 'achievements')} earned`,
    badgesSummary: (earned, total) => `${earned} of ${total} earned`,
    badgeRequirement: (rule, earned) => {
      const pass = earned ? 'Passed' : 'Pass';
      switch (rule.kind) {
        case 'branch_complete':
          return `${pass} every exercise in ${rule.branchName}.`;
        case 'exercises_passed':
          return `${pass} ${counted(rule.n, 'exercise', 'exercises')}.`;
        case 'first_try':
          return `${pass} ${counted(rule.n, 'exercise', 'exercises')} on the first graded attempt.`;
        case 'no_hint_passes':
          return `${pass} ${counted(rule.n, 'exercise', 'exercises')} without revealing a hint.`;
        case 'streak_days':
          return `${earned ? 'Learned' : 'Learn'} on ${counted(rule.n, 'day', 'days')} in a row.`;
        case 'level_reached':
          return `${earned ? 'Reached' : 'Reach'} level ${rule.n}.`;
        case 'capstones_passed':
          return `${pass} ${counted(rule.n, 'capstone project', 'capstone projects')}.`;
      }
    },

    streak: 'Streak',
    streakCurrent: (days) => (days === 0 ? 'No streak yet' : `${days}-day streak`),
    streakLongest: (days) => `Longest: ${plural(days, 'day', 'days')}`,

    referenceSolution: 'Reference solution',
    referenceNotes: 'Notes',
    referenceLocked: (talents) =>
      `A competency unlocks reference solutions for this track.${
        talents.length > 0 ? ` Acquire ${unlockingTalents(talents)} to unlock it.` : ''
      }`,

    certificatesHeading: 'Certificates',
    certificatesNone: 'No certificates yet. Complete a track to earn its certificate.',
    certificateEarned: (title, includesCapstone = false) =>
      `Certificate earned: ${title} track${includesCapstone ? `, ${INCLUDING_CAPSTONE}` : ''}`,
    certificateIncludesCapstone: INCLUDING_CAPSTONE,
    certificatesLink: 'View your certificates',

    proMark: 'Pro',
    proMarkDescription: 'Part of Forgeway Pro',
    proCtaTitle: 'Forgeway Pro is coming',
    proCtaBody:
      'This exercise is part of Forgeway Pro. Read the brief now, and join the waitlist to hear when Pro opens.',
    proJoin: 'Join the waitlist',
    proJoined: 'You are on the waitlist.',
    proLearnMore: 'What Pro includes',
    proPageTitle: 'Forgeway Pro',
    proPageSummary: 'The capstones, the guided projects and certificates you can share.',
    proIncludesHeading: 'What Pro includes',
    proIncludes: [
      'The capstone project that closes every track',
      'Every exercise of every track, past the free ones',
      'The guided projects, which build one codebase across several tracks',
      'Public certificates, with a verification page and LinkedIn sharing',
    ],
    proFreeHeading: 'What stays free',
    proFree: PRO_FREE,
    proNoBilling: PRO_NO_BILLING,
    proHasPlan: 'Your account already has Pro. Everything is open to you.',
    whatsNew: 'What’s new',
    whatsNewSummary: 'New exercises, changes and fixes, newest first.',
    whatsNewUnread: 'new release',
    whatsNewNone: 'No releases yet.',
    releaseAdded: 'Added',
    releaseUpdated: 'Updated',
    releaseFixed: 'Fixed',
    releaseDate: (date) => `Released ${date}`,

    // --- Layout review additions ---
    settingsHeading: 'Settings',
    badgesToEarn: (n) => `${n} more to earn`,
    certificatePublishPro:
      'Publishing a certificate is part of Forgeway Pro, which is not open yet.',
    certificateActionsPro:
      'With Forgeway Pro, a public certificate can be viewed, linked to, added to LinkedIn and shared.',
    certificatePublishUnverified: 'Verify your email address before you make a certificate public.',

    problems: {
      planRequired:
        'This is part of Forgeway Pro, which is not open yet. Join the waitlist to hear when it opens.',
      emailUnverified: 'Verify your email address first. We sent a link when you registered.',
      challengeFailed: 'The human check did not pass. Complete it again, then retry.',
      attemptInFlight: 'An attempt is already being graded. Wait for its result, then run again.',
      rateLimited: 'You are submitting too quickly. Wait a moment and try again.',
      attemptDailyCap: (limit) =>
        `${limit === null ? 'Today’s graded attempts are' : `Today’s ${limit} graded attempts are`} used up. More free up as attempts from 24 hours ago age out.`,
      gradingBudget: (minutes) =>
        `Today’s grading time is used up${minutes === null ? '' : `, at ${minutes} minutes in any 24 hours`}. More frees up as your earlier runs age out.`,
      busy: 'Grading is busy right now. Your code is saved; try again in a minute.',
    },
    attemptNeedsVerified: 'Verify your email address to run checks.',
    humanCheckTitle: 'Human check',
    humanCheckBody: 'A quick check by Cloudflare that you are a person, not a script.',
    humanCheckPending: 'Complete the human check to continue.',
    verifyEmailTitle: 'Verify your email address',
    verifyLinkIncomplete: 'This link is incomplete. Open the whole link from the email.',
    accountData: {
      exportHeading: 'Your data',
      exportBodyBefore:
        'Download a JSON file of everything we hold about you: your account, your progress, and every attempt with its code. The',
      exportPolicyLink: 'privacy policy',
      exportBodyAfter: 'says what we keep and why.',
      exportAction: 'Download your data',
      deleteHeading: 'Delete your account',
      deleteBody:
        'This deletes your account and everything in it: progress, attempts, badges and certificates. Public certificate links stop working. It cannot be undone.',
      deletePasswordLabel: 'Your password, to confirm',
      deleteConfirm: 'Delete my account for good',
      deleteKeep: 'Keep my account',
      deleteStart: 'Delete account…',
    },
  };
})();

const rpg: Lexicon = (() => {
  const branchCount = (n: number) => plural(n, 'zone', 'zones');
  const exerciseCount = (n: number) => plural(n, 'quest', 'quests');
  return {
    appName: 'Forgeway',
    branch: 'zone',
    branchPlural: 'zones',
    exercise: 'quest',
    capstone: 'boss challenge',
    level: 'level',
    hint: 'scroll of insight',
    hintPlural: 'scrolls of insight',
    mapTitle: 'The Atlas',
    backToMap: 'Back to the atlas',
    backToWorld: 'Back to the world',
    worldMapTitle: 'The known world',
    worldMapDescription: (n) =>
      `A map of ${branchCount(n)}: the starter zone at the centre, with roads running out to the rest. Roads to zones still in fog are dashed.`,
    mapSummary: (branches, exercises) =>
      `${branchCount(branches)} charted, ${exerciseCount(exercises)} to conquer.`,
    branchCount,
    exerciseCount,
    levelLabel: (level) => `Level ${level}`,
    xpLabel: (xp) => `${xp} XP`,
    progressLabel: (passed, total) => `${passed} of ${total} conquered`,
    attemptSubmit: 'Attempt the quest',
    attemptRunning: 'The trial is under way',
    status: { locked: 'Shrouded', available: 'Open', passed: 'Conquered' },
    tier: { beginner: 'Novice', intermediate: 'Adept', advanced: 'Master', capstone: 'Boss' },
    capstoneLabel: 'Boss challenge',
    capstoneNote: 'The guardian of this zone draws on every quest you have conquered here.',
    capstoneState: { locked: 'Sealed', available: 'Awaiting', passed: 'Defeated' },
    capstoneStrip: (xp, level) => `Boss defeated · +${xp} XP · Level ${level}`,
    capstoneCompletionTitle: 'Boss defeated',
    projectLabel: 'Expedition',
    carriedNote: (title) => `You carry your work from ${title} into this quest.`,
    carriedReset: 'Start from the provided code instead',
    carriedResetConfirm:
      'The work you carried is set down and the provided code takes its place. Your victory in the earlier quest stands.',
    carriedResetAction: 'Set it down',
    carriedKeep: 'Keep my work',
    resetCode: 'Begin anew',
    resetCodeConfirm:
      'Your work on this quest is wiped clean and the starting scroll returns. Quests you have conquered, and your XP, stay yours.',
    resetCodeAction: 'Wipe it clean',
    editorShortcuts: "The scribe's shortcuts",
    hintRevealAction: 'Unroll a scroll of insight',
    hintConfirmCost: 'Unrolling a scroll of insight forfeits the +20% no-hint bonus.',
    lockedBranch: (requires) => `This zone lies in fog until ${waitingOn(requires)} conquered.`,
    lockedExercise: 'This quest is shrouded in fog.',
    lockedByExercises: 'Conquer these quests to lift the fog:',
    passedStrip: (xp, level) => `Conquered · +${xp} XP · Level ${level}`,
    completionTitle: 'Quest conquered',
    levelUp: (level) => `Level ${level}`,
    newlyOpened: (n) => `${plural(n, 'new quest', 'new quests')} revealed`,
    signIn: 'Enter the realm',
    register: 'Begin your journey',
    checkInboxTitle: 'A messenger rides to you',
    checkInboxBody: (email) =>
      `A sealed letter is on its way to ${email}. Open it within 24 hours to prove your name. You may wander the realm meanwhile; quests open once your name is proven.`,
    checkInboxContinue: 'Enter the world map',
    unverifiedBanner:
      'Prove your name to attempt quests and display your seals: follow the link in the letter we sent you.',
    resendVerification: 'Send another letter',
    verificationResent: (email) => `Another letter rides to ${email}.`,
    verifyingEmail: 'Breaking the seal…',
    emailVerifiedTitle: 'Your name is proven',
    emailVerifiedBody: 'The gates are open. Quests and seals await.',
    forgotPassword: 'Lost your passphrase?',
    forgotPasswordTitle: 'Recover your passphrase',
    forgotPasswordSent:
      'If a traveller bears that address, a letter to reset the passphrase is on its way. It holds for 15 minutes.',
    resetPasswordTitle: 'Choose a new passphrase',
    resetPasswordDone:
      'Your passphrase is changed and every session ended. Enter the realm with the new one.',
    authSummary: 'Learn AI engineering by building it. Every quest is judged by automated trials.',
    passwordLabel: 'Passphrase',
    newPasswordLabel: 'New passphrase',
    forgotPasswordAction: 'Send the letter',
    resetPasswordAction: 'Set new passphrase',
    resetLinkInvalid: 'This letter’s seal has lapsed or has already been broken:',
    resetLinkRequest: 'send for another',

    profile: 'Character sheet',
    profileSummary: (level) => `Level ${level}. Your class, talents and deeds.`,
    path: 'path',
    pathPlural: 'paths',
    specialisation: 'class',
    specialisationPlural: 'classes',
    pathNames: {
      generalist: 'Wayfarer',
      retrieval: 'Loremaster',
      protocols: 'Artificer',
      orchestration: 'Conductor',
      'knowledge-graphs': 'Surveyor',
      memory: 'Chronicler',
      'context-engineering': 'Weaver',
      evals: 'Arbiter',
    },
    pathCurrent: 'Your class',
    pathChoose: 'Take this class',
    pathChangeWarning:
      'Changing class refunds the talent points you spent in the old class. Common talents are kept.',
    pathConfirm: (name, dropped) =>
      `Becoming a ${name} unlearns ${list(dropped)}. The points return to you.`,
    pathDropped: (titles) => `Unlearned: ${list(titles)}.`,
    pathLocked: (names) => `Conquer ${andList(names)} to take this class.`,
    titlesHeading: 'Titles',
    titlesNone: 'No titles yet. Learn talents to earn them.',
    timeZone: 'Time zone',
    timeZoneHint: 'Your streak counts days in this time zone.',
    timeZoneSave: 'Save time zone',

    talent: 'talent',
    talentPlural: 'talents',
    talentTree: 'Talent tree',
    talentTreeSummary: 'Each talent is learned by level and by conquering the named quests.',
    talentGeneral: 'Common talents',
    talentPoint: 'talent point',
    talentPointPlural: 'talent points',
    talentPoints: (available, total) =>
      `${available} of ${plural(total, 'talent point', 'talent points')} to spend`,
    talentPointsGained: (n) => `+${plural(n, 'talent point', 'talent points')}`,
    talentState: { allocated: 'Learned', available: 'Ready to learn', locked: 'Sealed' },
    talentAllocate: 'Learn',
    talentDeallocate: 'Unlearn',
    talentRequirements: 'To learn',
    talentRequiresLevel: (level) => `Level ${level}`,
    talentRequiresParents: (titles) => `First learn: ${list(titles)}`,
    talentRequiresExercises: (titles) => `Conquer: ${list(titles)}`,
    respec: 'Respec talents',
    respecCost:
      'Respeccing returns every point. It costs nothing and you may do it as often as you like.',
    respecConfirm: 'Respec all',
    respecKeep: 'Keep my talents',

    badge: 'badge',
    badgePlural: 'badges',
    badgeEarned: (date) => `Won ${date}`,
    badgeNotEarned: 'Not yet won',
    badgeAwarded: (title) => `Badge won: ${title}`,
    badgesAwarded: (n) => `${plural(n, 'badge', 'badges')} won`,
    badgesSummary: (earned, total) => `${earned} of ${total} won`,
    badgeRequirement: (rule, earned) => {
      const conquer = earned ? 'Conquered' : 'Conquer';
      switch (rule.kind) {
        case 'branch_complete':
          return `${conquer} every quest in ${rule.branchName}.`;
        case 'exercises_passed':
          return `${conquer} ${counted(rule.n, 'quest', 'quests')}.`;
        case 'first_try':
          return `${conquer} ${counted(rule.n, 'quest', 'quests')} at the first attempt.`;
        case 'no_hint_passes':
          return `${conquer} ${counted(rule.n, 'quest', 'quests')} without unrolling a scroll of insight.`;
        case 'streak_days':
          return `${earned ? 'Journeyed' : 'Journey'} on ${counted(rule.n, 'day', 'days')} in a row.`;
        case 'level_reached':
          return `${earned ? 'Reached' : 'Reach'} level ${rule.n}.`;
        case 'capstones_passed':
          return `${earned ? 'Defeated' : 'Defeat'} ${counted(rule.n, 'boss', 'bosses')}.`;
      }
    },

    streak: 'Streak',
    streakCurrent: (days) =>
      days === 0 ? 'No streak yet' : `Learning streak: ${plural(days, 'day', 'days')}`,
    streakLongest: (days) => `Longest streak: ${plural(days, 'day', 'days')}`,

    referenceSolution: "Master's copy",
    referenceNotes: 'The master’s notes',
    referenceLocked: (talents) =>
      `A talent unlocks master's copies for this zone.${
        talents.length > 0 ? ` Learn ${unlockingTalents(talents)} to unlock it.` : ''
      }`,

    certificatesHeading: 'Seals of completion',
    certificatesNone: 'No seals yet. Complete a zone to earn its certificate.',
    certificateEarned: (title, includesCapstone = false) =>
      `The seal is set. Certificate earned: ${title} track${includesCapstone ? `, ${INCLUDING_CAPSTONE}` : ''}`,
    certificateIncludesCapstone: INCLUDING_CAPSTONE,
    certificatesLink: 'See your seals of completion',

    proMark: 'Guild · Pro',
    proMarkDescription: 'For guild members: part of Forgeway Pro',
    proCtaTitle: 'The guild opens soon: Forgeway Pro is coming',
    proCtaBody:
      'This quest is for guild members, in Forgeway Pro. Read the brief now, and join the waitlist to hear when the guild opens its doors.',
    proJoin: 'Join the waitlist',
    proJoined: 'Your name is on the guild’s waitlist.',
    proLearnMore: 'What guild members get',
    proPageTitle: 'The guild: Forgeway Pro',
    proPageSummary: 'Boss challenges, expeditions and seals you can show the world.',
    proIncludesHeading: 'What guild members get',
    proIncludes: [
      'The boss challenge that guards every zone',
      'Every quest of every zone, past the open ones',
      'The expeditions, which build one codebase across several zones',
      'Public seals of completion, with a verification page and LinkedIn sharing',
    ],
    proFreeHeading: 'What stays open to every traveller',
    proFree: (n) =>
      `The starter zone and the first ${n} quests of every zone stay free, with every check, scroll of insight and badge.`,
    proNoBilling: PRO_NO_BILLING,
    proHasPlan: 'You are already a guild member, with Forgeway Pro. Every road is open to you.',
    whatsNew: 'Chronicle',
    whatsNewSummary: 'New quests, revisions and mendings, the latest first.',
    whatsNewUnread: 'new entry',
    whatsNewNone: 'The chronicle is still blank.',
    releaseAdded: 'New quests',
    releaseUpdated: 'Revised',
    releaseFixed: 'Mended',
    releaseDate: (date) => `Recorded ${date}`,

    // --- Layout review additions ---
    settingsHeading: 'Settings',
    badgesToEarn: (n) => `${n} more to win`,
    certificatePublishPro:
      'Showing a seal to the world is for guild members, in Forgeway Pro, which is not open yet.',
    certificateActionsPro:
      'A guild member’s public seal can be viewed, linked to, added to LinkedIn and shared.',
    certificatePublishUnverified:
      'Confirm your messenger address before you show a seal to the world.',

    problems: {
      planRequired:
        'That road is for guild members, in Forgeway Pro, which is not open yet. Join the waitlist to hear when the gates open.',
      emailUnverified:
        'Confirm your messenger address first. A letter was sent when you signed the register.',
      challengeFailed: 'The gatekeeper was not satisfied. Pass the trial again, then retry.',
      attemptInFlight:
        'Another attempt is still before the judges. Wait for their verdict, then try again.',
      rateLimited: 'You are knocking too fast. Pause a moment and try again.',
      attemptDailyCap: (limit) =>
        `${limit === null ? 'Today’s attempts are' : `Today’s ${limit} attempts are`} spent. More return as attempts from 24 hours ago fade.`,
      gradingBudget: (minutes) =>
        `The judges’ hours for today are spent${minutes === null ? '' : `, at ${minutes} minutes in any 24 hours`}. More return as your earlier trials fade.`,
      busy: 'The judges’ hall is full. Your code is safe; try again in a minute.',
    },
    attemptNeedsVerified: 'Confirm your messenger address to attempt quests.',
    humanCheckTitle: 'Trial of the gate',
    humanCheckBody:
      'A quick trial, set by Cloudflare, to show you are a traveller and not a script.',
    humanCheckPending: 'Pass the trial of the gate to continue.',
    verifyEmailTitle: 'Confirm your messenger address',
    verifyLinkIncomplete: 'This seal is broken. Open the whole link from the letter.',
    accountData: {
      exportHeading: 'Your records',
      exportBodyBefore:
        'Download a JSON file of everything the guild holds about you: your account, your progress, and every attempt with its code. The',
      exportPolicyLink: 'privacy policy',
      exportBodyAfter: 'says what is kept and why.',
      exportAction: 'Download your records',
      deleteHeading: 'Leave the guild',
      deleteBody:
        'This deletes your account and everything in it: progress, attempts, badges and seals. Public seal links stop working. It cannot be undone.',
      deletePasswordLabel: 'Your passphrase, to confirm',
      deleteConfirm: 'Leave the guild for good',
      deleteKeep: 'Stay in the guild',
      deleteStart: 'Leave the guild…',
    },
  };
})();

export const LEXICONS: Record<Mode, Lexicon> = { professional, rpg };
