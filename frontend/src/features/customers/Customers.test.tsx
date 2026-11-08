import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { CustomerList } from './CustomerList';
import { CustomerForm } from './CustomerForm';
import { ContactForm } from './ContactForm';
import { SessionContext } from '../identity/session';
import {
  contact,
  customer,
  envelope,
  identity,
  member,
} from '../../test/fixtures';

afterEach(() => vi.unstubAllGlobals());

function mount(path: string, role: 'admin' | 'viewer' = 'admin') {
  const current = {
    ...identity,
    role,
    permissions: role === 'viewer' ? ['customers:read'] : identity.permissions,
  };
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const router = createMemoryRouter(
    [
      { path: '/app/customers', element: <CustomerList /> },
      { path: '/app/customers/new', element: <CustomerForm /> },
      { path: '/app/customers/:id/edit', element: <CustomerForm /> },
      { path: '/app/customers/:id/contacts/new', element: <ContactForm /> },
      {
        path: '/app/customers/:id/contacts/:contactId/edit',
        element: <ContactForm />,
      },
      { path: '/app/customers/:id', element: <h1>Customer saved</h1> },
    ],
    { initialEntries: [path] },
  );
  render(
    <QueryClientProvider client={client}>
      <SessionContext.Provider
        value={{
          identity: current,
          loading: false,
          error: null,
          setIdentity: vi.fn(),
          refreshIdentity: async () => {},
        }}
      >
        <RouterProvider router={router} />
      </SessionContext.Provider>
    </QueryClientProvider>,
  );
  return { client, router };
}

function network(customers: (typeof customer)[] = [customer]) {
  const fetch = vi
    .fn()
    .mockImplementation(async (url: string, options?: RequestInit) => {
      const pathname = new URL(url, 'http://localhost').pathname;
      let data: unknown = envelope(null);
      if (pathname.endsWith('/auth/csrf'))
        data = envelope({ csrf_token: 'synthetic-csrf' });
      else if (pathname.endsWith('/members')) data = envelope([member]);
      else if (pathname === '/api/v1/customers' && options?.method === 'POST')
        data = envelope(customer);
      else if (pathname === '/api/v1/customers') data = envelope(customers);
      else if (pathname === `/api/v1/customers/${customer.id}`)
        data = envelope(customer);
      else if (pathname === `/api/v1/contacts/${contact.id}`)
        data = envelope(contact);
      return {
        ok: true,
        status: options?.method === 'POST' ? 201 : 200,
        json: async () => data,
      };
    });
  vi.stubGlobal('fetch', fetch);
  return fetch;
}

it('shows linked customer records and never synthesizes a health score', async () => {
  network();
  mount('/app/customers');
  expect(
    (await screen.findAllByRole('link', { name: customer.name }))[0],
  ).toHaveAttribute('href', `/app/customers/${customer.id}`);
  expect(screen.getByText('Unknown')).toBeInTheDocument();
});

it('distinguishes empty collections from filtered results', async () => {
  network([]);
  mount('/app/customers');
  expect(await screen.findByText('No customers yet.')).toBeVisible();
});

it('shows filtered empty copy and keeps the search text', async () => {
  network([]);
  mount('/app/customers?q=missing');
  expect(
    await screen.findByText('No customers match these filters.'),
  ).toBeVisible();
  expect(screen.getByLabelText('Search customers')).toHaveValue('missing');
});

it('loads owner choices beyond the first API page', async () => {
  const fetch = network();
  const original = fetch.getMockImplementation()!;
  fetch.mockImplementation(async (url: string, options?: RequestInit) => {
    const parsed = new URL(url, 'http://localhost');
    if (parsed.pathname === '/api/v1/members')
      return {
        ok: true,
        status: 200,
        json: async () =>
          parsed.searchParams.has('cursor')
            ? envelope([
                {
                  ...member,
                  id: '66666666-6666-4666-8666-666666666666',
                  display_name: 'Later page owner',
                },
              ])
            : envelope([member], true, 'synthetic-next-cursor'),
      };
    return original(url, options);
  });
  mount('/app/customers');
  expect(
    await screen.findByRole('option', { name: 'Later page owner' }),
  ).toBeVisible();
  expect(
    fetch.mock.calls.some(([url]) =>
      String(url).includes('cursor=synthetic-next-cursor'),
    ),
  ).toBe(true);
});

it('clears the visible tag filter together with its URL state', async () => {
  network();
  const { router } = mount('/app/customers?tag=pilot&sort=created_at');
  expect(await screen.findByLabelText('Tag')).toHaveValue('pilot');
  await userEvent.click(screen.getByRole('button', { name: 'Clear filters' }));
  expect(screen.getByLabelText('Tag')).toHaveValue('');
  expect(router.state.location.search).toBe('');
});

it('hides customer mutation actions from a viewer', async () => {
  network();
  mount('/app/customers', 'viewer');
  await screen.findAllByRole('link', { name: customer.name });
  expect(
    screen.queryByRole('link', { name: 'Add customer' }),
  ).not.toBeInTheDocument();
});

it('shows loading and recoverable network errors', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
  mount('/app/customers');
  expect(screen.getByText('Loading customers…')).toHaveAttribute(
    'role',
    'status',
  );
  expect(
    await screen.findByRole('button', { name: 'Retry customers' }),
  ).toBeVisible();
});

