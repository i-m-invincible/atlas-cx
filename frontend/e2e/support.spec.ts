import { expect, test } from '@playwright/test';
import axe from 'axe-core';
import { supportFixture } from './support-fixture';
import { member, syntheticCase } from '../src/test/case-fixtures';

for (const width of [1440, 1024, 700, 390]) {
  test(`support workflow and reading order at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    const server = await supportFixture(page);
    await page.goto('/app/support/inbox');
    await page
      .getByRole('link', { name: syntheticCase.subject, exact: true })
      .click();
    await expect(
      page.getByRole('heading', { name: syntheticCase.subject, exact: true }),
    ).toBeVisible();
    const queue = page.getByRole('region', { name: 'Case queue' });
    if (width <= 700) await expect(queue).toBeHidden();
    else {
      await expect(queue).toBeVisible();
      const conversation = await page.locator('.case-main').boundingBox();
      const list = await queue.boundingBox();
      expect(conversation!.width).toBeGreaterThan(list!.width);
    }
    const context = page.getByRole('complementary', {
      name: 'Customer and case context',
    });
    if (width === 1440) await expect(context).toBeVisible();
    else await expect(context).toBeHidden();
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({
      path: `test-results/support-${width}-conversation.png`,
      fullPage: true,
    });
    await page.getByRole('button', { name: 'Claim case', exact: true }).click();
    await expect(
      page.getByText('Case claimed.', { exact: true }),
    ).toBeVisible();
    await page.getByRole('tab', { name: 'Internal note', exact: true }).click();
    await expect(page.getByRole('tabpanel')).toContainText('Staff only');
    await page
      .getByLabel('Internal note message')
      .fill('Synthetic private note for staff.');
    await page.getByRole('button', { name: 'Add note', exact: true }).click();
    await expect(
      page.getByText('Internal note added.', { exact: true }),
    ).toBeVisible();
    await page.getByRole('tab', { name: 'Public reply', exact: true }).click();
    await page
      .getByLabel('Public reply message')
      .fill('Synthetic public reply with a concrete next step.');
    await page.getByRole('button', { name: 'Send reply', exact: true }).click();
    await expect(
      page.getByText('Reply posted to the portal.', { exact: true }),
    ).toBeVisible();
    await page
      .getByRole('button', { name: 'Ask customer', exact: true })
      .click();
    const question = page.getByRole('dialog', {
      name: 'Ask customer',
      exact: true,
    });
    await question
      .getByLabel('Public question')
      .fill('Which project is affected?');
    await question
      .getByRole('button', { name: 'Ask customer', exact: true })
      .click();
    await expect(
      page.getByText('Question posted to the portal.', { exact: true }),
    ).toBeVisible();
    await page
      .getByRole('button', { name: 'Resolve case', exact: true })
      .click();
    const resolution = page.getByRole('dialog', {
      name: 'Resolve case',
      exact: true,
    });
    await resolution.getByLabel('Resolution code').selectOption('fixed');
    await resolution
      .getByLabel('Public resolution summary')
      .fill('Access was restored after correcting the project setting.');
    if (width <= 700) {
      const bounds = await resolution.boundingBox();
      expect(bounds!.x).toBe(0);
      expect(bounds!.y).toBe(0);
      expect(bounds!.width).toBe(width);
      expect(bounds!.height).toBe(1000);
    }
    await page.screenshot({
      path: `test-results/support-${width}-resolution.png`,
      fullPage: false,
    });
    await resolution
      .getByRole('button', { name: 'Resolve case', exact: true })
      .click();
    await expect(
      page.getByText('Resolution posted.', { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText('This case is resolved', { exact: true }),
    ).toBeVisible();
    expect(server.row.state).toBe('resolved');
    await page.addScriptTag({ content: axe.source });
    const results = await page.evaluate(async () => await window.axe.run());
    expect(
      results.violations.filter((item) =>
        ['serious', 'critical'].includes(item.impact ?? ''),
      ),
    ).toEqual([]);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  });

  test(`portal request form and conversation at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 950 });
    const server = await supportFixture(page, { portal: true });
    await page.goto('/portal/new');
    await page.getByLabel('Category', { exact: true }).selectOption('access');
    await page
      .getByLabel('Subject', { exact: true })
      .fill('Synthetic portal access request');
    await page
      .getByLabel('Description', { exact: true })
      .fill('I cannot open the shared project after signing in.');
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({
      path: `test-results/portal-${width}-request.png`,
      fullPage: true,
    });
    await page
      .getByRole('button', { name: 'Submit request', exact: true })
      .click();
    await expect(
      page.getByRole('heading', {
        name: 'Synthetic portal access request',
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      page.getByRole('navigation', { name: 'Portal navigation' }),
    ).toBeVisible();
    await expect(page.locator('.sidebar')).toHaveCount(0);
    await page
      .getByLabel('Reply', { exact: true })
      .fill('One more useful detail.');
    await page.getByRole('button', { name: 'Post reply', exact: true }).click();
    await expect(
      page.getByText('Reply posted.', { exact: true }),
    ).toBeVisible();
    expect(server.messages.at(-1)?.visibility).toBe('public');
    await page.screenshot({
      path: `test-results/portal-${width}-conversation.png`,
      fullPage: true,
    });
    await page.addScriptTag({ content: axe.source });
    const results = await page.evaluate(async () => await window.axe.run());
    expect(
      results.violations.filter((item) =>
        ['serious', 'critical'].includes(item.impact ?? ''),
      ),
    ).toEqual([]);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  });
}

