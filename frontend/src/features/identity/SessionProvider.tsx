import { useCallback, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Navigate } from 'react-router-dom';
import { api, ApiError } from '../../api/client';
import type { Identity } from '../../api/client';
import { SessionContext, useSession } from './session';

export function SessionProvider({ children }: { children: ReactNode }) {
  const client = useQueryClient();
  const [identity, storeIdentity] = useState<Identity | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const previousScope = useRef<string | null>(null);
  const bootstrap = useRef<AbortController | null>(null);
  const setIdentity = useCallback(
    (next: Identity | null) => {
      bootstrap.current?.abort();
      const key = next
        ? [
            next.user_id,
            next.workspace_id,
            next.audience,
            next.role,
            next.contact_id,
          ].join(':')
        : null;
      if (key !== previousScope.current || next === null) client.clear();
      previousScope.current = key;
      storeIdentity(next);
      setLoading(false);
      setError(null);
    },
    [client],
  );
  const refreshIdentity = useCallback(async () => {
    try {
      setIdentity((await api<Identity>('/auth/me')).data);
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 401)
        setIdentity(null);
      else throw failure;
    }
  }, [setIdentity]);
  useEffect(() => {
    const controller = new AbortController();
    bootstrap.current = controller;
    api<Identity>('/auth/me', { signal: controller.signal })
      .then((response) => {
        if (!controller.signal.aborted) setIdentity(response.data);
      })
      .catch((failure: Error) => {
        if (controller.signal.aborted) return;
        if (failure instanceof ApiError && failure.status === 401)
          setIdentity(null);
        else {
          setError(failure);
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [setIdentity]);
  useEffect(() => {
    const expired = () => setIdentity(null);
    window.addEventListener('atlas:session-expired', expired);
    return () => window.removeEventListener('atlas:session-expired', expired);
  }, [setIdentity]);
  return (
    <SessionContext.Provider
      value={{ identity, loading, error, setIdentity, refreshIdentity }}
    >
      {children}
    </SessionContext.Provider>
  );
}

export function RequireStaff({ children }: { children: ReactNode }) {
  const { identity, loading, error } = useSession();
  if (loading) return <p role="status">Loading your workspace…</p>;
  if (error)
    return (
      <p role="alert">
        We couldn’t load your session. Reload this page to try again.
      </p>
    );
  if (!identity) return <Navigate to="/sign-in" replace />;
  if (identity.audience !== 'staff') return <Navigate to="/portal" replace />;
  return children;
}
