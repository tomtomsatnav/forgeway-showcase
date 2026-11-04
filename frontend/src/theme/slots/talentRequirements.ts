/** Turns a talent and the backend's per-node reasons into one list of met and unmet requirements. */
import type { TalentNode } from '../../api/types';

export type RequirementKind = 'level' | 'parent' | 'exercise' | 'other';

export interface Requirement {
  kind: RequirementKind;
  /** The title for a parent or exercise; the backend's wording for `other`. */
  subject: string;
  /** Only meaningful for `level`. */
  level: number;
  met: boolean;
}

interface Context {
  /** Talent titles by id, to name parents. */
  titles: ReadonlyMap<string, string>;
  /** Talent states by id, which say whether a parent is taken. */
  states: ReadonlyMap<string, TalentNode['state']>;
  exerciseTitle: (id: string) => string;
}

const MAPPED_CODES = new Set(['level', 'parents', 'exercises']);

/**
 * The backend's reasons name why a talent cannot be taken now, one per kind of requirement
 * (`level`, `parents`, `exercises`) with every missing item inside one sentence. A requirement is
 * unmet when its kind has a reason and, for parents and exercises, the item is the one named in
 * it. Any other reason (a wrong path, no points left) has no requirement to hang on and stays as
 * its own unmet line. A taken talent has met everything.
 */
export function talentRequirements(node: TalentNode, context: Context): Requirement[] {
  const taken = node.state === 'allocated';
  const reasonFor = (code: string) => node.reasons.find((reason) => reason.code === code);

  const metBy = (code: string, subjects: readonly string[]): boolean[] => {
    const reason = reasonFor(code);
    if (taken || reason === undefined) return subjects.map(() => true);
    const met = subjects.map((subject) => !reason.detail.includes(subject));
    // A reason that names none of the items (reworded, say) must not read as all met.
    return met.every(Boolean) ? subjects.map(() => false) : met;
  };

  const parentSubjects = node.parents.map((id) => context.titles.get(id) ?? id);
  const parentMet = metBy('parents', parentSubjects).map((met, i) => {
    const state = context.states.get(node.parents[i] ?? '');
    return taken || state === undefined ? met : state === 'allocated';
  });
  const exerciseSubjects = node.required_exercises.map(context.exerciseTitle);
  const exerciseMet = metBy('exercises', exerciseSubjects);

  const requirements: Requirement[] = [
    { kind: 'level', subject: '', level: node.min_level, met: taken || !reasonFor('level') },
    ...parentSubjects.map((subject, i) => ({
      kind: 'parent' as const,
      subject,
      level: 0,
      met: parentMet[i] ?? false,
    })),
    ...exerciseSubjects.map((subject, i) => ({
      kind: 'exercise' as const,
      subject,
      level: 0,
      met: exerciseMet[i] ?? false,
    })),
  ];
  if (!taken)
    for (const reason of node.reasons)
      if (!MAPPED_CODES.has(reason.code))
        requirements.push({ kind: 'other', subject: reason.detail, level: 0, met: false });
  return requirements;
}
