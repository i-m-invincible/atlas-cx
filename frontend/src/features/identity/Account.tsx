import { useState } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { api } from '../../api/client';
import { useSession } from './session';
import { SignOut } from './SignOut';
import { ErrorMessage, Loading } from '../../components/Feedback';

export function Account({
  portal = false,
  embedded = false,
}: {
  portal?: boolean;
  embedded?: boolean;
}) {
  const { identity, loading, setIdentity } = useSession();
  const [error, setError] = useState<Error | null>(null);
  const [pending, setPending] = useState(false);
  if (loading) return <Loading label="Loading your account…" />;
  if (!identity)
    return <Navigate to={portal ? '/portal/sign-in' : '/sign-in'} replace />;
  if (portal && identity.audience !== 'portal')
    return <Navigate to="/app/customers" replace />;
  const Container = embedded || !portal ? 'section' : 'main';
  return (
    <Container className={portal && !embedded ? 'auth-page portal-page' : ''}>
      {portal && !embedded && <Link to="/portal">Atlas CX</Link>}
      <h1 id="page-heading" tabIndex={-1}>
        {portal ? 'Customer portal' : 'Your account'}
      </h1>
      <p>
        {identity.display_name} · {identity.workspace_name}
      </p>
      <p className="small-reading">{identity.email}</p>
      {portal && !embedded && (
        <p>
          Your account is connected to your own requests and public replies.
        </p>
      )}
      <form
        className="work-surface form-surface"
        onSubmit={async (event) => {
          event.preventDefault();
          setPending(true);
          setError(null);
          const form = new FormData(event.currentTarget);
          try {
            await api('/auth/password', {
              method: 'POST',
              body: {
                current_password: form.get('current_password'),
                new_password: form.get('new_password'),
              },
            });
            setIdentity(null);
          } catch (failure) {
            setError(failure as Error);
          } finally {
            setPending(false);
          }
        }}
      >
        <h2>Change password</h2>
        <ErrorMessage error={error} />
        <label htmlFor="current-password">Current password</label>
        <input
          id="current-password"
          name="current_password"
          type="password"
          autoComplete="current-password"
          required
          maxLength={128}
        />
        <label htmlFor="new-password">New password</label>
        <input
          id="new-password"
          name="new_password"
          type="password"
          autoComplete="new-password"
          required
          minLength={12}
          maxLength={128}
          aria-describedby="password-help"
        />
        <p id="password-help" className="small-reading">
          Use at least 12 characters. Changing it signs out every active
          session.
        </p>
        <button className="button" disabled={pending}>
          {pending ? 'Changing password…' : 'Change password'}
        </button>
      </form>
      {!embedded && <SignOut />}
    </Container>
  );
}
