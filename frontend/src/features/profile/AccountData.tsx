import { Link, useNavigate } from '@tanstack/react-router';
import { Download, Trash2 } from 'lucide-react';
import { useEffect, useRef, useState, type FormEvent } from 'react';

import { errorMessage } from '../../api/errors';
import { useDeleteAccount, useExportAccount } from '../../api/hooks';
import { Button } from '../../components/Button';
import { useLexicon } from '../../theme/useTheme';
import { FIELD, LINK } from '../auth/fields';

const ALERT = 'm-0 rounded-control bg-danger-soft px-3 py-2 text-sm text-danger';

/**
 * Your data: download everything held about the account as JSON, or delete the account. Deleting
 * takes a second step, with the current password, and cannot be undone.
 */
export function AccountData() {
  const copy = useLexicon().accountData;
  const exportAccount = useExportAccount();
  const deleteAccount = useDeleteAccount();
  const navigate = useNavigate();
  const [confirming, setConfirming] = useState(false);
  const [password, setPassword] = useState('');
  const passwordField = useRef<HTMLInputElement>(null);

  // The second step takes focus, so a keyboard user lands on the field it asks for.
  useEffect(() => {
    if (confirming) passwordField.current?.focus();
  }, [confirming]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    deleteAccount.mutate(password, {
      onSuccess: () => {
        void navigate({ to: '/sign-in' });
      },
    });
  };

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <h3 className="m-0 text-base font-semibold">{copy.exportHeading}</h3>
        <p className="m-0 max-w-measure text-sm text-ink-secondary">
          {copy.exportBodyBefore}{' '}
          <Link to="/privacy" className={LINK}>
            {copy.exportPolicyLink}
          </Link>{' '}
          {copy.exportBodyAfter}
        </p>
        <Button
          variant="secondary"
          loading={exportAccount.isPending}
          onClick={() => {
            exportAccount.mutate();
          }}
        >
          <Download aria-hidden="true" className="h-4 w-4" />
          {copy.exportAction}
        </Button>
        {exportAccount.isError && (
          <p role="alert" className={ALERT}>
            {errorMessage(exportAccount.error)}
          </p>
        )}
      </div>

      <div className="space-y-3">
        <h3 className="m-0 text-base font-semibold">{copy.deleteHeading}</h3>
        <p className="m-0 max-w-measure text-sm text-ink-secondary">{copy.deleteBody}</p>
        {confirming ? (
          <form onSubmit={submit} className="max-w-sm space-y-4" aria-label={copy.deleteHeading}>
            <div className="space-y-1">
              <label htmlFor="delete-password" className="block text-sm font-medium">
                {copy.deletePasswordLabel}
              </label>
              <input
                ref={passwordField}
                id="delete-password"
                type="password"
                className={FIELD}
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => {
                  setPassword(event.target.value);
                }}
              />
            </div>
            <div className="flex flex-wrap gap-3">
              <Button
                type="submit"
                variant="secondary"
                className="border-danger text-danger"
                disabled={password === ''}
                loading={deleteAccount.isPending}
              >
                <Trash2 aria-hidden="true" className="h-4 w-4" />
                {copy.deleteConfirm}
              </Button>
              <Button
                variant="quiet"
                onClick={() => {
                  setConfirming(false);
                  setPassword('');
                  deleteAccount.reset();
                }}
              >
                {copy.deleteKeep}
              </Button>
            </div>
            {deleteAccount.isError && (
              <p role="alert" className={ALERT}>
                {errorMessage(deleteAccount.error)}
              </p>
            )}
          </form>
        ) : (
          <Button
            variant="secondary"
            className="border-danger text-danger"
            onClick={() => {
              setConfirming(true);
            }}
          >
            <Trash2 aria-hidden="true" className="h-4 w-4" />
            {copy.deleteStart}
          </Button>
        )}
      </div>
    </div>
  );
}
