import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';

test.use({ trace: 'off', screenshot: 'off', video: 'off' });

test('M4 full stack ingests synthetic events and exposes only scoped activity', async ({
  page,
  browser,
}) => {
  test.skip(
    !process.env.E2E_BASE_URL,
    'Requires migrated Compose and private synthetic browser accounts.',
  );
  test.setTimeout(90000);
  const fixture: {
    workspace: string;
    email: string;
    password: string;
    other_workspace: string;
    other_admin_email: string;
  } = JSON.parse(readFileSync('../tmp/m2-browser.json', 'utf8'));
  async function signIn(target: typeof page, email: string, workspace: string) {
    await target.goto('/sign-in');
    await target.getByLabel('Workspace address').fill(workspace);
    await target.getByLabel('Email', { exact: true }).fill(email);
    try {
      await target
        .getByLabel('Password', { exact: true })
        .fill(fixture.password);
    } catch {
      throw new Error('Could not enter the private synthetic credential.');
    }
    await target.getByRole('button', { name: 'Sign in', exact: true }).click();
    await expect(
      target.getByRole('heading', { name: 'Customers', level: 1 }),
    ).toBeVisible();
  }
  await signIn(page, fixture.email, fixture.workspace);
  const suffix = Date.now().toString();
  const externalId = 'm4-synthetic-' + suffix;
  const eventName = 'feature_used_' + suffix;
  const eventLabel = 'Synthetic product activity ' + suffix;
  const customerId = await page.evaluate(async (external_id) => {
    const csrf = (await (await fetch('/api/v1/auth/csrf')).json()).data
      .csrf_token;
    const response = await fetch('/api/v1/customers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
      body: JSON.stringify({
        name: 'M4 synthetic activity customer',
        kind: 'business',
        external_id,
        activity_expected: true,
      }),
    });
    if (!response.ok)
      throw new Error('Could not create the synthetic customer.');
    return (await response.json()).data.id as string;
  }, externalId);
  await page.goto('/app/settings/event-tracking');
  await page.getByRole('button', { name: 'New event definition' }).click();
  await page.getByLabel('Event key', { exact: true }).fill(eventName);
  await page.getByLabel('Display label').fill(eventLabel);
  await page.getByLabel('Counts as meaningful activity').check();
  await page.getByRole('button', { name: 'Add property' }).click();
  await page.getByLabel('Property key 1').fill('feature');
  await page.getByRole('button', { name: 'Save event definition' }).click();
  await expect(page.getByRole('heading', { name: eventLabel })).toBeVisible();
  await page.getByLabel('Credential name').fill('Synthetic key ' + suffix);
  await page.getByRole('button', { name: 'Create credential' }).click();
  const secretPanel = page.getByRole('region', {
    name: 'One-time ingestion key',
  });
  await expect(secretPanel).toBeVisible();
  const secret = await secretPanel.locator('code').textContent();
  if (!secret) throw new Error('The synthetic credential was not shown.');
  await page.getByRole('button', { name: 'Dismiss key' }).click();
  await expect(secretPanel).toHaveCount(0);
  const recent = new Date(Date.now() - 60000).toISOString();
  const late = new Date(Date.now() - 3600000).toISOString();
  const item = (id: string, occurred_at: string) => ({
    external_event_id: suffix + '-' + id,
    customer_external_id: externalId,
    event_name: eventName,
    occurred_at,
    properties: { feature: 'Synthetic report opened' },
  });
  // Collect only status and counts so the bearer value cannot appear in test failures.
  const send = (events: ReturnType<typeof item>[], authenticated = true) =>
    page.evaluate(
      async ({ events, token }) => {
        const response = await fetch('/api/v1/events/batch', {
          method: 'POST',
          credentials: 'omit',
          headers: token
            ? {
                'Content-Type': 'application/json',
                Authorization: 'Bearer ' + token,
              }
            : { 'Content-Type': 'application/json' },
          body: JSON.stringify({ events }),
        });
        const body = response.ok ? (await response.json()).data : null;
        return {
          status: response.status,
          inserted: body?.inserted_count ?? null,
          duplicate: body?.duplicate_count ?? null,
        };
      },
      { events, token: authenticated ? secret : null },
    );
  expect((await send([item('recent', recent)], false)).status).toBe(401);
  expect(
    (await send([{ ...item('unknown', recent), event_name: 'unregistered' }]))
      .status,
  ).toBe(422);
  expect(await send([item('recent', recent)])).toEqual({
    status: 200,
    inserted: 1,
    duplicate: 0,
  });
  expect(await send([item('late', late), item('recent', recent)])).toEqual({
    status: 200,
    inserted: 1,
    duplicate: 1,
  });

  await page.goto('/app/customers/' + customerId);
  await expect(
    page.getByRole('heading', { name: 'Timeline', exact: true }),
  ).toBeVisible();
  await page.getByLabel('Messages', { exact: true }).uncheck();
  await page.getByRole('button', { name: 'Apply timeline filters' }).click();
  await expect(
    page.getByRole('link', { name: eventLabel, exact: true }),
  ).toHaveCount(2);
  await page
    .getByRole('link', { name: eventLabel, exact: true })
    .first()
    .click();
  await expect(
    page
      .getByRole('region', { name: 'Selected event' })
      .getByText('Synthetic report opened'),
  ).toBeVisible();
  await page.goto('/app/analytics/activity?customer=' + customerId);
  await page.getByLabel('Event name').fill(eventName);
  await page.getByRole('button', { name: 'Apply filters' }).click();
  await expect(
    page.locator('summary').filter({ hasText: eventLabel }),
  ).toHaveCount(2);
  await page.getByRole('link', { name: 'Service', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Now', exact: true }),
  ).toBeVisible();
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export CSV' }).click();
  expect((await download).suggestedFilename()).toBe('atlas-cases.csv');

  const context = await browser.newContext({
    baseURL: process.env.E2E_BASE_URL,
  });
  try {
    const other = await context.newPage();
    await signIn(other, fixture.other_admin_email, fixture.other_workspace);
    expect(
      (
        await other.request.get('/api/v1/customers/' + customerId + '/events')
      ).status(),
    ).toBe(404);
  } finally {
    await context.close();
  }
  await page.goto('/app/settings/event-tracking');
  await page
    .getByRole('button', { name: 'Revoke Synthetic key ' + suffix })
    .click();
  await page.getByRole('button', { name: 'Confirm revocation' }).click();
  await expect(
    page.getByText('Ingestion credential revoked.', { exact: true }),
  ).toBeVisible();
  expect((await send([item('revoked', recent)])).status).toBe(401);
});
