import { Suspense, useEffect, useRef } from 'react';
import type { ReactNode } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { useSession } from '../features/identity/session';

const plannedSections = ['Support', 'Analytics', 'Knowledge', 'Follow-ups'];

function Navigation({ onNavigate }: { onNavigate?: () => void }) {
  const { identity } = useSession();
  return (
    <nav aria-label="Primary navigation">
      <ul className="navigation">
        <li>
          <NavLink to="/app/overview" onClick={onNavigate}>
            Overview
          </NavLink>
        </li>
        {identity?.audience === 'staff' && (
          <li>
            <NavLink to="/app/customers" onClick={onNavigate}>
              Customers
            </NavLink>
          </li>
        )}
        {identity?.role === 'admin' && (
          <li>
            <NavLink to="/app/settings/workspace" onClick={onNavigate}>
              Settings
            </NavLink>
          </li>
        )}
        {plannedSections.map((section) => (
          <li className="planned-link" key={section}>
            <span>{section}</span>
            <span className="metadata">Planned</span>
          </li>
        ))}
      </ul>
    </nav>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { identity } = useSession();
  const location = useLocation();
  const drawer = useRef<HTMLDialogElement>(null);
  const menuButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    document.getElementById('page-heading')?.focus();
  }, [location.pathname]);

  function closeDrawer() {
    drawer.current?.close();
    menuButton.current?.focus();
  }

  useEffect(() => {
    const query = window.matchMedia('(min-width: 1200px)');
    const resize = () => {
      if (query.matches) drawer.current?.close();
    };
    query.addEventListener('change', resize);
    return () => query.removeEventListener('change', resize);
  }, []);

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <header className="app-header">
        <div className="flex items-center gap-3 min-w-0">
          <button
            className="button secondary menu-trigger"
            ref={menuButton}
            onClick={() => drawer.current?.showModal()}
            aria-haspopup="dialog"
            aria-controls="navigation-drawer"
          >
            Menu
          </button>
          <span className="brand">Atlas CX</span>
        </div>
        <div className="header-account">
          {identity ? (
            <>
              <span className="workspace-name">{identity.workspace_name}</span>
              <Link to="/app/account">Account</Link>
            </>
          ) : (
            <Link to="/sign-in">Sign in</Link>
          )}
        </div>
      </header>
      <aside className="sidebar" aria-label="Application navigation">
        <p className="sidebar-label">Customer operations</p>
        <Navigation />
        <p className="sidebar-note">
          {identity ? identity.workspace_name : 'No workspace connected'}
        </p>
      </aside>
      <dialog
        id="navigation-drawer"
        className="navigation-drawer"
        ref={drawer}
        aria-labelledby="navigation-title"
        onCancel={closeDrawer}
        onKeyDown={(event) => {
          if (event.key !== 'Tab') return;
          const controls = event.currentTarget.querySelectorAll<HTMLElement>(
            'a[href], button:not([disabled])',
          );
          const first = controls[0];
          const last = controls[controls.length - 1];
          if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last?.focus();
          } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first?.focus();
          }
        }}
      >
        <div className="flex justify-between items-center gap-3">
          <h2 id="navigation-title">Atlas CX</h2>
          <button className="button secondary" onClick={closeDrawer}>
            Close
          </button>
        </div>
        <p className="small-reading">
          {identity ? identity.workspace_name : 'No workspace connected'}
        </p>
        <Navigation
          onNavigate={() => {
            drawer.current?.close();
            requestAnimationFrame(() =>
              document.getElementById('page-heading')?.focus(),
            );
          }}
        />
      </dialog>
      <main id="main-content" className="main-content" tabIndex={-1}>
        <Suspense fallback={<p role="status">Loading page�</p>}>
          {children}
        </Suspense>
      </main>
    </div>
  );
}
