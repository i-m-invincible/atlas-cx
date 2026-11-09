import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import axe from 'axe-core';
import { caseIdentity, config, customer } from '../src/test/case-fixtures';
import { envelope } from '../src/test/fixtures';
import type {
  EventRecord,
  Report,
  TimelineEntry,
} from '../src/features/activity/data';
import { supportFixture } from './support-fixture';

const occurrence = '2026-11-08T10:00:00Z';
const synthetic: EventRecord = {
  id: '8a9bcfc3-4fa9-4dcc-bb78-bf3d1d4bcf24',
  event_name: 'feature_used',
  event_label: 'Synthetic feature used',
  external_event_id: 'synthetic-event-1',
  occurred_at: occurrence,
  received_at: '2026-11-08T10:05:00Z',
  properties: { version: '<svg onload=alert(1)>', count: 2 },
  counts_as_activity: true,
};
const timeline: TimelineEntry[] = [
  {
    id: synthetic.id,
    title: synthetic.event_label,
    preview: synthetic.event_name,
    kind: 'event',
    actor: 'Event ingestion',
    occurred_at: occurrence,
    received_at: synthetic.received_at,
    reference_id: synthetic.id,
  },
  {
    id: '4916961f-24ec-49c0-97c0-a10d59a9230d',
    title: 'Synthetic case message',
    preview: 'Synthetic request text.',
    kind: 'message',
    actor: 'Synthetic requester',
    occurred_at: occurrence,
    received_at: null,
    reference_id: 'f15c188b-d1ce-4654-8e32-8ba07c985d84',
  },
];
const scope: Report['scope'] = {
  from_at: '2026-11-07T18:30:00Z',
  to_at: '2026-11-09T18:30:00Z',
  timezone: 'Asia/Kolkata',
  generated_at: occurrence,
  as_of: occurrence,
  today_partial: true,
  team_id: null,
  category: null,
};
const noData = { numerator: 0, denominator: 0, share: null };
const report: Report = {
  scope,
  new_cases: 2,
  active_backlog: 3,
  unassigned: 2,
  unanswered_overdue: 1,
  resolution_overdue: 0,
  paused: 1,
  first_response: {
    median_seconds: 10,
    p90_seconds: 14,
    sample_count: 2,
    attainment: { numerator: 1, denominator: 2, share: 0.5 },
  },
  resolution: {
    median_seconds: null,
    p90_seconds: null,
    sample_count: 0,
    attainment: noData,
  },
  reopen: noData,
  immature_cycles: 0,
  csat: noData,
  coverage: noData,
  follow_up: noData,
  categories: [{ key: 'service', label: 'Synthetic service', count: 2 }],
  trend: {
    scope,
    bucket: 'day',
    points: [
      {
        start: '2026-11-08',
        count: 2,
        categories: { service: 2 },
        partial: true,
      },
      {
        start: '2026-11-09',
        count: 0,
        categories: { service: 0 },
        partial: false,
      },
    ],
  },
};

async function assertUsable(page: Page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.evaluate(axe.source);
  const results = await page.evaluate(async () => {
    const runtime = (window as unknown as { axe: typeof axe }).axe;
    return (await runtime.run('main')).violations
      .filter((violation) =>
        ['serious', 'critical'].includes(violation.impact ?? ''),
      )
      .map(({ id, nodes }) => [id, nodes.map((node) => node.target)]);
  });
  expect(results).toEqual([]);
}

