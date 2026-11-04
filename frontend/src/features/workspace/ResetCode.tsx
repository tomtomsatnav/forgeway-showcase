import { RotateCcw } from 'lucide-react';
import { useState } from 'react';

import { Button } from '../../components/Button';
import { useLexicon } from '../../theme/useTheme';

interface ResetCodeProps {
  onReset: () => void;
  pending?: boolean;
  error?: string | null;
}

/**
 * Puts the editor back to the exercise's starter code. It replaces the learner's work, so it
 * asks first; passed attempts and XP are untouched, and the confirmation says so.
 */
export function ResetCode({ onReset, pending = false, error }: ResetCodeProps) {
  const lexicon = useLexicon();
  const [confirming, setConfirming] = useState(false);

  const failure = error != null && (
    <p role="alert" className="m-0 text-sm text-danger">
      {error}
    </p>
  );
  if (!confirming) {
    return (
      <>
        <Button
          variant="quiet"
          onClick={() => {
            setConfirming(true);
          }}
        >
          <RotateCcw aria-hidden="true" className="h-4 w-4" />
          {lexicon.resetCode}
        </Button>
        {failure}
      </>
    );
  }
  return (
    <div
      role="group"
      aria-label={lexicon.resetCode}
      className="basis-full space-y-3 rounded-control border border-warning bg-warning-soft p-3"
    >
      <p className="m-0 text-sm text-ink">{lexicon.resetCodeConfirm}</p>
      <div className="flex flex-wrap gap-2">
        <Button
          variant="primary"
          loading={pending}
          onClick={() => {
            onReset();
            setConfirming(false);
          }}
        >
          {lexicon.resetCodeAction}
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
      {failure}
    </div>
  );
}
