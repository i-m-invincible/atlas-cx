import { Suspense, lazy } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Overview } from '../features/overview/Overview';
import { RequireStaff } from '../features/identity/SessionProvider';
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

export function App() {
  return (
    <Suspense
      fallback={
        <main className="auth-page">
          <p role="status">Loading page�</p>
        </main>
      }
    >
      <Routes>
        <Route path="/sign-in" element={<SignIn />} />
        <Route path="/portal/sign-in" element={<SignIn portal />} />
        <Route path="/setup" element={<Setup />} />
        <Route path="/portal" element={<Account portal />} />
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
