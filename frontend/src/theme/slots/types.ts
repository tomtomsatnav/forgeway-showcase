import type { BranchSummary, Progression, TalentTree } from '../../api/types';

/** Props are identical for every mode's renderer of a slot. */
export interface BranchOverviewProps {
  branches: readonly BranchSummary[];
}

export interface CompletionMomentProps {
  progression: Progression;
  /** Exercises this pass opened, resolved to titles. */
  unlocked: readonly { id: string; title: string }[];
  onDismiss: () => void;
  /** Progress towards the next level, 0 to 1, for the seal's ring. */
  levelFraction: number;
  /** Set when the pass was a capstone, so the moment can be the capstone's own. */
  capstone?: { exerciseId: string; title: string } | null;
}

export interface TalentTreeProps {
  tree: TalentTree;
  /** An exercise id as a title, for the requirements. */
  exerciseTitle: (id: string) => string;
  /** A subtree id as a heading: "General" or the name of a path. */
  subtreeName: (subtree: string) => string;
  /** The talent an allocate or deallocate is in flight for, if any. */
  pendingNode: string | null;
  respeccing: boolean;
  /** The last action's problem (a 409 reason, say), already worded; null when there is none. */
  problem: string | null;
  onAllocate: (nodeId: string) => void;
  onDeallocate: (nodeId: string) => void;
  onRespec: () => void;
}

export interface PageHeaderProps {
  title: string;
  /** The exercise this page is about, if any, so a mode can theme its title. */
  exerciseId?: string;
  summary?: string;
  /** The exercise is a capstone: the header frames it as one (a boss in RPG mode). */
  capstone?: boolean;
  /** The guided project the exercise belongs to, by name: the header labels it as one. */
  project?: string;
}
