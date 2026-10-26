import { Link } from '@tanstack/react-router';
import { useState, type FormEvent } from 'react';

import { errorMessage } from '../../api/errors';
import { useRequestPasswordReset } from '../../api/hooks';
import { Button } from '../../components/Button';
import { PageHeader } from '../../theme/slots';
import { useLexicon } from '../../theme/useTheme';
import { FIELD, LINK } from './fields';

/** Ask for a reset link. The answer never says whether the address has an account. */
export function ForgotPasswordPage() {
  const lexicon = useLexicon();
  const request = useRequestPasswordReset();
  const [email, setEmail] = useState('');

  const submit = (event: FormEvent) => {
    event.preventDefault();
    request.mutate(email);
  };

  return (
    <div className="mx-auto max-w-md space-y-8 px-4 py-12 sm:px-6">
      <PageHeader
        title={lexicon.forgotPasswordTitle}
        summary="Enter the email address you signed up with and we will send you a link."
      />
      {request.isSuccess ? (
        <p role="status" className="m-0">
          {lexicon.forgotPasswordSent}
        </p>
      ) : (
        <form onSubmit={submit} className="space-y-5">
          <div className="space-y-1">
            <label htmlFor="email" className="block text-sm font-medium">
              Email
            </label>
            <input
              id="email"
              type="email"
              className={FIELD}
              autoComplete="email"
              required
              value={email}
              onChange={(event) => {
                setEmail(event.target.value);
              }}
            />
          </div>
          {request.isError && (
            <p
              role="alert"
              className="m-0 rounded-control bg-danger-soft px-3 py-2 text-sm text-danger"
            >
              {errorMessage(request.error)}
            </p>
          )}
          <Button type="submit" loading={request.isPending} className="w-full">
            {lexicon.forgotPasswordAction}
          </Button>
        </form>
      )}
      <p className="m-0 text-center text-sm">
        <Link to="/sign-in" className={LINK}>
          {lexicon.signIn}
        </Link>
      </p>
    </div>
  );
}
