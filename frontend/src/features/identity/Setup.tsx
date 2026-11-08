import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../api/client';
import { ErrorMessage } from '../../components/Feedback';

export function Setup() {
  const [token, setToken] = useState(() => {
    const value =
      new URLSearchParams(window.location.hash.slice(1)).get('token') ?? '';
    return value;
  });
  useEffect(() => {
    window.history.replaceState(null, '', window.location.pathname);
  }, []);
  const [existing, setExisting] = useState(false);
  const [password, setPassword] = useState('');
  const [pending, setPending] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  return (
    <main className="auth-page">
      <Link to="/">Atlas CX</Link>
      <h1>Set up your access</h1>
      {done ? (
        <>
          <p role="status">Access set up. You can sign in now.</p>
          <Link to="/sign-in">Staff sign-in</Link>
          <Link to="/portal/sign-in">Customer portal sign-in</Link>
        </>
      ) : !token ? (
        <p>
          This setup link isn’t available. Ask your administrator for a new
          link.
        </p>
      ) : (
        <form
          className="work-surface form-surface"
          onSubmit={async (event) => {
            event.preventDefault();
            setPending(true);
            setError(null);
            try {
              await api('/auth/setup', {
                method: 'POST',
                body: {
                  setup_token: token,
                  [existing ? 'current_password' : 'new_password']: password,
                },
              });
              setPassword('');
              setToken('');
              setDone(true);
            } catch (failure) {
              setError(failure as Error);
            } finally {
              setPending(false);
            }
          }}
        >
          <ErrorMessage error={error} />
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={existing}
              onChange={(event) => setExisting(event.target.checked)}
            />
            I already have an Atlas CX account
          </label>
          <p className="small-reading">
            Existing accounts use their current password. New accounts and
            operator-issued recovery links require a new password with at least
            12 characters.
          </p>
          <label htmlFor="setup-password">
            {existing ? 'Current password' : 'New password'}
          </label>
          <input
            id="setup-password"
            type="password"
            autoComplete={existing ? 'current-password' : 'new-password'}
            required
            minLength={existing ? 1 : 12}
            maxLength={128}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <button className="button" disabled={pending}>
            {pending ? 'Setting up…' : 'Set up access'}
          </button>
        </form>
      )}
    </main>
  );
}
