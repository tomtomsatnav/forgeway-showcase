import { RotateCcw } from 'lucide-react';
import { useState } from 'react';

import { Button } from '../../components/Button';
import { useLexicon } from '../../theme/useTheme';

interface CarriedFilesProps {
  /** The earlier exercise the files came from, as the learner knows it. */
  title: string;
  onReset: () => void;
  pending?: boolean;
  error?: string | null;
}

/**
 * Says the editor opened on the learner's own files from an earlier exercise, and offers the
 * starter instead. Resetting replaces their code here, so it sits behind a confirm step.
 */
export function CarriedFiles({ title, onReset, pending = false, error }: CarriedFilesProps) {
  const lexicon = useLexicon();
  const [confirming, setConfirming] = useState(false);

  return (
    <div role="note" className="space-y-3 rounded-control border border-line-strong bg-raised p-3">
      <p className="m-0 text-sm text-ink">{lexicon.carriedNote(title)}</p>
      {confirming ? (
        <div
          role="group"
          aria-label={lexicon.carriedReset}
          className="space-y-3 rounded-control border border-warning bg-warning-soft p-3"
        >
          <p className="m-0 text-sm text-ink">{lexicon.carriedResetConfirm}</p>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="primary"
              loading={pending}
              onClick={() => {
                onReset();
              }}
            >
              {lexicon.carriedResetAction}
            </Button>
            <Button
              variant="quiet"
              onClick={() => {
                setConfirming(false);
              }}
            >
              {lexicon.carriedKeep}
            </Button>
          </div>
        </div>
      ) : (
        <Button
          variant="secondary"
          onClick={() => {
            setConfirming(true);
          }}
        >
          <RotateCcw aria-hidden="true" className="h-4 w-4" />
          {lexicon.carriedReset}
        </Button>
      )}
      {error != null && (
        <p role="alert" className="m-0 text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
