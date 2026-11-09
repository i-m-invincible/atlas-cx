import { Suspense, lazy } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Overview } from '../features/overview/Overview';
import { RequireStaff } from '../features/identity/SessionProvider';
import { PortalShell } from '../features/portal/PortalShell';
const Support = lazy(() =>
  import('../features/support/Support').then((module) => ({
    default: module.Support,
  })),
);
const CreateCase = lazy(() =>
  import('../features/support/CreateCase').then((module) => ({
    default: module.CreateCase,
  })),
);
const CaseAssignment = lazy(() =>
  import('../features/support/CaseAssignment').then((module) => ({
    default: module.CaseAssignment,
  })),
);
const Requests = lazy(() =>
  import('../features/portal/Requests').then((module) => ({
    default: module.Requests,
  })),
);
const RequestDetail = lazy(() =>
  import('../features/portal/RequestDetail').then((module) => ({
    default: module.RequestDetail,
  })),
);
const SignIn = lazy(() =>
  import('../features/identity/SignIn').then((module) => ({
    default: module.SignIn,
  })),
);
const Setup = lazy(() =>
  import('../features/identity/Setup').then((module) => ({
    default: module.Setup,
  })),
);
const Account = lazy(() =>
  import('../features/identity/Account').then((module) => ({
    default: module.Account,
  })),
);
const CustomerList = lazy(() =>
  import('../features/customers/CustomerList').then((module) => ({
    default: module.CustomerList,
  })),
);
const CustomerForm = lazy(() =>
  import('../features/customers/CustomerForm').then((module) => ({
    default: module.CustomerForm,
  })),
);
const CustomerDetail = lazy(() =>
  import('../features/customers/CustomerDetail').then((module) => ({
    default: module.CustomerDetail,
  })),
);
const ContactForm = lazy(() =>
  import('../features/customers/ContactForm').then((module) => ({
    default: module.ContactForm,
  })),
);
const Settings = lazy(() =>
  import('../features/workspace/Settings').then((module) => ({
    default: module.Settings,
  })),
);
const CaseConfiguration = lazy(() =>
  import('../features/workspace/CaseConfiguration').then((module) => ({
    default: module.CaseConfiguration,
  })),
);
const FollowUps = lazy(() =>
  import('../features/followups/FollowUps').then((module) => ({
    default: module.FollowUps,
  })),
);
const TaskDetail = lazy(() =>
  import('../features/followups/TaskDetail').then((module) => ({
    default: module.TaskDetail,
  })),
);
const CustomerImport = lazy(() =>
  import('../features/customers/CustomerImport').then((module) => ({
    default: module.CustomerImport,
  })),
);
const Analytics = lazy(() =>
  import('../features/activity/Analytics').then((module) => ({
    default: module.Analytics,
  })),
);
const EventSettings = lazy(() =>
  import('../features/activity/EventSettings').then((module) => ({
    default: module.EventSettings,
  })),
);

