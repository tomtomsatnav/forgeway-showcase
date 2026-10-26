import { Link } from '@tanstack/react-router';
import { Copy, ExternalLink, Plus, Share2 } from 'lucide-react';
import { useEffect, useRef, useState, type FormEvent } from 'react';

import { errorMessage } from '../../api/errors';
import { useMe, useUpdateCertificate } from '../../api/hooks';
import { useProblemMessage } from '../../api/useProblemMessage';
import type { Certificate } from '../../api/types';
import { Button } from '../../components/Button';
import { ProMark } from '../../components/ProMark';
import { Toggle } from '../../components/Toggle';
import { useLexicon } from '../../theme/useTheme';
import { addToProfileUrl, shareUrl } from './linkedin';

const NAME_MAX = 60;

const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });

/** Why a recipient name cannot be saved, or null when it can. */
export function nameProblem(value: string): string | null {
  const length = value.trim().length;
  if (length === 0) return 'Enter the name to show on the certificate.';
  if (length > NAME_MAX) return `Use ${NAME_MAX} characters or fewer.`;
  return null;
}

const FIELD =
  'block min-h-11 w-full max-w-sm rounded-control border border-line-strong bg-sunken px-3 text-base text-ink';
const LINK_BUTTON =
  'inline-flex min-h-11 items-center justify-center gap-2 rounded-control border border-line-strong bg-transparent px-4 font-ui text-base font-medium text-ink transition-colors duration-fast hover:bg-sunken';
const ALERT = 'm-0 rounded-control bg-danger-soft px-3 py-2 text-sm text-danger';

/** The name on the certificate, edited in place and saved with PATCH. */
function RecipientName({ certificate }: { certificate: Certificate }) {
  const update = useUpdateCertificate();
  const [value, setValue] = useState(certificate.recipient_name);
  const [saved, setSaved] = useState(false);

  const problem = nameProblem(value);
  const unchanged = value.trim() === certificate.recipient_name;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (problem !== null || unchanged) return;
    update.mutate(
      { id: certificate.id, recipient_name: value.trim() },
      {
        onSuccess: (updated) => {
          setValue(updated.recipient_name);
          setSaved(true);
        },
      },
    );
  };

  const fieldId = `recipient-${certificate.id}`;
  return (
    <form onSubmit={submit} className="space-y-2">
      <label htmlFor={fieldId} className="block text-sm font-medium">
        Name on the certificate
      </label>
      <div className="flex flex-wrap items-start gap-2">
        <input
          id={fieldId}
          className={FIELD}
          autoComplete="name"
          aria-invalid={problem !== null || undefined}
          aria-describedby={`${fieldId}-hint`}
          value={value}
          onChange={(event) => {
            setValue(event.target.value);
            setSaved(false);
          }}
        />
        <Button
          type="submit"
          variant="secondary"
          disabled={problem !== null || unchanged}
          loading={update.isPending}
        >
          Save name
        </Button>
      </div>
      <p
        id={`${fieldId}-hint`}
        className={`m-0 text-sm ${problem !== null ? 'text-danger' : 'text-ink-muted'}`}
      >
        {problem ?? `1 to ${NAME_MAX} characters. This is the name anyone viewing it sees.`}
      </p>
      <p role="status" className="m-0 text-sm text-success empty:hidden">
        {saved ? 'Name saved.' : ''}
      </p>
      {update.isError && update.variables.recipient_name !== undefined && (
        <p role="alert" className={ALERT}>
          {errorMessage(update.error)}
        </p>
      )}
    </form>
  );
}

/**
 * Publishing is part of Pro. True for a learner known to be on the free plan whose certificate is
 * private, so the limit is shown before they reach it rather than as an error after.
 */
function useNeedsPro(certificate: Certificate): boolean {
  const me = useMe();
  return me.data?.plan === 'free' && !certificate.is_public;
}

/** Publishing also needs a verified email; only a known-unverified learner is held back. */
function useNeedsVerified(certificate: Certificate): boolean {
  const me = useMe();
  return me.data?.email_verified === false && !certificate.is_public;
}

/** Private or public, with what each means; making it public is the only way to share it. */
function Visibility({ certificate }: { certificate: Certificate }) {
  const lexicon = useLexicon();
  const needsPro = useNeedsPro(certificate);
  const needsVerified = useNeedsVerified(certificate);
  const problemMessage = useProblemMessage();
  const update = useUpdateCertificate();
  const reasons = [
    ...(needsVerified ? [`${certificate.id}-verify`] : []),
    ...(needsPro ? [`${certificate.id}-pro`] : []),
  ];
  // The control follows the click at once and settles back if the request fails.
  const [choice, setChoice] = useState<boolean | null>(null);
  const isPublic = choice ?? certificate.is_public;
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-3">
        <Toggle
          legend={`Visibility of the ${certificate.branch_title} certificate`}
          value={isPublic ? 'public' : 'private'}
          options={[
            { value: 'private', label: 'Private' },
            {
              value: 'public',
              label: 'Public',
              disabled: reasons.length > 0,
              describedBy: reasons.length > 0 ? reasons.join(' ') : undefined,
            },
          ]}
          onChange={(next) => {
            setChoice(next === 'public');
            update.mutate(
              { id: certificate.id, is_public: next === 'public' },
              {
                onSettled: () => {
                  setChoice(null);
                },
              },
            );
          }}
        />
        {needsPro && <ProMark />}
      </div>
      {needsVerified && (
        <p id={`${certificate.id}-verify`} className="m-0 max-w-measure text-sm text-ink">
          {lexicon.certificatePublishUnverified}
        </p>
      )}
      {needsPro && (
        <p id={`${certificate.id}-pro`} className="m-0 max-w-measure text-sm text-ink">
          {lexicon.certificatePublishPro}{' '}
          <Link to="/pro" className="text-accent-strong underline underline-offset-2">
            {lexicon.proJoin}
          </Link>
        </p>
      )}
      <p className="m-0 max-w-measure text-sm text-ink-secondary">
        {certificate.is_public
          ? 'Anyone with the link can see the verification page: your name, the track, the date and the credential ID. Make it private to take it down; copies others have cached can linger for a few minutes.'
          : 'Only you can see this. Sharing it makes a verification page public: anyone with the link can see your name, the track, the date and the credential ID.'}
      </p>
      {update.isError && update.variables.is_public !== undefined && (
        <p role="alert" className={ALERT}>
          {problemMessage(update.error)}
        </p>
      )}
    </div>
  );
}