it('creates a customer through the API with CSRF and validated input', async () => {
  const fetch = network();
  mount('/app/customers/new');
  await userEvent.type(
    screen.getByLabelText('Customer name'),
    'New synthetic customer',
  );
  await userEvent.click(screen.getByRole('button', { name: 'Add customer' }));
  expect(
    await screen.findByRole('heading', { name: 'Customer saved' }),
  ).toBeVisible();
  expect(fetch).toHaveBeenCalledWith(
    '/api/v1/customers',
    expect.objectContaining({
      method: 'POST',
      headers: expect.objectContaining({ 'X-CSRF-Token': 'synthetic-csrf' }),
    }),
  );
});

it('preserves a draft when saving fails', async () => {
  const fetch = network();
  fetch.mockImplementation(async (url: string, options?: RequestInit) => ({
    ok: options?.method !== 'POST',
    status: 503,
    json: async () =>
      url.endsWith('/auth/csrf')
        ? envelope({ csrf_token: 'synthetic-csrf' })
        : url.includes('/members')
          ? envelope([member])
          : {
              detail: 'The service is unavailable.',
              code: 'dependency_unavailable',
            },
  }));
  mount('/app/customers/new');
  await userEvent.type(
    screen.getByLabelText('Customer name'),
    'Keep this draft',
  );
  await userEvent.click(screen.getByRole('button', { name: 'Add customer' }));
  expect(await screen.findByText('The service is unavailable.')).toBeVisible();
  expect(screen.getByLabelText('Customer name')).toHaveValue('Keep this draft');
});

it('focuses a validation summary and links to invalid fields', async () => {
  network();
  mount('/app/customers/new');
  await userEvent.click(screen.getByRole('button', { name: 'Add customer' }));
  const summary = await screen.findByRole('alert');
  await waitFor(() => expect(summary).toHaveFocus());
  await userEvent.click(
    screen.getByRole('link', { name: 'Enter the customer name.' }),
  );
  expect(screen.getByLabelText('Customer name')).toHaveFocus();
});

it('requires If-Match for edits and preserves a conflict draft', async () => {
  const fetch = network();
  const original = fetch.getMockImplementation()!;
  fetch.mockImplementation(async (url: string, options?: RequestInit) =>
    options?.method === 'PATCH'
      ? {
          ok: false,
          status: 409,
          json: async () => ({
            code: 'version_conflict',
            detail: 'This record changed.',
          }),
        }
      : original(url, options),
  );
  mount(`/app/customers/${customer.id}/edit`);
  const name = await screen.findByLabelText('Customer name');
  await userEvent.clear(name);
  await userEvent.type(name, 'Conflict draft');
  await userEvent.click(screen.getByRole('button', { name: 'Save customer' }));
  expect(await screen.findByText('This record changed.')).toBeVisible();
  expect(name).toHaveValue('Conflict draft');
  expect(fetch).toHaveBeenCalledWith(
    `/api/v1/customers/${customer.id}`,
    expect.objectContaining({
      headers: expect.objectContaining({ 'If-Match': '"1"' }),
    }),
  );
});

it('requires explicit review and save before applying a contact conflict draft', async () => {
  const fetch = network();
  const original = fetch.getMockImplementation()!;
  let writes = 0;
  fetch.mockImplementation(async (url: string, options?: RequestInit) => {
    if (options?.method === 'PATCH') {
      writes += 1;
      return writes === 1
        ? {
            ok: false,
            status: 409,
            json: async () => ({
              code: 'version_conflict',
              detail: 'Contact changed.',
            }),
          }
        : {
            ok: true,
            status: 200,
            json: async () => envelope({ ...contact, version: 3 }),
          };
    }
    if (writes && url === `/api/v1/contacts/${contact.id}`)
      return {
        ok: true,
        status: 200,
        json: async () =>
          envelope({ ...contact, version: 2, name: 'Latest contact' }),
      };
    return original(url, options);
  });
  mount(`/app/customers/${customer.id}/contacts/${contact.id}/edit`);
  const name = await screen.findByLabelText('Contact name');
  await userEvent.clear(name);
  await userEvent.type(name, 'My contact draft');
  await userEvent.click(screen.getByRole('button', { name: 'Save contact' }));
  expect(await screen.findByText('Contact changed.')).toBeVisible();
  await userEvent.click(
    screen.getByRole('button', { name: 'Review latest contact' }),
  );
  expect(await screen.findByText('Latest contact')).toBeVisible();
  await userEvent.click(
    screen.getByRole('button', { name: 'Keep my draft for version 2' }),
  );
  expect(writes).toBe(1);
  expect(name).toHaveValue('My contact draft');
  await userEvent.click(screen.getByRole('button', { name: 'Save contact' }));
  expect(
    await screen.findByRole('heading', { name: 'Customer saved' }),
  ).toBeVisible();
  expect(fetch).toHaveBeenCalledWith(
    `/api/v1/contacts/${contact.id}`,
    expect.objectContaining({
      headers: expect.objectContaining({ 'If-Match': '"2"' }),
    }),
  );
});

it('validates contact email before sending a request', async () => {
  const fetch = network();
  mount(`/app/customers/${customer.id}/contacts/new`);
  await userEvent.type(screen.getByLabelText('Contact name'), 'New contact');
  await userEvent.type(screen.getByLabelText('Email'), 'invalid-email');
  await userEvent.click(screen.getByRole('button', { name: 'Add contact' }));
  expect(
    await screen.findByRole('link', { name: 'Enter a valid email address.' }),
  ).toBeVisible();
  expect(
    fetch.mock.calls.some(([, options]) => options?.method === 'POST'),
  ).toBe(false);
});
