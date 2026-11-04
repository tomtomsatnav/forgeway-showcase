import { useLearnerMap } from '../../api/hooks';
import { errorMessage } from '../../api/errors';
import { BranchOverview, PageHeader } from '../../theme/slots';
import { useLexicon } from '../../theme/useTheme';

export function MapPage() {
  const lexicon = useLexicon();
  const map = useLearnerMap();

  if (map.isPending) {
    return (
      <p role="status" className="mx-auto max-w-page px-4 py-12 text-ink-muted sm:px-6">
        Loading…
      </p>
    );
  }
  if (map.isError) {
    return (
      <p role="alert" className="mx-auto max-w-page px-4 py-12 text-danger sm:px-6">
        {errorMessage(map.error)}
      </p>
    );
  }

  const { branches } = map.data;
  const exerciseTotal = branches.reduce((sum, branch) => sum + branch.exercises.length, 0);
  return (
    <div className="mx-auto max-w-page space-y-10 px-4 py-8 sm:px-6">
      <PageHeader
        title={lexicon.mapTitle}
        summary={lexicon.mapSummary(branches.length, exerciseTotal)}
      />
      <BranchOverview branches={branches} />
    </div>
  );
}
