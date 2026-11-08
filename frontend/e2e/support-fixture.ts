import type { Page } from '@playwright/test';
import { CaseServer } from '../src/test/case-server';
import { caseIdentity, syntheticCase } from '../src/test/case-fixtures';
import { envelope } from '../src/test/fixtures';

export async function supportFixture(
  page: Page,
  options: { portal?: boolean; viewer?: boolean; server?: CaseServer } = {},
) {
  const server = options.server ?? new CaseServer();
  let signedIn = true;
  const user = {
    ...caseIdentity,
    ...(options.portal
      ? {
          audience: 'portal',
          role: null,
          member_id: null,
          contact_id: syntheticCase.requester.id,
          permissions: [],
        }
      : options.viewer
        ? { role: 'viewer', permissions: ['customers:read', 'cases:read'] }
        : {}),
  };
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname.replace('/api/v1', '');
    if (path === '/auth/me')
      return route.fulfill(
        signedIn
          ? { status: 200, json: envelope(user) }
          : {
              status: 401,
              json: { code: 'unauthenticated', detail: 'Sign in to continue.' },
            },
      );
    if (path === '/auth/logout') {
      signedIn = false;
      return route.fulfill({ status: 204 });
    }
    const raw = request.headers();
    const headers = {
      ...raw,
      'If-Match': raw['if-match'] ?? '',
      'Idempotency-Key': raw['idempotency-key'] ?? '',
    };
    const response = await server.respond(
      request.url(),
      request.method(),
      request.postData() ? request.postDataJSON() : {},
      headers,
      options.portal,
    );
    return route.fulfill({ status: response.status, json: response.json });
  });
  return server;
}