for (const width of [1440, 1024, 700, 390]) {
  test(
    'M4 analytics and Customer 360 at ' + width + 'px',
    async ({ page }, info) => {
      await page.setViewportSize({ width, height: 1040 });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await supportFixture(page);
      await page.route('**/api/v1/auth/me', async (route) =>
        route.fulfill({
          json: envelope({
            ...caseIdentity,
            role: 'admin',
            capabilities: { ...caseIdentity.capabilities, activity: true },
          }),
        }),
      );
      await page.route('**/api/v1/customers/*/timeline?**', async (route) => {
        const kinds = new URL(route.request().url()).searchParams.get('kinds');
        await route.fulfill({
          json: envelope(
            kinds
              ? timeline.filter((row) => kinds.split(',').includes(row.kind))
              : timeline,
          ),
        });
      });
      await page.route('**/api/v1/customers/*/events?**', async (route) => {
        const key = new URL(route.request().url()).searchParams.get(
          'event_name',
        );
        await route.fulfill({
          json: envelope(
            !key || key === synthetic.event_name ? [synthetic] : [],
          ),
        });
      });
      await page.route(
        '**/api/v1/customers/*/events/' + synthetic.id,
        async (route) => route.fulfill({ json: envelope(synthetic) }),
      );
      await page.route('**/api/v1/analytics/overview?**', async (route) => {
        const query = new URL(route.request().url()).searchParams;
        const filtered = !!query.get('from');
        await route.fulfill({
          json: envelope(
            filtered
              ? {
                  ...report,
                  new_cases: 0,
                  categories: [],
                  trend: { ...report.trend, points: [] },
                }
              : report,
          ),
        });
      });
      await page.route('**/api/v1/case-configs?**', async (route) =>
        route.fulfill({ json: envelope([config]) }),
      );
      await page.route('**/api/v1/teams?**', async (route) =>
        route.fulfill({ json: envelope([]) }),
      );
      await page.route('**/api/v1/analytics/records?**', async (route) =>
        route.fulfill({ json: envelope([]) }),
      );

      await page.goto('/app/customers/' + customer.id);
      await expect(
        page.getByRole('link', { name: 'Synthetic case message' }),
      ).toBeVisible();
      await page.getByLabel('Messages', { exact: true }).uncheck();
      await page
        .getByRole('button', { name: 'Apply timeline filters' })
        .click();
      await expect(
        page.getByRole('link', { name: 'Synthetic case message' }),
      ).toHaveCount(0);
      await page.getByRole('link', { name: synthetic.event_label }).click();
      const selected = page.getByRole('region', { name: 'Selected event' });
      await expect(
        selected.getByText('<svg onload=alert(1)>', { exact: true }),
      ).toBeVisible();
      await expect(selected.locator('svg')).toHaveCount(0);
      const disclosure = page
        .locator('summary')
        .filter({ hasText: synthetic.event_name });
      await disclosure.focus();
      await page.keyboard.press('Enter');
      await expect(
        page.getByText('Event ID', { exact: false }).last(),
      ).toBeVisible();
      await assertUsable(page);
      await page.screenshot({
        path: info.outputPath('customer-activity.png'),
        fullPage: true,
      });

      await page.goto('/app/analytics/activity');
      await expect(
        page.getByText('Choose a customer to inspect recorded activity.'),
      ).toBeVisible();
      await page
        .getByLabel('Customer', { exact: true })
        .selectOption(customer.id);
      await expect(
        page.getByRole('link', { name: 'Open Customer 360' }),
      ).toBeVisible();
      await page.getByLabel('Event name').fill('unseen_event');
      await page
        .getByRole('button', { name: 'Apply filters', exact: true })
        .click();
      await expect(page.getByText('No events in this period.')).toBeVisible();
      await page.getByRole('button', { name: 'Reset', exact: true }).click();
      await expect(
        page.getByText(synthetic.event_label, { exact: true }),
      ).toBeVisible();

      await page.getByRole('link', { name: 'Service', exact: true }).click();
      await expect(
        page.getByRole('heading', { name: 'Now', exact: true }),
      ).toBeVisible();
      await expect(
        page.getByText('No ratings submitted in this period.'),
      ).toBeVisible();
      await expect(
        page.getByRole('table', { name: 'New case counts by category' }),
      ).toBeVisible();
      await expect(
        page.getByRole('table', { name: 'New cases per day in Asia/Kolkata' }),
      ).toBeVisible();
      await page
        .getByRole('button', { name: 'Inspect records for First response' })
        .click();
      await expect(
        page.getByText('No records match this measure.'),
      ).toBeVisible();
      await assertUsable(page);
      await page.screenshot({
        path: info.outputPath('service.png'),
        fullPage: true,
      });
      if (width <= 700)
        await page.getByText('Report filters', { exact: true }).click();
      await page.getByLabel('From', { exact: true }).fill('2026-11-07');
      await page.getByLabel('To (exclusive)').fill('2026-11-08');
      await page
        .getByRole('button', { name: 'Apply filters', exact: true })
        .click();
      await expect(
        page.getByText('No cases were created in this period.'),
      ).toBeVisible();
      await expect(page).toHaveURL(/from=2026-11-07/);

      await page.route('**/api/v1/event-definitions?**', async (route) =>
        route.fulfill({ json: envelope([]) }),
      );
      await page.route('**/api/v1/api-credentials?**', async (route) =>
        route.fulfill({ json: envelope([]) }),
      );
      await page.goto('/app/settings/event-tracking');
      await expect(
        page.getByText('No ingestion credentials yet.'),
      ).toBeVisible();
      await page.getByRole('button', { name: 'New event definition' }).click();
      await page.getByRole('button', { name: 'Add property' }).click();
      await page
        .getByRole('combobox', { name: 'Type 1', exact: true })
        .selectOption('boolean');
      await expect(page.getByLabel('Maximum length 1')).toHaveCount(0);
      await assertUsable(page);
      await page.screenshot({
        path: info.outputPath('event-settings.png'),
        fullPage: true,
      });
    },
  );
}