export function App() {
  return (
    <Suspense
      fallback={
        <main className="auth-page">
          <p role="status">Loading page...</p>
        </main>
      }
    >
      <Routes>
        {['activity', 'service'].map((view) => (
          <Route
            key={view}
            path={'/app/analytics/' + view}
            element={
              <RequireStaff>
                <AppShell>
                  <Analytics service={view === 'service'} />
                </AppShell>
              </RequireStaff>
            }
          />
        ))}
        <Route
          path="/app/analytics"
          element={<Navigate to="/app/analytics/activity" replace />}
        />
        <Route
          path="/app/settings/event-tracking"
          element={
            <RequireStaff>
              <AppShell>
                <EventSettings />
              </AppShell>
            </RequireStaff>
          }
        />
        <Route
          path="/app/settings/case-configuration/:id?"
          element={
            <RequireStaff>
              <AppShell>
                <CaseConfiguration />
              </AppShell>
            </RequireStaff>
          }
        />
        <Route
          path="/app/follow-ups/tasks"
          element={
            <RequireStaff>
              <AppShell>
                <FollowUps />
              </AppShell>
            </RequireStaff>
          }
        />
        <Route
          path="/app/follow-ups/feedback"
          element={
            <RequireStaff>
              <AppShell>
                <FollowUps />
              </AppShell>
            </RequireStaff>
          }
        />
        <Route
          path="/app/follow-ups/tasks/new"
          element={
            <RequireStaff>
              <AppShell>
                <TaskDetail />
              </AppShell>
            </RequireStaff>
          }
        />
        <Route
          path="/app/follow-ups/tasks/:id"
          element={
            <RequireStaff>
              <AppShell>
                <TaskDetail />
              </AppShell>
            </RequireStaff>
          }
        />
        <Route
          path="/app/customers/import/:id?"
          element={
            <RequireStaff>
              <AppShell>
                <CustomerImport />
              </AppShell>
            </RequireStaff>
          }
        />
        <Route path="/sign-in" element={<SignIn />} />
        <Route path="/portal/sign-in" element={<SignIn portal />} />
        <Route path="/setup" element={<Setup />} />
        <Route
          path="/portal"
          element={
            <PortalShell>
              <Requests />
            </PortalShell>
          }
        />
        <Route
          path="/portal/new"
          element={
            <PortalShell>
              <CreateCase portal />
            </PortalShell>
          }
        />
        <Route
          path="/portal/requests/:id"
          element={
            <PortalShell>
              <RequestDetail />
            </PortalShell>
          }
        />
        <Route
          path="/portal/profile"
          element={
            <PortalShell>
              <Account portal embedded />
            </PortalShell>
          }
        />
        {[
          '/app/support/inbox',
          '/app/support/cases',
          '/app/support/cases/:id',
        ].map((path) => (
          <Route
            key={path}
            path={path}
            element={
              <RequireStaff>
                <AppShell>
                  <Support />
                </AppShell>
              </RequireStaff>
            }
          />
        ))}
        <Route
          path="/app/support/cases/new"
          element={
            <RequireStaff>
              <AppShell>
                <CreateCase />
              </AppShell>
            </RequireStaff>
          }
        />
        <Route
          path="/app/support/cases/:id/edit"
          element={
            <RequireStaff>
              <AppShell>
                <CaseAssignment />
              </AppShell>
            </RequireStaff>
          }
        />
        <Route path="/" element={<Navigate to="/app/overview" replace />} />
        <Route
          path="/app/overview"
          element={
            <AppShell>
              <Overview />
            </AppShell>
          }
        />
        <Route
          path="/app/customers"
          element={
            <RequireStaff>
              <AppShell>
                <CustomerList />
              </AppShell>
            </RequireStaff>
          }
        />
        <Route
          path="/app/customers/new"
          element={
            <RequireStaff>
              <AppShell>
                <CustomerForm />
              </AppShell>
            </RequireStaff>
          }
        />
        <Route
          path="/app/customers/:id"
          element={
            <RequireStaff>
              <AppShell>
                <CustomerDetail />
              </AppShell>
            </RequireStaff>
          }
        />
        <Route
          path="/app/customers/:id/edit"
          element={
            <RequireStaff>
              <AppShell>
                <CustomerForm />
              </AppShell>
            </RequireStaff>
          }
        />
        <Route
          path="/app/customers/:id/contacts/new"
          element={
            <RequireStaff>
              <AppShell>
                <ContactForm />
              </AppShell>
            </RequireStaff>
          }
        />
        <Route
          path="/app/customers/:id/contacts/:contactId/edit"
          element={
            <RequireStaff>
              <AppShell>
                <ContactForm />
              </AppShell>
            </RequireStaff>
          }
        />
        <Route
          path="/app/settings/workspace"
          element={
            <RequireStaff>
              <AppShell>
                <Settings />
              </AppShell>
            </RequireStaff>
          }
        />
        <Route
          path="/app/account"
          element={
            <RequireStaff>
              <AppShell>
                <Account />
              </AppShell>
            </RequireStaff>
          }
        />
        <Route
          path="*"
          element={
            <AppShell>
              <h1 id="page-heading" tabIndex={-1}>
                Page unavailable
              </h1>
              <p>This page isn’t available. Choose Overview to return.</p>
            </AppShell>
          }
        />
      </Routes>
    </Suspense>
  );
}
