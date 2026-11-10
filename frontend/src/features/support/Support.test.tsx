import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { Support } from './Support';
import { CreateCase } from './CreateCase';
import { RequestDetail } from '../portal/RequestDetail';
import { Requests } from '../portal/Requests';
import { SessionContext } from '../identity/session';
import { CaseServer } from '../../test/case-server';
import { caseIdentity, syntheticCase } from '../../test/case-fixtures';

afterEach(() => vi.unstubAllGlobals());

function setup({
  portal = false,
  viewer = false,
  path,
  server = new CaseServer(),
}: {
  portal?: boolean;
  viewer?: boolean;
  path?: string;
  server?: CaseServer;
} = {}) {
  const current = {
    ...caseIdentity,
    ...(portal
      ? {
          audience: 'portal' as const,
          role: null,
          member_id: null,
          contact_id: syntheticCase.requester.id,
          permissions: [],
        }
      : viewer
        ? {
            role: 'viewer' as const,
            permissions: ['cases:read', 'customers:read'],
          }
        : {}),
  };
  const fetch = vi.fn(async (url: string, options?: RequestInit) => {
    const response = await server.respond(
      url,
      options?.method ?? 'GET',
      options?.body ? JSON.parse(String(options.body)) : {},
      (options?.headers as Record<string, string>) ?? {},
      portal,
    );
    return {
      ok: response.status < 400,
      status: response.status,
      json: async () => structuredClone(response.json),
    };
  });
  vi.stubGlobal('fetch', fetch);
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const router = createMemoryRouter(
    [
      { path: '/app/support/inbox', element: <Support /> },
      { path: '/app/support/cases/:id', element: <Support /> },
      { path: '/portal/new', element: <CreateCase portal /> },
      { path: '/portal', element: <Requests /> },
      { path: '/portal/requests/:id', element: <RequestDetail /> },
    ],
    { initialEntries: [path ?? `/app/support/cases/${syntheticCase.id}`] },
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
  return { server, fetch, router };
}

it('keeps public and internal drafts separate and never submits on Enter', async () => {
  const { server } = setup();
  const reply = await screen.findByLabelText('Public reply message');
  await userEvent.type(reply, 'Public draft{enter}');
  await userEvent.click(screen.getByRole('tab', { name: 'Internal note' }));
  const note = screen.getByLabelText('Internal note message');
  expect(note).toHaveValue('');
  await userEvent.type(note, 'Private draft');
  expect(screen.getByRole('tabpanel')).toHaveTextContent('Staff only');
  await userEvent.click(screen.getByRole('tab', { name: 'Public reply' }));
  expect(screen.getByLabelText('Public reply message')).toHaveValue(
    'Public draft\n',
  );
  expect(screen.getByRole('tabpanel')).toHaveTextContent(
    'Visible to the customer in the portal',
  );
  expect(
    server.requests.filter((item) => item.path.endsWith('/messages')),
  ).toHaveLength(0);
});

it('retains a failed reply and reuses its idempotency key on retry', async () => {
  const server = new CaseServer();
  server.failMessage = true;
  setup({ server });
  await userEvent.type(
    await screen.findByLabelText('Public reply message'),
    'Reply retained after failure',
  );
  await userEvent.click(screen.getByRole('button', { name: 'Send reply' }));
  expect(
    await screen.findByText('Your reply could not be posted.'),
  ).toBeVisible();
  expect(screen.getByLabelText('Public reply message')).toHaveValue(
    'Reply retained after failure',
  );
  await userEvent.click(screen.getByRole('button', { name: 'Send reply' }));
  expect(await screen.findByText('Reply posted to the portal.')).toBeVisible();
  const sent = server.requests.filter((item) =>
    item.path.endsWith('/messages'),
  );
  expect(sent).toHaveLength(2);
  expect(sent[0]!.headers['Idempotency-Key']).toBe(
    sent[1]!.headers['Idempotency-Key'],
  );
  expect(sent[0]!.headers['X-CSRF-Token']).toBe('synthetic-case-csrf');
  expect(sent[0]!.headers['If-Match']).toBe('"1"');
});

it('does not display a message as delivered until the server confirms it', async () => {
  const server = new CaseServer();
  let confirm!: () => void;
  server.delayMessage = new Promise<void>((resolve) => {
    confirm = resolve;
  });
  setup({ server });
  await userEvent.type(
    await screen.findByLabelText('Public reply message'),
    'Pending message',
  );
  await userEvent.click(screen.getByRole('button', { name: 'Send reply' }));
  expect(
    await screen.findByRole('button', { name: 'Posting...' }),
  ).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Resolve case' })).toBeDisabled();
  expect(
    within(screen.getByRole('list', { name: 'Conversation' })).queryByText(
      'Pending message',
    ),
  ).not.toBeInTheDocument();
  confirm();
  expect(await screen.findByText('Reply posted to the portal.')).toBeVisible();
  expect(await screen.findByText('Pending message')).toBeVisible();
});

it('preserves a conflict draft and requires explicit review and resubmission', async () => {
  const server = new CaseServer();
  server.conflictMessage = true;
  setup({ server });
  await userEvent.type(
    await screen.findByLabelText('Public reply message'),
    'Conflict draft',
  );
  await userEvent.click(screen.getByRole('button', { name: 'Send reply' }));
  expect(
    await screen.findByText(
      'This case changed while you were editing. Your draft is still here.',
    ),
  ).toBeVisible();
  await userEvent.click(
    screen.getByRole('button', { name: 'Review latest case' }),
  );
  await userEvent.click(
    await screen.findByRole('button', { name: 'Keep my draft for version 2' }),
  );
  expect(
    server.requests.filter((item) => item.path.endsWith('/messages')),
  ).toHaveLength(1);
  expect(screen.getByLabelText('Public reply message')).toHaveValue(
    'Conflict draft',
  );
  await userEvent.click(screen.getByRole('button', { name: 'Send reply' }));
  expect(await screen.findByText('Reply posted to the portal.')).toBeVisible();
  expect(
    server.requests.filter((item) => item.path.endsWith('/messages'))[1]!
      .headers['If-Match'],
  ).toBe('"2"');
});

it('focuses resolution validation and retains text through the discard confirmation', async () => {
  const server = new CaseServer();
  server.row.state = 'open';
  server.row.assignee = syntheticCase.customer;
  setup({ server });
  await screen.findByLabelText('Public reply message');
  await userEvent.click(screen.getByRole('button', { name: 'Resolve case' }));
  const dialog = screen.getByRole('dialog', { name: 'Resolve case' });
  await userEvent.click(
    within(dialog).getByRole('button', { name: 'Resolve case' }),
  );
  expect(await within(dialog).findByRole('alert')).toHaveFocus();
  await userEvent.type(
    within(dialog).getByLabelText('Public resolution summary'),
    'Resolution draft kept',
  );
  await userEvent.click(
    within(dialog).getByRole('button', { name: /^Close$/ }),
  );
  await userEvent.click(screen.getByRole('button', { name: 'Keep editing' }));
  expect(screen.getByLabelText('Public resolution summary')).toHaveValue(
    'Resolution draft kept',
  );
  await userEvent.click(
    within(dialog).getByRole('button', { name: 'Resolve case' }),
  );
  expect(await screen.findByText('Resolution posted.')).toBeVisible();
  const transition = server.requests.find(
    (item) => item.body.action === 'resolve',
  );
  expect(transition?.body.resolution_summary).toBe('Resolution draft kept');
});

it('hides case mutations from a viewer', async () => {
  setup({ viewer: true });
  expect(
    await screen.findByText(
      'Synthetic customer request: I cannot access the project.',
    ),
  ).toBeVisible();
  expect(
    screen.queryByRole('button', { name: 'Claim case' }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole('button', { name: 'Resolve case' }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByLabelText('Public reply message'),
  ).not.toBeInTheDocument();
});

it('renders only public portal messages and replaces a resolved composer with reopening', async () => {
  const server = new CaseServer();
  server.row.state = 'resolved';
  server.row.state_label = 'Resolved';
  server.messages.push({
    ...server.messages[0]!,
    id: crypto.randomUUID(),
    sequence: 2,
    body: 'Visible public resolution',
    author_kind: 'staff',
    message_kind: 'resolution',
  });
  setup({ portal: true, server, path: `/portal/requests/${server.row.id}` });
  expect(await screen.findByText('Visible public resolution')).toBeVisible();
  expect(
    screen.queryByLabelText('Reply', { exact: true }),
  ).not.toBeInTheDocument();
  await userEvent.type(
    screen.getByLabelText('Reopening message'),
    'Still needs attention',
  );
  await userEvent.click(screen.getByRole('button', { name: 'Reopen request' }));
  expect(await screen.findByText('Request reopened.')).toBeVisible();
  expect(
    server.requests.find((item) => item.path.endsWith('/reopen'))?.body,
  ).toEqual({ message: 'Still needs attention' });
  expect(screen.queryByText('Operational targets')).not.toBeInTheDocument();
});

it('validates the portal form and submits only contact-safe fields', async () => {
  const { server, router } = setup({ portal: true, path: '/portal/new' });
  await screen.findByLabelText('Subject');
  await userEvent.click(screen.getByRole('button', { name: 'Submit request' }));
  await waitFor(() => expect(screen.getByRole('alert')).toHaveFocus());
  await userEvent.selectOptions(screen.getByLabelText('Category'), 'access');
  await userEvent.type(
    screen.getByLabelText('Subject'),
    'New synthetic request',
  );
  await userEvent.type(
    screen.getByLabelText('Description'),
    'A precise description',
  );
  await userEvent.click(screen.getByRole('button', { name: 'Submit request' }));
  await waitFor(() =>
    expect(router.state.location.pathname).toBe(
      `/portal/requests/${server.row.id}`,
    ),
  );
  const created = server.requests.find((item) => item.path === '/portal/cases');
  expect(created?.body).toEqual({
    category_key: 'access',
    subject: 'New synthetic request',
    description: 'A precise description',
    custom_values: {},
  });
  expect(created?.headers['Idempotency-Key']).toBeTruthy();
});

it('distinguishes an empty queue from a request that cannot be read', async () => {
  const server = new CaseServer();
  server.empty = true;
  setup({ server, path: '/app/support/inbox' });
  expect(await screen.findByText('No unassigned cases.')).toBeVisible();
});