test('case details and assignment remain usable at 1024px with reduced motion', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1024, height: 1000 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  const server = await supportFixture(page);
  await page.goto(`/app/support/cases/${syntheticCase.id}`);
  await page.getByRole('button', { name: 'Details', exact: true }).click();
  await expect(
    page.getByRole('link', { name: 'Synthetic customer', exact: true }),
  ).toBeVisible();
  await page
    .getByRole('link', { name: 'Edit assignment and priority', exact: true })
    .click();
  await page
    .getByLabel('Assignee', { exact: true })
    .selectOption({ label: member.display_name });
  await page.getByLabel('Priority', { exact: true }).selectOption('high');
  await page
    .getByRole('button', { name: 'Save case details', exact: true })
    .click();
  await expect(
    page.getByRole('heading', { name: syntheticCase.subject, exact: true }),
  ).toBeVisible();
  expect(server.row.priority).toBe('high');
  expect(server.row.assignee?.name).toBe(member.display_name);
  expect(
    server.requests.find((item) => item.method === 'PATCH')?.headers[
      'If-Match'
    ],
  ).toBe('"1"');
});

test('support dialogs preserve drafts and trap keyboard focus', async ({
  page,
}) => {
  await supportFixture(page);
  await page.goto(`/app/support/cases/${syntheticCase.id}`);
  await page.getByRole('button', { name: 'Resolve case', exact: true }).click();
  const modal = page.getByRole('dialog', { name: 'Resolve case', exact: true });
  await modal
    .getByLabel('Public resolution summary')
    .fill('Draft resolution preserved');
  await page.keyboard.press('Escape');
  await expect(
    page.getByRole('heading', { name: 'Discard unsaved changes?' }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Keep editing' }).click();
  await expect(page.getByLabel('Public resolution summary')).toHaveValue(
    'Draft resolution preserved',
  );
  await modal
    .getByRole('button', { name: 'Resolve case', exact: true })
    .focus();
  await page.keyboard.press('Tab');
  await expect(
    modal.getByRole('button', { name: 'Close', exact: true }),
  ).toBeFocused();
});

test('portal never renders internal notes and a viewer has no mutation controls', async ({
  page,
  context,
}) => {
  const server = await supportFixture(page, { portal: true });
  server.messages.push({
    ...server.messages[0]!,
    id: crypto.randomUUID(),
    sequence: 2,
    visibility: 'internal',
    body: 'Private note must never reach the portal.',
    author_kind: 'staff',
    message_kind: 'note',
  });
  await page.goto(`/portal/requests/${server.row.id}`);
  await expect(
    page.getByRole('heading', { name: server.row.subject, exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText('Private note must never reach the portal.'),
  ).toHaveCount(0);
  await expect(page.getByText('Operational targets')).toHaveCount(0);
  const viewer = await context.newPage();
  await supportFixture(viewer, { viewer: true });
  await viewer.goto(`/app/support/cases/${server.row.id}`);
  await expect(
    viewer.getByRole('heading', { name: server.row.subject, exact: true }),
  ).toBeVisible();
  await expect(viewer.getByRole('button', { name: 'Claim case' })).toHaveCount(
    0,
  );
  await expect(
    viewer.getByRole('button', { name: 'Resolve case' }),
  ).toHaveCount(0);
  await expect(viewer.getByLabel('Public reply message')).toHaveCount(0);
});

test('narrow back navigation restores queue filters and focus', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 900 });
  await supportFixture(page);
  await page.goto('/app/support/inbox?q=Synthetic&view=all');
  await page
    .getByRole('link', { name: syntheticCase.subject, exact: true })
    .click();
  await page.getByRole('link', { name: 'Back to inbox' }).click();
  await expect(page.getByLabel('Search cases')).toHaveValue('Synthetic');
  await expect(
    page.getByRole('link', { name: syntheticCase.subject, exact: true }),
  ).toBeFocused();
  await page.getByRole('button', { name: 'Filters', exact: true }).click();
  const filters = page.getByRole('dialog', { name: 'Case filters' });
  await filters.getByLabel('Priority', { exact: true }).selectOption('urgent');
  await filters.getByRole('button', { name: 'Done' }).click();
  await expect(page.getByText('No cases match this view.')).toBeVisible();
  await expect(page).toHaveURL(/priority=urgent/);
});
