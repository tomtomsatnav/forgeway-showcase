import type { ComponentType } from 'react';

import type { Mode } from '../../api/types';
import { useTheme } from '../useTheme';
import { Atlas } from './Atlas';
import { ProfessionalCompletionMoment, RpgCompletionMoment } from './CompletionMoment';
import { ProfessionalPageHeader, RpgPageHeader } from './PageHeader';
import { Syllabus } from './Syllabus';
import { TalentConstellation } from './TalentConstellation';
import { TalentMatrix } from './TalentMatrix';
import type {
  BranchOverviewProps,
  CompletionMomentProps,
  PageHeaderProps,
  TalentTreeProps,
} from './types';

interface SlotRenderers {
  BranchOverview: ComponentType<BranchOverviewProps>;
  CompletionMoment: ComponentType<CompletionMomentProps>;
  PageHeader: ComponentType<PageHeaderProps>;
  TalentTree: ComponentType<TalentTreeProps>;
}

/** One renderer per mode for each slot; TypeScript requires every mode to supply all four. */
export const SLOTS: Record<Mode, SlotRenderers> = {
  professional: {
    BranchOverview: Syllabus,
    CompletionMoment: ProfessionalCompletionMoment,
    PageHeader: ProfessionalPageHeader,
    TalentTree: TalentMatrix,
  },
  rpg: {
    BranchOverview: Atlas,
    CompletionMoment: RpgCompletionMoment,
    PageHeader: RpgPageHeader,
    TalentTree: TalentConstellation,
  },
};

export function BranchOverview(props: BranchOverviewProps) {
  const Renderer = SLOTS[useTheme().mode].BranchOverview;
  return <Renderer {...props} />;
}

export function CompletionMoment(props: CompletionMomentProps) {
  const Renderer = SLOTS[useTheme().mode].CompletionMoment;
  return <Renderer {...props} />;
}

export function PageHeader(props: PageHeaderProps) {
  const Renderer = SLOTS[useTheme().mode].PageHeader;
  return <Renderer {...props} />;
}

export function TalentTree(props: TalentTreeProps) {
  const Renderer = SLOTS[useTheme().mode].TalentTree;
  return <Renderer {...props} />;
}
