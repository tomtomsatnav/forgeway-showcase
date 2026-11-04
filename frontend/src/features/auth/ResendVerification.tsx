import { errorMessage } from '../../api/errors';
import { useResendVerification } from '../../api/hooks';
import { Button } from '../../components/Button';
import { useLexicon } from '../../theme/useTheme';

/** Ask for a fresh verification link; the outcome is announced politely. */
export function ResendVerification({ variant = 'secondary' }: { variant?: 'secondary' | 'quiet' }) {
  const lexicon = useLexicon();
  const resend = useResendVerification();
  return (
    <div className="space-y-2">
      <Button
        variant={variant}
        loading={resend.isPending}
        onClick={() => {
          resend.mutate();
        }}
      >
        {lexicon.resendVerification}
      </Button>
      <p aria-live="polite" className="m-0 text-sm">
        {resend.isSuccess &&
          lexicon.verificationResent(resend.data.pending_email ?? resend.data.email)}
        {resend.isError && <span className="text-danger">{errorMessage(resend.error)}</span>}
      </p>
    </div>
  );
}
