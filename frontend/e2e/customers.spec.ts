import { expect, test } from '@playwright/test';
import axe from 'axe-core';
import { customerFixture } from './customer-fixture';
import { customer } from '../src/test/fixtures';

for (const width of [1440, 1024, 700, 390]) {
  test(`customers work at ${width}px`, async ({ page }, testInfo) => {
    const fixture = await customerFixture(page);
    await page.setViewportSize({ width, height: 1000 });
    await page.goto('/app/customers');
    await expect(
      page.getByRole('link', { name: customer.name, exact: true }),
    ).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: testInfo.outputPath('customers-list.png'),
      fullPage: true,
    });
    await page.addScriptTag({ content: axe.source });
    expect(
      (
        await page.evaluate(async () => (await window.axe.run()).violations)
      ).filter((item) => ['critical', 'serious'].includes(item.impact ?? '')),
    ).toEqual([]);
    await page.getByRole('link', { name: customer.name, exact: true }).click();
    await expect(
      page.getByRole('heading', { level: 1, name: customer.name }),
    ).toBeVisible();
    await expect(
      page.getByText('contact@example.com', { exact: true }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: testInfo.outputPath('customer-detail.png'),
      fullPage: true,
    });
    await page.getByRole('link', { name: 'Add contact', exact: true }).click();
    await page.getByLabel('Contact name').fill('New synthetic contact');
    await page
      .getByLabel('Email', { exact: true })
      .fill('new-contact@example.com');
    await page.getByLabel('Phone · Optional').fill('5550100');
    await page
      .getByRole('button', { name: 'Add contact', exact: true })
      .click();
    await expect(
      page.getByText('Contact added.', { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText('new-contact@example.com', { exact: true }),
    ).toBeVisible();
    await page
      .getByRole('link', { name: 'Edit customer', exact: true })
      .click();
    await page.getByLabel('Customer name').fill('Updated synthetic customer');
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: testInfo.outputPath('customer-form.png'),
      fullPage: true,
    });
    await page
      .getByRole('button', { name: 'Save customer', exact: true })
      .click();
    await expect(
      page.getByRole('heading', {
        level: 1,
        name: 'Updated synthetic customer',
      }),
    ).toBeVisible();
    expect(
      fixture.requests.find((request) => request.method === 'PATCH')?.version,
    ).toBe('"1"');
    expect(
      fixture.requests.every(
        (request) => request.csrf === 'synthetic-browser-csrf',
      ),
    ).toBe(true);
    expect(
      await page.evaluate(() => localStorage.length + sessionStorage.length),
    ).toBe(0);
  });
}

test('search retains its URL and empty-state context', async ({ page }) => {
  await customerFixture(page);
  await page.goto('/app/customers');
  await page.getByLabel('Search customers').fill('No matching customer');
  await expect(
    page.getByText('No customers match these filters.'),
  ).toBeVisible();
  await expect(page).toHaveURL(/q=No\+matching\+customer/);
  await page.getByRole('button', { name: 'Clear filters' }).click();
  await expect(
    page.getByRole('link', { name: customer.name, exact: true }),
  ).toBeVisible();
});

test('customer drafts require explicit discard when navigating away', async ({
  page,
}) => {
  await customerFixture(page);
  await page.goto('/app/customers/new');
  await page.getByLabel('Customer name').fill('Unsaved synthetic draft');
  await page
    .getByRole('link', { name: 'Back to customers', exact: true })
    .click();
  await expect(
    page.getByRole('dialog', { name: 'Discard unsaved changes?' }),
  ).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Keep editing' }),
  ).toBeFocused();
  await page.getByRole('button', { name: 'Keep editing' }).click();
  await expect(page.getByLabel('Customer name')).toHaveValue(
    'Unsaved synthetic draft',
  );
  await page
    .getByRole('link', { name: 'Back to customers', exact: true })
    .click();
  await page
    .getByRole('button', { name: 'Discard changes', exact: true })
    .click();
  await expect(
    page.getByRole('heading', { level: 1, name: 'Customers' }),
  ).toBeVisible();
});

test('viewer controls and portal navigation respect their audience', async ({
  page,
}) => {
  await customerFixture(page, { viewer: true });
  await page.goto('/app/customers');
  await expect(
    page.getByRole('link', { name: customer.name, exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole('link', { name: 'Add customer', exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole('link', { name: 'Settings', exact: true }),
  ).toHaveCount(0);
});

test('portal accounts never inherit staff navigation', async ({ page }) => {
  await customerFixture(page, { portal: true });
  await page.goto('/app/customers');
  await expect(page).toHaveURL(/\/portal$/);
  await expect(page.locator('.sidebar')).toHaveCount(0);
  await expect(page.getByText(customer.name, { exact: true })).toHaveCount(0);
});

test('sign-in and sign-out keep authentication out of browser storage', async ({
  page,
}) => {
  await customerFixture(page, { signedIn: false });
  await page.goto('/sign-in');
  await page.getByLabel('Workspace address').fill('synthetic');
  await page.getByLabel('Email', { exact: true }).fill('agent@example.com');
  await page
    .getByLabel('Password', { exact: true })
    .fill('Synthetic-test-password-42');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Customers', level: 1 }),
  ).toBeVisible();
  await page.getByRole('link', { name: 'Account', exact: true }).click();
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Staff sign-in' }),
  ).toBeVisible();
  expect(
    await page.evaluate(() => localStorage.length + sessionStorage.length),
  ).toBe(0);
});
