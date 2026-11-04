import { useState } from 'react';

import { useLexicon } from '../theme/useTheme';
import { Button } from './Button';
import { Markdown } from './Markdown';

interface HintRevealProps {
  revealed: readonly string[];
  total: number;
  onReveal: () => void;
  pending?: boolean;
  error?: string | null;
}

/**
 * Hints appear one at a time. The first reveal forfeits the no-hint bonus, so it sits behind a
 * confirm step that says so; later reveals cost nothing further and need no confirmation.
 */
export function HintReveal({ revealed, total, onReveal, pending = false, error }: HintRevealProps) {
  const lexicon = useLexicon();
  const [confirming, setConfirming] = useState(false);
  const remaining = total - revealed.length;
  const bonusAlreadyLost = revealed.length > 0;

  if (total === 0) return null;

  const reveal = () => {
    setConfirming(false);
    onReveal();
  };

  return (
    <section aria-labelledby="hints-heading" className="space-y-3">
      <h2 id="hints-heading" className="m-0 font-ui text-base font-semibold first-letter:uppercase">
        {lexicon.hintPlural}
      </h2>
      {revealed.length > 0 && (
        <ol className="m-0 space-y-2 pl-5 text-sm">
          {revealed.map((hint, index) => (
            <li key={index}>
              <Markdown inline>{hint}</Markdown>
            </li>
          ))}
        </ol>
      )}
      {remaining > 0 &&
        (confirming ? (
          <div
            role="group"
            aria-label={`Confirm ${lexicon.hint}`}
            className="space-y-3 rounded-control border border-warning bg-warning-soft p-3"
          >
            <p className="m-0 text-sm text-ink">{lexicon.hintConfirmCost}</p>
            <div className="flex flex-wrap gap-2">
              <Button variant="primary" onClick={reveal}>
                Reveal anyway
              </Button>
              <Button
                variant="quiet"
                onClick={() => {
                  setConfirming(false);
                }}
              >
                Keep trying
              </Button>
            </div>
          </div>
        ) : (
          <Button
            variant="secondary"
            loading={pending}
            onClick={
              bonusAlreadyLost
                ? reveal
                : () => {
                    setConfirming(true);
                  }
            }
          >
            {lexicon.hintRevealAction}
            <span className="tabular text-ink-muted">
              {revealed.length}/{total}
            </span>
          </Button>
        ))}
      {error != null && (
        <p role="alert" className="m-0 text-sm text-danger">
          {error}
        </p>
      )}
    </section>
  );
}
