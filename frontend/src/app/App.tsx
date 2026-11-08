import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Overview } from '../features/overview/Overview';

export function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/app/overview" replace />} />
        <Route path="/app/overview" element={<Overview />} />
        <Route
          path="*"
          element={
            <>
              <h1 id="page-heading" tabIndex={-1}>
                Page unavailable
              </h1>
              <p>This page isn’t available. Choose Overview to return.</p>
            </>
          }
        />
      </Routes>
    </AppShell>
  );
}