/** Copies the public link, confirming politely; when the browser refuses, selects it to copy by hand. */
function CopyLink({ url }: { url: string }) {
  const [state, setState] = useState<'idle' | 'copied' | 'blocked'>('idle');
  const field = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (state === 'blocked') {
      field.current?.focus();
      field.current?.select();
    }
    if (state !== 'copied') return;
    const timer = setTimeout(() => {
      setState('idle');
    }, 4000);
    return () => {
      clearTimeout(timer);
    };
  }, [state]);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setState('copied');
    } catch {
      setState('blocked');
    }
  };

  return (
    <div className="space-y-2">
      <Button variant="secondary" onClick={() => void copy()}>
        <Copy aria-hidden="true" className="h-4 w-4" />
        Copy link
      </Button>
      {state === 'blocked' && (
        <input
          ref={field}
          readOnly
          value={url}
          aria-label="Certificate link"
          className={`${FIELD} max-w-md font-mono text-sm`}
          onFocus={(event) => {
            event.target.select();
          }}
        />
      )}
      <p role="status" className="m-0 text-sm text-success empty:hidden">
        {state === 'copied' && 'Link copied.'}
        {state === 'blocked' &&
          'Your browser blocked copying. The link is selected: copy it with your keyboard.'}
      </p>
    </div>
  );
}

const NEW_TAB = <span className="sr-only"> (opens in a new tab)</span>;

/** Actions that need a public certificate; a private one explains how to unlock them. */
function Actions({ certificate }: { certificate: Certificate }) {
  const lexicon = useLexicon();
  const needsPro = useNeedsPro(certificate);
  if (!certificate.is_public) {
    return (
      <p className="m-0 max-w-measure text-sm text-ink-secondary">
        {needsPro
          ? lexicon.certificateActionsPro
          : 'Make this certificate public to view it, copy its link, add it to LinkedIn or share it.'}
      </p>
    );
  }
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <a href={`/c/${certificate.id}`} target="_blank" rel="noopener" className={LINK_BUTTON}>
          <ExternalLink aria-hidden="true" className="h-4 w-4" />
          <span>View certificate{NEW_TAB}</span>
        </a>
        <a
          href={addToProfileUrl(certificate.linkedin)}
          target="_blank"
          rel="noopener noreferrer"
          className={LINK_BUTTON}
        >
          <Plus aria-hidden="true" className="h-4 w-4" />
          <span>Add to LinkedIn profile{NEW_TAB}</span>
        </a>
        <a
          href={shareUrl(certificate.public_url)}
          target="_blank"
          rel="noopener noreferrer"
          className={LINK_BUTTON}
        >
          <Share2 aria-hidden="true" className="h-4 w-4" />
          <span>Share on LinkedIn{NEW_TAB}</span>
        </a>
      </div>
      <CopyLink url={certificate.public_url} />
    </div>
  );
}

function CertificateCard({ certificate }: { certificate: Certificate }) {
  const lexicon = useLexicon();
  return (
    <li className="space-y-4 rounded-panel border border-line-strong bg-raised p-4 sm:p-6">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,20rem)]">
        <div className="space-y-4">
          <h3 className="m-0 text-lg">{certificate.branch_title}</h3>
          <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
            <dt className="text-ink-secondary">Issued</dt>
            <dd className="m-0">{formatDate(certificate.issued_at)}</dd>
            <dt className="text-ink-secondary">Exercises</dt>
            <dd className="tabular m-0">
              {certificate.exercise_count}
              {certificate.includes_capstone && `, ${lexicon.certificateIncludesCapstone}`}
            </dd>
            <dt className="text-ink-secondary">Credential ID</dt>
            <dd className="m-0 break-all font-mono">{certificate.id}</dd>
          </dl>
          <RecipientName certificate={certificate} />
          <Visibility certificate={certificate} />
          <Actions certificate={certificate} />
        </div>
        {certificate.is_public && (
          <img
            src={`/c/${certificate.id}.png`}
            width={1200}
            height={627}
            loading="lazy"
            alt={`Certificate of completion for the ${certificate.branch_title} track, awarded to ${certificate.recipient_name}`}
            className="h-auto w-full self-start rounded-control border border-line-subtle"
          />
        )}
      </div>
    </li>
  );
}

/** The learner's certificates, newest first, or what earns the first one. */
export function Certificates({ certificates }: { certificates: readonly Certificate[] }) {
  const lexicon = useLexicon();
  if (certificates.length === 0) {
    return <p className="m-0 text-ink-secondary">{lexicon.certificatesNone}</p>;
  }
  return (
    <ul className="m-0 list-none space-y-4 p-0">
      {certificates.map((certificate) => (
        <CertificateCard key={certificate.id} certificate={certificate} />
      ))}
    </ul>
  );
}
