import { Link } from '@tanstack/react-router';
import { useState, type FormEvent } from 'react';

import { ApiError, errorMessage } from '../../api/errors';
import { useConfirmPasswordReset, usePasswordResetCheck } from '../../api/hooks';
import { Button } from '../../components/Button';
import { PageHeader } from '../../theme/slots';
import { useLexicon } from '../../theme/useTheme';
import { FIELD, LINK, PASSWORD_MIN_LENGTH } from './fields';

/** A 422 from the API on a reset link means the link itself no longer works. */
const isDeadLink = (error: unknown) => error instanceof ApiError && error.status === 422;

/**
 * The target of the emailed reset link: /reset-password?token=… The link is checked as the page
 * opens, so a dead one says so before a new password is typed.
 */
export function ResetPasswordPage({ token }: { token: string | undefined }) {
  const lexicon = useLexicon();
  const check = usePasswordResetCheck(token);
  const reset = useConfirmPasswordReset();
  const [password, setPassword] = useState('');
  const deadLink = isDeadLink(check.error) || isDeadLink(reset.error);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (token !== undefined) reset.mutate({ token, password });
  };

  return (
    <div className="mx-auto max-w-md space-y-8 px-4 py-12 sm:px-6">
      <PageHeader title={lexicon.resetPasswordTitle} />
      {reset.isSuccess ? (
        <div className="space-y-4">
          <p role="status" className="m-0">
            {lexicon.resetPasswordDone}
          </p>
          <Link to="/sign-in" className={LINK}>
            {lexicon.signIn}
          </Link>
        </div>
      ) : token === undefined ? (
        <p role="alert" className="m-0 text-danger">
          This link is incomplete. Open the whole link from the email, or{' '}
          <Link to="/forgot-password" className={LINK}>
            ask for a new one
          </Link>
          .
        </p>
      ) : deadLink ? (
        <p role="alert" className="m-0 text-danger">
          {lexicon.resetLinkInvalid}{' '}
          <Link to="/forgot-password" className={LINK}>
            {lexicon.resetLinkRequest}
          </Link>
          .
        </p>
      ) : (
        <form onSubmit={submit} className="space-y-5">
          <div className="space-y-1">
            <label htmlFor="new-password" className="block text-sm font-medium">
              {lexicon.newPasswordLabel}
            </label>
            <input
              id="new-password"
              type="password"
              className={FIELD}
              autoComplete="new-password"
              required
              minLength={PASSWORD_MIN_LENGTH}
              aria-describedby="new-password-hint"
              value={password}
              onChange={(event) => {
                setPassword(event.target.value);
              }}
            />
            <p id="new-password-hint" className="m-0 text-sm text-ink-muted">
              At least {PASSWORD_MIN_LENGTH} characters. Every signed-in session ends when it
              changes.
            </p>
          </div>
          {reset.isError && (
            <p
              role="alert"
              className="m-0 rounded-control bg-danger-soft px-3 py-2 text-sm text-danger"
            >
              {errorMessage(reset.error)}
            </p>
          )}
          <Button type="submit" loading={reset.isPending} className="w-full">
            {lexicon.resetPasswordAction}
          </Button>
        </form>
      )}
    </div>
  );
}
