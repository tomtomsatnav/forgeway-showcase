import { useQuery } from '@tanstack/react-query';

import { api, unwrap } from '../../api/client';
import type { BranchSummary } from '../../api/types';

/**
 * The public catalogue: every track as a brand-new learner on the free plan sees it, for visitors
 * who are not signed in (`/api/map` needs a session). The API caches it for five minutes.
 */
export function useCatalogue(enabled = true) {
  return useQuery({
    queryKey: ['catalogue'],
    queryFn: async () => unwrap(await api.GET('/api/catalogue')),
    staleTime: 5 * 60 * 1000,
    retry: false,
    enabled,
  });
}

/**
 * The counts the landing page states, all read from the catalogue. A primer is optional and
 * outside the course proper, so it is counted apart from the tracks and their exercises.
 */
export function catalogueCounts(branches: readonly BranchSummary[]) {
  const course = branches.filter((branch) => branch.kind !== 'primer');
  const exercises = course.flatMap((branch) => branch.exercises);
  return {
    tracks: course.filter((branch) => branch.kind !== 'project').length,
    projects: course.filter((branch) => branch.kind === 'project').length,
    primers: branches.length - course.length,
    exercises: exercises.length,
    capstones: exercises.filter((exercise) => exercise.tier === 'capstone').length,
  };
}
