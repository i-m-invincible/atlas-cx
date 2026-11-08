import { useState } from 'react';
import { api } from '../../api/client';
import { useSession } from './session';
import { ErrorMessage } from '../../components/Feedback';

export function SignOut() {
  const { setIdentity } = useSession();
  const [error, setError] = useState<Error | null>(null);
  const [pending, setPending] = useState(false);
  return (
    <>
      <button
        className="button secondary"
        disabled={pending}
        onClick={async () => {
          setPending(true);
          setError(null);
          try {
            await api('/auth/logout', { method: 'POST' });
            setIdentity(null);
          } catch (failure) {
            setError(failure as Error);
          } finally {
            setPending(false);
          }
        }}
      >
        {pending ? 'Signing out…' : 'Sign out'}
      </button>
      <ErrorMessage error={error} />
    </>
  );
}
