import { Check, Lock } from 'lucide-react';
import { useState } from 'react';

import { errorMessage } from '../../api/errors';
import { useUpdatePathProfile } from '../../api/hooks';
import type { PathProfile, TalentTree } from '../../api/types';
import { Button } from '../../components/Button';
import { useFlavour } from '../../theme/flavour';
import { useLexicon } from '../../theme/useTheme';
import { usePathName } from '../../theme/usePathName';

interface PathChoiceProps {
  profile: PathProfile;
  tree: TalentTree;
}

/**
 * Choose a path (RPG: a class). Changing it refunds the talents in the old path's subtree, so
 * when there are any a confirm step names them first, and afterwards the refunded talents are
 * listed. The titles are read from the tree as it was, because the refreshed tree no longer has
 * the dropped nodes.
 */
export function PathChoice({ profile, tree }: PathChoiceProps) {
  const lexicon = useLexicon();
  const flavour = useFlavour();
  const pathName = usePathName();
  const update = useUpdatePathProfile();
  const [confirming, setConfirming] = useState<string | null>(null);
  const [refunded, setRefunded] = useState<string[] | null>(null);

  const titles = new Map(tree.nodes.map((node) => [node.id, node.title]));
  const atRisk = tree.nodes.filter(
    (node) => node.state === 'allocated' && node.subtree === profile.path,
  );

  const choose = (pathId: string) => {
    setConfirming(null);
    setRefunded(null);
    update.mutate(
      { path: pathId },
      {
        onSuccess: (updated) => {
          setRefunded(updated.dropped_talents.map((id) => titles.get(id) ?? id));
        },
      },
    );
  };

  const confirmingOption = profile.paths.find((option) => option.id === confirming);

  return (
    <div className="space-y-4">
      <p className="m-0 max-w-measure text-sm text-ink-secondary">{lexicon.pathChangeWarning}</p>
      <ul className="m-0 list-none border-t border-line-subtle p-0">
        {profile.paths.map((option) => {
          const current = option.id === profile.path;
          const reasonId = `path-reason-${option.id}`;
          const epithet = flavour.path(option.id)?.epithet;
          return (
            <li
              key={option.id}
              aria-current={current || undefined}
              className="grid gap-x-6 gap-y-2 border-b border-line-subtle py-4 sm:grid-cols-[minmax(0,1fr)_10rem] sm:items-center"
            >
              <div className="min-w-0 space-y-1">
                <h3 className="m-0 text-lg">{pathName(option.id, option.title)}</h3>
                {epithet !== undefined && (
                  <p className="m-0 text-sm italic text-ink-muted">{epithet}</p>
                )}
                <p className="m-0 max-w-measure text-sm text-ink-secondary">{option.summary}</p>
                {!option.selectable && option.reason !== null && (
                  <p
                    id={reasonId}
                    className="m-0 inline-flex items-center gap-1.5 text-sm text-ink"
                  >
                    <Lock aria-hidden="true" className="h-4 w-4 shrink-0 text-ink-muted" />
                    {option.requires.length > 0
                      ? lexicon.pathLocked(
                          option.requires.map((b) => flavour.zone(b.id)?.name ?? b.title),
                        )
                      : option.reason}
                  </p>
                )}
              </div>
              {current ? (
                <p className="m-0 inline-flex min-h-11 items-center gap-1.5 text-accent sm:justify-self-end">
                  <Check aria-hidden="true" className="h-4 w-4" />
                  <span className="label-caps">{lexicon.pathCurrent}</span>
                </p>
              ) : (
                <Button
                  variant="secondary"
                  className="justify-self-start sm:w-full"
                  disabled={!option.selectable}
                  loading={update.isPending && update.variables.path === option.id}
                  aria-label={`${lexicon.pathChoose}: ${pathName(option.id, option.title)}`}
                  aria-describedby={option.selectable ? undefined : reasonId}
                  onClick={() => {
                    if (atRisk.length > 0) setConfirming(option.id);
                    else choose(option.id);
                  }}
                >
                  {lexicon.pathChoose}
                </Button>
              )}
            </li>
          );
        })}
      </ul>
      {confirmingOption !== undefined && (
        <div
          role="group"
          aria-label={`Confirm ${lexicon.specialisation} change`}
          className="space-y-3 rounded-control border border-warning bg-warning-soft p-3"
        >
          <p className="m-0 text-sm text-ink">
            {lexicon.pathConfirm(
              pathName(confirmingOption.id, confirmingOption.title),
              atRisk.map((node) => node.title),
            )}
          </p>
          <div className="flex flex-wrap gap-2">
            <Button
              onClick={() => {
                choose(confirmingOption.id);
              }}
            >
              Change anyway
            </Button>
            <Button
              variant="quiet"
              onClick={() => {
                setConfirming(null);
              }}
            >
              Keep {pathName(profile.path)}
            </Button>
          </div>
        </div>
      )}
      {update.isError && (
        <p
          role="alert"
          className="m-0 rounded-control bg-danger-soft px-3 py-2 text-sm text-danger"
        >
          {errorMessage(update.error)}
        </p>
      )}
      {refunded !== null && refunded.length > 0 && (
        <p role="status" className="m-0 text-sm text-ink">
          {lexicon.pathDropped(refunded)}
        </p>
      )}
    </div>
  );
}
