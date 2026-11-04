import { Download, ExternalLink, KeyRound } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { usePublicConfig } from '../../api/hooks';
import { Button } from '../../components/Button';
import { useLexicon } from '../../theme/useTheme';

/** The guide's page in the app (docs/live-mode.md, served by the API). */
export const LIVE_MODE_GUIDE = '/live-mode';
/** The toolkit reference's page in the app (docs/toolkit-reference.md, served by the API). */
export const TOOLKIT_REFERENCE = '/toolkit';

const LINK_BUTTON =
  'inline-flex min-h-11 items-center justify-center gap-2 rounded-control border border-transparent bg-transparent px-4 font-ui text-base font-medium text-ink-secondary transition-colors duration-fast hover:bg-sunken hover:text-ink';

const ENV_VARS: readonly (readonly [string, string])[] = [
  ['FORGEWAY_LIVE', 'anthropic, openai or openai-compatible'],
  ['ANTHROPIC_API_KEY or OPENAI_API_KEY', 'your own key, set in your shell'],
  ['FORGEWAY_MODEL', 'the model to call'],
  ['FORGEWAY_BASE_URL', 'for Ollama and other local servers'],
];

/**
 * Downloads the exercise as a zip (the brief, the learner's current files, a README) to run
 * against a real model on their own machine, then says how. Forgeway never asks for a key: the
 * learner's own environment holds it, and grades still come from the checks here.
 */
export function RunLocally({ exerciseId }: { exerciseId: string }) {
  const lexicon = useLexicon();
  const [open, setOpen] = useState(false);
  const link = useRef<HTMLAnchorElement>(null);
  return (
    <>
      <a
        ref={link}
        href={`/api/exercises/${exerciseId}/download`}
        download
        className={LINK_BUTTON}
        onClick={() => {
          setOpen(true);
        }}
      >
        <Download aria-hidden="true" className="h-4 w-4" />
        {lexicon.runLocally}
      </a>
      {open && (
        <RunLocallyPanel
          onClose={() => {
            setOpen(false);
            link.current?.focus();
          }}
        />
      )}
    </>
  );
}

function RunLocallyPanel({ onClose }: { onClose: () => void }) {
  const lexicon = useLexicon();
  const config = usePublicConfig();
  const wheel = config.data?.kit_wheel_url;
  const panel = useRef<HTMLElement>(null);
  // Focus moves to the panel as the download starts, so a screen reader reads what to do next.
  useEffect(() => {
    panel.current?.focus();
  }, []);
  return (
    <section
      ref={panel}
      tabIndex={-1}
      aria-label={lexicon.runLocally}
      className="basis-full space-y-3 rounded-control border border-line-strong bg-raised p-3 text-sm"
    >
      <p className="m-0 text-ink">{lexicon.runLocallyIntro}</p>
      <div className="space-y-1">
        <p className="m-0 font-semibold text-ink">Install the toolkit</p>
        {wheel ? (
          <pre
            tabIndex={0}
            className="m-0 overflow-x-auto rounded-control bg-sunken p-3 font-mono text-sm leading-6 text-ink"
          >
            {`pip install "${wheel}"`}
          </pre>
        ) : (
          <p className="m-0 text-ink-secondary">The README in the download has the command.</p>
        )}
      </div>
      <div className="space-y-1">
        <p className="m-0 font-semibold text-ink">Set, in your own shell</p>
        <dl className="m-0 space-y-1">
          {ENV_VARS.map(([name, what]) => (
            <div key={name} className="flex flex-wrap gap-x-2">
              <dt className="font-mono text-ink">{name}</dt>
              <dd className="m-0 text-ink-secondary">{what}</dd>
            </div>
          ))}
        </dl>
      </div>
      <p className="m-0 flex items-start gap-2 text-ink">
        <KeyRound aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
        <span>
          Your key never leaves your machine: Forgeway never asks for it or stores it.{' '}
          {lexicon.runLocallyGrades}
        </span>
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <a
          href={LIVE_MODE_GUIDE}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex min-h-11 items-center gap-2 text-accent-strong underline underline-offset-2"
        >
          <ExternalLink aria-hidden="true" className="h-4 w-4" />
          <span>
            The live mode guide<span className="sr-only"> (opens in a new tab)</span>
          </span>
        </a>
        <Button variant="quiet" onClick={onClose}>
          Close
        </Button>
      </div>
    </section>
  );
}

/** The link beside the editor to every name the toolkit offers. New tab: the editor stays put. */
export function ToolkitReferenceLink() {
  const lexicon = useLexicon();
  return (
    <a href={TOOLKIT_REFERENCE} target="_blank" rel="noopener noreferrer" className={LINK_BUTTON}>
      <ExternalLink aria-hidden="true" className="h-4 w-4" />
      <span>
        {lexicon.toolkitReference}
        <span className="sr-only"> (opens in a new tab)</span>
      </span>
    </a>
  );
}
