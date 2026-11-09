import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

test.use({ trace: 'off', screenshot: 'off', video: 'off' });

test('M3 full stack publishes a service preset, rates a case and commits a CSV', async ({
  page: staff,
  browser,
}) => {
  test.skip(
    !process.env.E2E_BASE_URL,
    'Requires migrated Compose and private synthetic browser accounts.',
  );
  test.setTimeout(120000);
  const fixture: {
    password: string;
    other_workspace: string;
    other_admin_email: string;
    other_portal_email: string;
    other_case_id: string;
    email: string;
    workspace: string;
  } = JSON.parse(readFileSync('../tmp/m2-browser.json', 'utf8'));
  async function signIn(
    page: Page,
    email: string,
    portal = false,
    workspace = fixture.other_workspace,
  ) {
    await page.goto(portal ? '/portal/sign-in' : '/sign-in');
    await page.getByLabel('Workspace address').fill(workspace);
    await page.getByLabel('Email', { exact: true }).fill(email);
    try {
      await page.getByLabel('Password', { exact: true }).fill(fixture.password);
    } catch {
      throw new Error('Could not enter the private synthetic credential.');
    }
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    await expect(
      page.getByRole('heading', {
        level: 1,
        name: portal ? 'Your requests' : 'Customers',
      }),
    ).toBeVisible();
  }
  await signIn(staff, fixture.other_admin_email);
  const member = (await (await staff.request.get('/api/v1/auth/me')).json())
    .data.member_id as string;
  const team = await staff.evaluate(async (memberId) => {
    const csrf = await (await fetch('/api/v1/auth/csrf')).json();
    const response = await fetch('/api/v1/teams', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': csrf.data.csrf_token,
      },
      body: JSON.stringify({
        name: 'Synthetic appointments',
        member_ids: [memberId],
      }),
    });
    if (!response.ok)
      throw new Error('Could not create the synthetic routing team.');
    return (await response.json()).data.id as string;
  }, member);
  await staff.goto('/app/settings/case-configuration/new');
  await staff.getByLabel('Starter preset').selectOption('service_business');
  await staff.getByRole('button', { name: 'Copy preset into draft' }).click();
  await staff
    .getByLabel('Default routing team', { exact: true })
    .first()
    .selectOption(team);
  await staff.getByRole('button', { name: 'Save draft' }).click();
  await expect(staff.getByText('Draft saved.', { exact: true })).toBeVisible();
  await staff.getByRole('button', { name: 'Review and publish' }).click();
  await expect(
    staff.getByRole('heading', { name: 'Portal request preview' }),
  ).toBeVisible();
  await staff
    .getByRole('button', { name: 'Publish configuration', exact: true })
    .click();
  await expect(
    staff.getByText('Configuration published for new cases.'),
  ).toBeVisible();

  const portalContext = await browser.newContext({
    baseURL: process.env.E2E_BASE_URL,
  });
  const originalContext = await browser.newContext({
    baseURL: process.env.E2E_BASE_URL,
  });
  try {
    const portal = await portalContext.newPage();
    const original = await originalContext.newPage();
    await signIn(portal, fixture.other_portal_email, true);
    await signIn(original, fixture.email, false, fixture.workspace);
    const originalConfig = await (
      await original.request.get('/api/v1/case-configs')
    ).json();
    expect(
      originalConfig.data[0].definition.categories.some(
        (item: { key: string }) => item.key === 'access',
      ),
    ).toBe(true);
    const old = await (
      await staff.request.get('/api/v1/cases/' + fixture.other_case_id)
    ).json();
    expect(old.data.category_label).toBe('Access');

    await portal.goto('/portal/new');
    const subject = 'Synthetic appointment update';
    await portal
      .getByLabel('Category', { exact: true })
      .selectOption('appointment');
    await portal.getByLabel('Subject', { exact: true }).fill(subject);
    await portal
      .getByLabel('Description', { exact: true })
      .fill('Please confirm my appointment time.');
    await portal.getByLabel(/Appointment date/).fill('2026-11-09');
    await portal
      .getByRole('button', { name: 'Submit request', exact: true })
      .click();
    await expect(
      portal.getByRole('heading', { name: subject, exact: true }),
    ).toBeVisible();
    const id = new URL(portal.url()).pathname.split('/').at(-1)!;
    const stored = await (
      await staff.request.get('/api/v1/cases/' + id)
    ).json();
    expect(stored.data.team.id).toBe(team);
    expect(stored.data.custom_values.appointment_date).toBe('2026-11-09');
    expect(stored.data.config_version_id).not.toBe(old.data.config_version_id);
    expect((await original.request.get('/api/v1/cases/' + id)).status()).toBe(
      404,
    );
    await staff.goto('/app/support/cases/' + id);
    await staff
      .getByRole('button', { name: 'Claim case', exact: true })
      .click();
    await expect(
      staff.getByText('Case claimed.', { exact: true }),
    ).toBeVisible();
    await staff
      .getByRole('button', { name: 'Resolve case', exact: true })
      .click();
    const modal = staff.getByRole('dialog', { name: 'Resolve case' });
    await modal
      .getByLabel('Public resolution summary')
      .fill('The synthetic appointment time is confirmed.');
    await modal.getByLabel('Resolution code').selectOption('answered');
    await modal
      .getByRole('button', { name: 'Resolve case', exact: true })
      .click();
    await expect(
      staff.getByText('Resolution posted.', { exact: true }),
    ).toBeVisible();

    await portal.reload();
    await portal.getByRole('radio', { name: /^2 · Dissatisfied$/ }).check();
    await portal
      .getByLabel(/Comment/)
      .fill('I needed a clearer appointment window.');
    await portal
      .getByRole('button', { name: 'Submit feedback', exact: true })
      .click();
    await expect(
      portal.getByText('Feedback submitted.', { exact: true }),
    ).toBeVisible();
    await portal.reload();
    await expect(
      portal.getByText('2 of 5 · Dissatisfied', { exact: true }),
    ).toBeVisible();
    await expect(
      portal.getByRole('button', { name: 'Submit feedback' }),
    ).toHaveCount(0);
    await staff.goto('/app/follow-ups/feedback?case_id=' + id);
    await staff.getByRole('link', { name: 'Review follow-up task' }).click();
    await expect(
      staff.getByRole('heading', {
        name: 'Review low resolution rating',
        exact: true,
      }),
    ).toBeVisible();
    await staff.getByRole('button', { name: 'Record completion' }).click();
    await staff
      .getByLabel('What was done?')
      .fill('Clarified the available appointment windows.');
    await staff
      .getByRole('button', { name: 'Complete follow-up', exact: true })
      .click();
    await expect(
      staff.getByText('Follow-up completed.', { exact: true }),
    ).toBeVisible();
    await expect(
      staff.getByText(/Completed · Synthetic other administrator/),
    ).toBeVisible();

    await staff.goto('/app/customers/import');
    await staff.getByLabel('Customer CSV').setInputFiles({
      name: 'synthetic.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from(
        'external_id,name,kind\nm3-browser-import,Synthetic imported customer,business\n',
      ),
    });
    await staff.getByRole('button', { name: 'Validate CSV' }).click();
    await expect(
      staff.getByRole('heading', { name: 'Review import preview' }),
    ).toBeVisible();
    const before = await (
      await staff.request.get(
        '/api/v1/customers?q=Synthetic%20imported%20customer',
      )
    ).json();
    expect(before.data).toEqual([]);
    await staff.getByRole('button', { name: 'Review and confirm' }).click();
    await staff.getByRole('button', { name: 'Confirm import' }).click();
    await expect(
      staff.getByRole('heading', { name: 'Import complete' }),
    ).toBeVisible();
    await staff.reload();
    await expect(
      staff.getByRole('heading', { name: 'Import complete' }),
    ).toBeVisible();
    const after = await (
      await staff.request.get(
        '/api/v1/customers?q=Synthetic%20imported%20customer',
      )
    ).json();
    expect(after.data).toHaveLength(1);
  } finally {
    await portalContext.close();
    await originalContext.close();
  }
});
