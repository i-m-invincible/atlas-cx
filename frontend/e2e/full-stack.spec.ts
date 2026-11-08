import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';

test('M1 full stack persists customers and enforces portal identity', async ({
  page,
  browser,
}) => {
  test.skip(
    !process.env.E2E_BASE_URL,
    'Requires the migrated Compose stack and isolated operator-seeded fixture.',
  );
  const fixture: {
    workspace: string;
    workspace_id: string;
    email: string;
    password: string;
    other_customer_id: string;
  } = JSON.parse(readFileSync('../tmp/m1-browser.json', 'utf8'));
  await page.goto('/sign-in');
  await page.getByLabel('Workspace address').fill(fixture.workspace);
  await page.getByLabel('Email', { exact: true }).fill(fixture.email);
  await page.getByLabel('Password', { exact: true }).fill(fixture.password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(
    page.getByRole('heading', { level: 1, name: 'Customers' }),
  ).toBeVisible();
  const cookie = (await page.context().cookies()).find(
    (item) => item.name === 'atlas_session',
  );
  expect(cookie?.secure).toBe(true);
  expect(cookie?.httpOnly).toBe(true);
  expect(cookie?.sameSite).toBe('Lax');
  const denied = await page.evaluate(
    async (id) => (await fetch(`/api/v1/customers/${id}`)).status,
    fixture.other_customer_id,
  );
  expect(denied).toBe(404);
  await page.getByRole('link', { name: 'Add customer', exact: true }).click();
  const name = `Synthetic persisted ${Date.now()}`;
  await page.getByLabel('Customer name').fill(name);
  await page.getByRole('button', { name: 'Add customer', exact: true }).click();
  await expect(page.getByRole('heading', { level: 1, name })).toBeVisible();
  const detail = page.url();
  await page.reload();
  await expect(page.getByRole('heading', { level: 1, name })).toBeVisible();
  await page.getByRole('link', { name: 'Add contact', exact: true }).click();
  const contactEmail = `portal-${Date.now()}@example.com`;
  await page.getByLabel('Contact name').fill('Synthetic portal contact');
  await page.getByLabel('Email', { exact: true }).fill(contactEmail);
  await page.getByRole('button', { name: 'Add contact', exact: true }).click();
  await expect(page.getByText(contactEmail, { exact: true })).toBeVisible();
  await page
    .getByRole('button', {
      name: 'Create setup link for Synthetic portal contact',
      exact: true,
    })
    .click();
  await page.getByText('Reveal setup link', { exact: true }).click();
  const setupUrl = await page.locator('.secret-value').textContent();
  expect(
    setupUrl?.startsWith(process.env.E2E_BASE_URL! + '/setup#token='),
  ).toBe(true);
  const portalContext = await browser.newContext();
  const portal = await portalContext.newPage();
  await portal.goto(setupUrl!);
  await expect(portal).toHaveURL(/\/setup$/);
  await portal
    .getByLabel('New password', { exact: true })
    .fill(fixture.password);
  await portal
    .getByRole('button', { name: 'Set up access', exact: true })
    .click();
  await expect(
    portal.getByText('Access set up. You can sign in now.'),
  ).toBeVisible();
  await portal
    .getByRole('link', { name: 'Customer portal sign-in', exact: true })
    .click();
  await portal.getByLabel('Workspace address').fill(fixture.workspace);
  await portal.getByLabel('Email', { exact: true }).fill(contactEmail);
  await portal.getByLabel('Password', { exact: true }).fill(fixture.password);
  await portal.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(
    portal.getByRole('heading', { level: 1, name: 'Customer portal' }),
  ).toBeVisible();
  expect(
    await portal.evaluate(
      async () => (await fetch('/api/v1/customers')).status,
    ),
  ).toBe(403);
  expect(
    await portal.evaluate(async () => (await fetch('/api/v1/contacts')).status),
  ).toBe(403);
  await portal.goto(detail);
  await expect(portal).toHaveURL(/\/portal$/);
  await expect(portal.locator('.sidebar')).toHaveCount(0);
  expect(
    await portal.evaluate(() => localStorage.length + sessionStorage.length),
  ).toBe(0);
  await portal.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(
    portal.getByRole('heading', { name: 'Customer portal sign-in' }),
  ).toBeVisible();
  await portalContext.close();
});
