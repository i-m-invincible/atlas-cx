import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import axe from 'axe-core';
import {
  caseIdentity,
  config,
  customer,
  publicCase,
  syntheticCase,
} from '../src/test/case-fixtures';
import { envelope } from '../src/test/fixtures';
import { supportFixture } from './support-fixture';

async function noHorizontalOverflow(page: Page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
}

for (const width of [1440, 1024, 700, 390]) {
  test('M3 operations remain usable at ' + width + 'px', async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await supportFixture(page);
    let portal = false;
    await page.route('**/api/v1/auth/me', async (route) =>
      route.fulfill({
        json: envelope({
          ...caseIdentity,
          audience: portal ? 'portal' : 'staff',
          role: portal ? null : 'admin',
          contact_id: portal ? syntheticCase.requester.id : null,
          permissions: portal
            ? []
            : [
                ...caseIdentity.permissions,
                'tasks:read',
                'tasks:write',
                'customers:import',
              ],
          capabilities: { ...caseIdentity.capabilities, feedback: true },
        }),
      }),
    );
    const taskId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
    let task = {
      id: taskId,
      version: 1,
      title: 'Synthetic appointment follow-up',
      description: null,
      customer: { id: customer.id, name: customer.name },
      case: null,
      feedback_id: null,
      assignee: { id: caseIdentity.member_id, name: caseIdentity.display_name },
      state: 'open',
      due_at: '2026-11-09T12:00:00Z',
      overdue: true,
      completed_at: null as string | null,
      completed_by_member_id: null as string | null,
      completion_note: null as string | null,
      created_at: customer.created_at,
      updated_at: customer.updated_at,
    };
    await page.route('**/api/v1/tasks?**', async (route) =>
      route.fulfill({ json: envelope([task]) }),
    );
    await page.route('**/api/v1/tasks/' + taskId, async (route) => {
      if (route.request().method() === 'PATCH') {
        expect(route.request().headers()['if-match']).toBe('"1"');
        const body = route.request().postDataJSON();
        expect(body.completion_note).toBe('Confirmed the appointment.');
        task = {
          ...task,
          ...body,
          version: 2,
          overdue: false,
          completed_at: customer.updated_at,
        };
      }
      return route.fulfill({ json: envelope(task) });
    });
    await page.route('**/api/v1/tasks/' + taskId + '/history', async (route) =>
      route.fulfill({ json: envelope([]) }),
    );
    await page.goto('/app/follow-ups/tasks?scope=all');
    await page.getByRole('link', { name: task.title, exact: true }).click();
    await page.getByRole('button', { name: 'Record completion' }).click();
    await page.getByLabel('What was done?').fill('Confirmed the appointment.');
    await page
      .getByRole('button', { name: 'Complete follow-up', exact: true })
      .click();
    await expect(
      page.getByText('Follow-up completed.', { exact: true }),
    ).toBeVisible();
    await noHorizontalOverflow(page);

    await page.route('**/api/v1/case-presets', async (route) =>
      route.fulfill({
        json: envelope([
          {
            key: 'service_business',
            label: 'Service business',
            definition: {
              ...config.definition,
              categories: [
                {
                  key: 'appointment',
                  label: 'Appointment',
                  default_team_id: null,
                },
              ],
            },
          },
        ]),
      }),
    );
    await page.route('**/api/v1/case-configs', async (route) =>
      route.fulfill({
        status: 201,
        json: envelope({
          ...config,
          number: 2,
          status: 'draft',
          published_at: null,
          definition: route.request().postDataJSON(),
        }),
      }),
    );
    await page.goto('/app/settings/case-configuration/new');
    await page.getByLabel('Starter preset').selectOption('service_business');
    await page.getByRole('button', { name: 'Copy preset into draft' }).click();
    await expect(page.getByLabel('Category label')).toHaveValue('Appointment');
    await page.getByRole('button', { name: 'Save draft' }).click();
    await expect(page.getByText('Draft saved.', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Review and publish' }).click();
    await expect(
      page.getByRole('heading', { name: 'Portal request preview' }),
    ).toBeVisible();
    await noHorizontalOverflow(page);

    const importId = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
    const staged = {
      id: importId,
      version: 1,
      status: 'validated',
      create_count: 0,
      update_count: 0,
      error_count: 1,
      expires_at: customer.updated_at,
      created_at: customer.created_at,
      completed_at: null,
      rows: [
        {
          row: 2,
          action: 'error',
          values: {},
          errors: [{ field: 'kind', message: 'Review this customer value.' }],
        },
      ],
    };
    await page.route('**/api/v1/customer-imports/validate', async (route) => {
      expect(route.request().headers()['content-type']).toContain(
        'multipart/form-data; boundary=',
      );
      return route.fulfill({ status: 201, json: envelope(staged) });
    });
    await page.route('**/api/v1/customer-imports/' + importId, async (route) =>
      route.fulfill({ json: envelope(staged) }),
    );
    await page.goto('/app/customers/import');
    await page.getByLabel('Customer CSV').setInputFiles({
      name: 'synthetic.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from('external_id,name,kind\nX,Test,unknown\n'),
    });
    await page.getByRole('button', { name: 'Validate CSV' }).click();
    await expect(
      page.getByText('Fix the rows listed below before importing.'),
    ).toBeVisible();
    await expect(
      page.getByRole('button', { name: 'Confirm import' }),
    ).toHaveCount(0);
    await noHorizontalOverflow(page);

    portal = true;
    const row = {
      ...publicCase(syntheticCase),
      state: 'resolved',
      state_label: 'Resolved',
      can_rate: true,
      can_reply: false,
      can_reopen: true,
    };
    await page.route('**/api/v1/portal/cases/' + row.id, async (route) =>
      route.fulfill({ json: envelope(row) }),
    );
    const ratings: object[] = [];
    await page.route(
      '**/api/v1/portal/cases/' + row.id + '/feedback',
      async (route) => route.fulfill({ json: envelope(ratings) }),
    );
    await page.route(
      '**/api/v1/portal/cases/' + row.id + '/cycles/1/feedback',
      async (route) => {
        const body = route.request().postDataJSON();
        expect(body.rating).toBe(2);
        expect(route.request().headers()['idempotency-key']).toBeTruthy();
        const saved = {
          id: taskId,
          cycle_number: 1,
          ...body,
          created_at: customer.created_at,
        };
        ratings.push(saved);
        row.can_rate = false;
        return route.fulfill({ status: 201, json: envelope(saved) });
      },
    );
    await page.goto('/portal/requests/' + row.id);
    const rating = page.getByRole('radio', { name: /^2 · Dissatisfied$/ });
    await rating.focus();
    await page.keyboard.press('Space');
    await expect(rating).toBeChecked();
    await page
      .getByRole('button', { name: 'Submit feedback', exact: true })
      .click();
    await expect(
      page.getByText('Feedback submitted.', { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText('2 of 5 · Dissatisfied', { exact: true }),
    ).toBeVisible();
    await noHorizontalOverflow(page);
    await page.addScriptTag({ content: axe.source });
    const results = await page.evaluate(async () => window.axe.run());
    expect(
      results.violations.filter((item) =>
        ['serious', 'critical'].includes(item.impact ?? ''),
      ),
    ).toEqual([]);
  });
}
