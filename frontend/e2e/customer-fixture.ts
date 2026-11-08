import type { Page } from '@playwright/test';
import {
  customer,
  contact,
  envelope,
  identity,
  member,
} from '../src/test/fixtures';
import type { Contact, Customer, Identity } from '../src/api/client';

export async function customerFixture(
  page: Page,
  options: {
    signedIn?: boolean;
    viewer?: boolean;
    portal?: boolean;
    failList?: boolean;
  } = {},
) {
  let signedIn = options.signedIn ?? true;
  let failList = options.failList ?? false;
  const user: Identity = {
    ...identity,
    ...(options.viewer
      ? { role: 'viewer', permissions: ['customers:read'] }
      : {}),
    ...(options.portal
      ? {
          audience: 'portal',
          role: null,
          contact_id: contact.id,
          member_id: null,
          permissions: [],
        }
      : {}),
  };
  const rows = new Map<string, Customer>([[customer.id, { ...customer }]]);
  const contacts = new Map<string, Contact>([[contact.id, { ...contact }]]);
  const requests: {
    path: string;
    method: string;
    body: Record<string, unknown>;
    csrf: string | undefined;
    version: string | undefined;
  }[] = [];
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace('/api/v1', '');
    const method = request.method();
    const body: Record<string, unknown> = request.postData()
      ? request.postDataJSON()
      : {};
    if (method !== 'GET')
      requests.push({
        path,
        method,
        body,
        csrf: request.headers()['x-csrf-token'],
        version: request.headers()['if-match'],
      });
    const reply = (data: unknown, status = 200) =>
      route.fulfill({ status, json: data });
    if (path === '/auth/me')
      return signedIn
        ? reply(envelope(user))
        : reply(
            { code: 'unauthenticated', detail: 'Sign in to continue.' },
            401,
          );
    if (path === '/auth/csrf')
      return reply(envelope({ csrf_token: 'synthetic-browser-csrf' }));
    if (path === '/auth/login') {
      signedIn = true;
      return reply(envelope(user));
    }
    if (path === '/auth/logout') {
      signedIn = false;
      return route.fulfill({ status: 204 });
    }
    if (path === '/members') return reply(envelope([member]));
    if (path === '/health/live') return reply(envelope({ status: 'ok' }));
    if (path === '/customers' && method === 'GET') {
      if (failList) {
        failList = false;
        return reply(
          {
            detail: 'Customers could not be loaded.',
            code: 'dependency_unavailable',
          },
          503,
        );
      }
      const query = url.searchParams.get('q')?.toLowerCase() ?? '';
      return reply(
        envelope(
          [...rows.values()].filter(
            (row) =>
              row.name.toLowerCase().includes(query) ||
              row.external_id?.toLowerCase().includes(query),
          ),
        ),
      );
    }
    if (path === '/customers' && method === 'POST') {
      const row = {
        ...customer,
        ...body,
        id: '66666666-6666-4666-8666-666666666666',
        name: String(body.name),
        version: 1,
      } as Customer;
      rows.set(row.id, row);
      return reply(envelope(row), 201);
    }
    const customerId = path.match(/^\/customers\/([^/]+)$/)?.[1];
    if (customerId && rows.has(customerId)) {
      let row = rows.get(customerId)!;
      if (method === 'PATCH') {
        row = { ...row, ...body, version: row.version + 1 } as Customer;
        rows.set(customerId, row);
      }
      return reply(envelope(row));
    }
    if (path === '/contacts' && method === 'GET')
      return reply(
        envelope(
          [...contacts.values()].filter(
            (row) => row.customer_id === url.searchParams.get('customer_id'),
          ),
        ),
      );
    if (path === '/contacts' && method === 'POST') {
      const row = {
        ...contact,
        ...body,
        id: '77777777-7777-4777-8777-777777777777',
        name: String(body.name),
        email: String(body.email),
        customer_id: String(body.customer_id),
      } as Contact;
      contacts.set(row.id, row);
      return reply(envelope(row), 201);
    }
    return reply(
      { detail: 'This record is not available.', code: 'not_found' },
      404,
    );
  });
  return { requests };
}
