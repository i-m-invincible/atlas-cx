import type { ReactNode } from 'react';
import { Link, Navigate, NavLink, useLocation } from 'react-router-dom';
import { useEffect } from 'react';
import { useSession } from '../identity/session';
import { SignOut } from '../identity/SignOut';
import { ErrorMessage, Loading } from '../../components/Feedback';

export function PortalShell({ children }: { children: ReactNode }) {
  const { identity, loading, error } = useSession();
  const location = useLocation();
  useEffect(() => {
    document.getElementById('page-heading')?.focus();
  }, [location.pathname]);
  if (loading) return <Loading label="Loading your requests..." />;
  if (error) return <ErrorMessage error={error} />;
  if (!identity) return <Navigate to="/portal/sign-in" replace />;
  if (identity.audience !== 'portal')
    return <Navigate to="/app/support/inbox" replace />;
  return (
    <div className="portal-shell">
      <a className="skip-link" href="#portal-content">
        Skip to requests
      </a>
      <header className="portal-header">
        <Link className="brand" to="/portal">
          Atlas CX
        </Link>
        <nav aria-label="Portal navigation">
          <NavLink to="/portal" end>
            Requests
          </NavLink>
          <NavLink to="/portal/new">New request</NavLink>
          <NavLink to="/portal/profile">Profile</NavLink>
        </nav>
        <SignOut />
      </header>
      <main id="portal-content" className="portal-content">
        <p className="small-reading">{identity.workspace_name}</p>
        {identity.capabilities.demo && (
          <p className="demo-banner">
            Demo workspace. Use fictional information.
          </p>
        )}
        {children}
      </main>
    </div>
  );
}
