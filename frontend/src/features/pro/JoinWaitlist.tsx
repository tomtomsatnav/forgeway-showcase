import { Check } from 'lucide-react';

import { errorMessage } from '../../api/errors';
import { useJoinWaitlist, useMe, useWaitlist } from '../../api/hooks';
import { Button } from '../../components/Button';
import { useLexicon } from '../../theme/useTheme';

/**
 * The join button, or "you are on the waitlist" once joined. Joining twice is harmless. Nothing
 * at all for a learner whose plan already includes Pro.
 */
export function JoinWaitlist() {
  const lexicon = useLexicon();
  const me = useMe();
  const waitlist = useWaitlist();
  const join = useJoinWaitlist();
  const joined = waitlist.data?.joined === true;
  if (me.data != null && me.data.plan !== 'free') return null;

  return (
    <div className="space-y-2">
      <div role="status" className="min-h-0">
        {joined && (
          <p className="m-0 inline-flex items-center gap-2 font-medium text-success">
            <Check aria-hidden="true" className="h-4 w-4" />
            {lexicon.proJoined}
          </p>
        )}
      </div>
      {!joined && (
        <Button
          loading={join.isPending}
          disabled={waitlist.isPending}
          onClick={() => {
            join.mutate();
          }}
        >
          {lexicon.proJoin}
        </Button>
      )}
      {join.isError && (
        <p role="alert" className="m-0 text-sm text-danger">
          {errorMessage(join.error)}
        </p>
      )}
    </div>
  );
}
