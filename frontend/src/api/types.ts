import type { components } from './schema';

type Schemas = components['schemas'];

export type Me = Schemas['Me'];
export type Profile = Schemas['Profile'];
export type LearnerMap = Schemas['LearnerMap'];
export type BranchSummary = Schemas['BranchSummary'];
export type ExerciseSummary = Schemas['ExerciseSummary'];
export type ExerciseDetail = Schemas['ExerciseDetail'];
export type AttemptDetail = Schemas['AttemptDetail'];
export type CheckInfo = Schemas['CheckInfo'];
export type CheckResult = Schemas['CheckResult'];
export type Progression = Schemas['Progression'];
export type Level = Schemas['Level'];
export type Streak = Schemas['Streak'];
export type PathProfile = Schemas['PathProfile'];
export type PathOption = Schemas['PathOption'];
export type PathFlavour = Schemas['PathFlavour'];
export type TalentTree = Schemas['TalentTree'];
export type TalentNode = Schemas['TalentNode'];
export type BadgeStatus = Schemas['BadgeStatus'];
export type BadgeAwarded = Schemas['BadgeAwarded'];
export type Certificate = Schemas['Certificate'];
export type CertificateIssued = Schemas['CertificateIssued'];
export type LinkedInFields = Schemas['LinkedInFields'];
export type ReferenceSolution = Schemas['ReferenceSolution'];
export type ThemeFlavour = Schemas['ThemeFlavour'];
export type BossFlavour = Schemas['BossFlavour'];
export type WaitlistStatus = Schemas['WaitlistStatus'];
export type Release = Schemas['Release'];
export type ReleaseList = Schemas['ReleaseList'];
export type ReleaseExercise = Schemas['ReleaseExercise'];
export type Plan = Me['plan'];

export type TalentState = TalentNode['state'];
export type ExerciseStatus = ExerciseSummary['status'];
export type AttemptStatus = AttemptDetail['status'];
export type Mode = 'rpg' | 'professional';
export type ColourScheme = 'system' | 'light' | 'dark';
export type Tier = 'beginner' | 'intermediate' | 'advanced' | 'capstone';

export const TIERS: readonly Tier[] = ['beginner', 'intermediate', 'advanced', 'capstone'];

/** The API types tier as a free string; unknown values fall back to the lowest tier. */
export function toTier(value: string): Tier {
  return TIERS.find((tier) => tier === value) ?? 'beginner';
}

export function isTerminal(status: AttemptStatus): boolean {
  return status === 'passed' || status === 'failed' || status === 'errored';
}
