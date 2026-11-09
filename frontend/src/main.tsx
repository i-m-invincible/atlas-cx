import React from 'react';
import ReactDOM from 'react-dom/client';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import { App } from './app/App';
import './styles.css';
import './features/customers/customers.css';
import './features/support/support.css';
import './features/followups/operations.css';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SessionProvider } from './features/identity/SessionProvider';

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

const router = createBrowserRouter([
  {
    path: '*',
    element: (
      <SessionProvider>
        <App />
      </SessionProvider>
    ),
  },
]);

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>,
);
