import { Link, useNavigate } from '@tanstack/react-router';
import { useState, type FormEvent } from 'react';

import { useLogin, usePublicConfig, useRegister } from '../../api/hooks';
import { useProblemMessage } from '../../api/useProblemMessage';
import { Button } from '../../components/Button';
import { PageHeader } from '../../theme/slots';
import { useTheme } from '../../theme/useTheme';
import { CheckInbox } from './CheckInbox';
import { FIELD, LINK, PASSWORD_MIN_LENGTH } from './fields';
import { Turnstile } from './Turnstile';

export function AuthPage({ kind }: { kind: 'sign-in' | 'register' }) {
  const { lexicon, mode, scheme } = useTheme();
  const navigate = useNavigate();
  const login = useLogin();
  const register = useRegister();
  const config = usePublicConfig();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  // A new key remounts the widget: a Turnstile token works once, so a failed register needs another.
  const [widgetKey, setWidgetKey] = useState(0);
  const problemMessage = useProblemMessage();
  const registering = kind === 'register';
  const mutation = registering ? register : login;
  const siteKey = registering ? (config.data?.turnstile_site_key ?? null) : null;
  const awaitingToken = siteKey !== null && turnstileToken === null;

  if (registering && register.isSuccess) {
    return <CheckInbox email={register.data.email} />;
  }

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (registering) {
      // The browser's zone, so streak days start and end where the learner is.
      const time_zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
      register.mutate(
        {
          email,
          password,
          display_name: displayName,
          time_zone,
          // The mode and scheme chosen as a guest carry over to the new profile.
          mode,
          colour_scheme: scheme,
          ...(turnstileToken === null ? {} : { turnstile_token: turnstileToken }),
        },
        {
          onError: () => {
            setTurnstileToken(null);
            setWidgetKey((key) => key + 1);
          },
        },
      );
    } else {
      login.mutate(
        { email, password },
        {
          onSuccess: () => {
            void navigate({ to: '/' });
          },
        },
      );
    }
  };

  return (
    <div className="mx-auto max-w-md space-y-8 px-4 py-12 sm:px-6">
      <PageHeader
        title={registering ? lexicon.register : lexicon.signIn}
        summary={lexicon.authSummary}
      />
      <form onSubmit={submit} className="space-y-5">
        {registering && (
          <div className="space-y-1">
            <label htmlFor="display-name" className="block text-sm font-medium">
              Display name
            </label>
            <input
              id="display-name"
              className={FIELD}
              autoComplete="nickname"
              required
              value={displayName}
              onChange={(event) => {
                setDisplayName(event.target.value);
              }}
            />
          </div>
        )}
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
        <div className="space-y-1">
          <label htmlFor="password" className="block text-sm font-medium">
            {lexicon.passwordLabel}
          </label>
          <input
            id="password"
            type="password"
            className={FIELD}
            autoComplete={registering ? 'new-password' : 'current-password'}
            required
            minLength={registering ? PASSWORD_MIN_LENGTH : undefined}
            aria-describedby={registering ? 'password-hint' : undefined}
            value={password}
            onChange={(event) => {
              setPassword(event.target.value);
            }}
          />
          {registering && (
            <p id="password-hint" className="m-0 text-sm text-ink-muted">
              At least {PASSWORD_MIN_LENGTH} characters.
            </p>
          )}
        </div>
        {siteKey !== null && (
          <Turnstile key={widgetKey} siteKey={siteKey} onToken={setTurnstileToken} />
        )}
        {mutation.isError && (
          <p
            role="alert"
            className="m-0 rounded-control bg-danger-soft px-3 py-2 text-sm text-danger"
          >
            {problemMessage(mutation.error)}
          </p>
        )}
        {registering && (
          <p className="m-0 text-sm text-ink-secondary">
            By creating an account you agree to the{' '}
            <Link to="/terms" className={LINK}>
              terms
            </Link>{' '}
            and the{' '}
            <Link to="/privacy" className={LINK}>
              privacy policy
            </Link>
            .
          </p>
        )}
        <Button
          type="submit"
          loading={mutation.isPending}
          disabled={awaitingToken}
          aria-describedby={awaitingToken ? 'turnstile-pending' : undefined}
          className="w-full"
        >
          {registering ? lexicon.register : lexicon.signIn}
        </Button>
        {awaitingToken && (
          <p id="turnstile-pending" className="m-0 text-sm text-ink-muted">
            {lexicon.humanCheckPending}
          </p>
        )}
      </form>
      {!registering && (
        <p className="m-0 text-center text-sm">
          <Link to="/forgot-password" className="text-accent-strong underline underline-offset-2">
            {lexicon.forgotPassword}
          </Link>
        </p>
      )}
      <p className="m-0 text-center text-sm text-ink-secondary">
        {registering ? 'Already have an account? ' : 'New here? '}
        <Link
          to={registering ? '/sign-in' : '/register'}
          className="text-accent-strong underline underline-offset-2"
        >
          {registering ? lexicon.signIn : lexicon.register}
        </Link>
      </p>
    </div>
  );
}
