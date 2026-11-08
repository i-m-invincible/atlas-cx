import { createContext, useContext } from 'react';
import type { Identity } from '../../api/client';

export const SessionContext = createContext<{
  identity: Identity | null;
  loading: boolean;
  error: Error | null;
  setIdentity: (identity: Identity | null) => void;
  refreshIdentity: () => Promise<void>;
}>({
  identity: null,
  loading: true,
  error: null,
  setIdentity: () => {},
  refreshIdentity: async () => {},
});

export function useSession() {
  return useContext(SessionContext);
}
