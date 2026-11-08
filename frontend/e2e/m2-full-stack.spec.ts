import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import type { CaseDetail } from '../src/features/support/data';

test.use({ trace: 'off', screenshot: 'off', video: 'off' });

test('M2 full stack persists portal requests, replies, resolution cycles and isolation', async ({
  page: staff,
  browser,
}) => {
  test.skip(
    !process.env.E2E_BASE_URL,
    'Requires the migrated Compose stack and private synthetic M2 fixture.',
  );
  test.setTimeout(90000);
  const fixture: {
    workspace: string;
    email: string;
    password: string;
    alpha_email: string;
    beta_email: string;
    other_case_id: string;
  } = JSON.parse(readFileSync('../tmp/m2-browser.json', 'utf8'));
  const signIn = async (page: Page, email: string, portal = false) => {
    await page.goto(portal ? '/portal/sign-in' : '/sign-in');
    await page.getByLabel('Workspace address').fill(fixture.workspace);
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
        exact: true,
      }),
    ).toBeVisible();
  };
  const alphaContext = await browser.newContext({
    baseURL: process.env.E2E_BASE_URL,
  });
  const betaContext = await browser.newContext({
    baseURL: process.env.E2E_BASE_URL,
  });
  const alpha = await alphaContext.newPage();
  const beta = await betaContext.newPage();
  try {
    await signIn(alpha, fixture.alpha_email, true);
    await alpha.getByRole('link', { name: 'New request', exact: true }).click();
    const subject = `Synthetic persisted M2 request ${Date.now()}`;
    const description = 'I cannot open the synthetic shared project.';
    await alpha.getByLabel('Category', { exact: true }).selectOption('access');
    await alpha.getByLabel('Subject', { exact: true }).fill(subject);
    await alpha.getByLabel('Description', { exact: true }).fill(description);
    await alpha
      .getByRole('button', { name: 'Submit request', exact: true })
      .click();
    await expect(
      alpha.getByRole('heading', { name: subject, exact: true }),
    ).toBeVisible();
    const id = new URL(alpha.url()).pathname.split('/').at(-1)!;
    await alpha.reload();
    await expect(alpha.getByText(description, { exact: true })).toBeVisible();

    await signIn(staff, fixture.email);
    const other = await staff.request.get(
      `/api/v1/cases/${fixture.other_case_id}`,
    );
    expect(other.status()).toBe(404);
    await staff.goto('/app/support/inbox?view=all');
    await staff.getByLabel('Search cases').fill(subject);
    await staff.getByRole('link', { name: subject, exact: true }).click();
    await staff
      .getByRole('button', { name: 'Claim case', exact: true })
      .click();
    await expect(
      staff.getByText('Case claimed.', { exact: true }),
    ).toBeVisible();
    // Exercise the real assignment form, then return to the conversation.
    await staff.getByRole('button', { name: 'Details', exact: true }).click();
    await staff
      .getByRole('link', { name: 'Edit assignment and priority', exact: true })
      .click();
    await staff.getByLabel('Priority', { exact: true }).selectOption('high');
    await staff
      .getByRole('button', { name: 'Save case details', exact: true })
      .click();
    await expect(
      staff.getByRole('heading', { name: subject, exact: true }),
    ).toBeVisible();
    const privateNote = 'Synthetic internal-only diagnostic detail.';
    await staff
      .getByRole('tab', { name: 'Internal note', exact: true })
      .click();
    await staff.getByLabel('Internal note message').fill(privateNote);
    await staff.getByRole('button', { name: 'Add note', exact: true }).click();
    await expect(
      staff.getByText('Internal note added.', { exact: true }),
    ).toBeVisible();
    const publicReply = 'We are checking the project access setting.';
    await staff.getByRole('tab', { name: 'Public reply', exact: true }).click();
    await staff.getByLabel('Public reply message').fill(publicReply);
    await staff
      .getByRole('button', { name: 'Send reply', exact: true })
      .click();
    await expect(
      staff.getByText('Reply posted to the portal.', { exact: true }),
    ).toBeVisible();
    await staff
      .getByRole('button', { name: 'Ask customer', exact: true })
      .click();
    const question = staff.getByRole('dialog', {
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
      staff.getByText('Question posted to the portal.', { exact: true }),
    ).toBeVisible();
    const readCase = async (): Promise<CaseDetail> => {
      const response = await staff.request.get(`/api/v1/cases/${id}`);
      expect(response.status()).toBe(200);
      return (await response.json()).data as CaseDetail;
    };
    const waiting = await readCase();
    expect(waiting.state).toBe('pending_customer');
    expect(waiting.target_status.status).toBe('paused');
    expect(waiting.target_status.due_at).toBeNull();
    expect(waiting.first_response_at).not.toBeNull();
    // Changing priority must retain the normal-priority target snapshot.
    expect(waiting.current_cycle.target_seconds).toBe(2880 * 60);

    await alpha.reload();
    await expect(alpha.getByText(publicReply, { exact: true })).toBeVisible();
    await expect(
      alpha.getByText('Which project is affected?', { exact: true }),
    ).toBeVisible();
    await expect(alpha.getByText(privateNote)).toHaveCount(0);
    const projection = await (
      await alpha.request.get(`/api/v1/portal/cases/${id}`)
    ).json();
    expect(projection.data).not.toHaveProperty('priority');
    expect(projection.data).not.toHaveProperty('target_status');
    const messages = await (
      await alpha.request.get(`/api/v1/portal/cases/${id}/messages`)
    ).text();
    expect(messages).not.toContain(privateNote);

    await signIn(beta, fixture.beta_email, true);
    await beta.goto(`/portal/requests/${id}`);
    await expect(beta.getByRole('alert')).toBeVisible();
    for (const suffix of ['', '/messages']) {
      expect(
        (
          await beta.request.get(`/api/v1/portal/cases/${id}${suffix}`)
        ).status(),
      ).toBe(404);
    }
    for (const suffix of ['messages', 'reopen']) {
      const status = await beta.evaluate(
        async ({ id, suffix }) => {
          const csrf = await (await fetch('/api/v1/auth/csrf')).json();
          return (
            await fetch(`/api/v1/portal/cases/${id}/${suffix}`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': csrf.data.csrf_token,
                'If-Match': '"1"',
                'Idempotency-Key': crypto.randomUUID(),
              },
              body: JSON.stringify(
                suffix === 'reopen'
                  ? { message: 'Forbidden' }
                  : { body: 'Forbidden' },
              ),
            })
          ).status;
        },
        { id, suffix },
      );
      expect(status).toBe(404);
    }
    await alpha
      .getByLabel('Reply', { exact: true })
      .fill('The synthetic project is affected.');
    await alpha
      .getByRole('button', { name: 'Post reply', exact: true })
      .click();
    await expect(
      alpha.getByText('Reply posted.', { exact: true }),
    ).toBeVisible();
    expect((await readCase()).state).toBe('open');
    await staff.reload();
    const resolve = async (summary: string) => {
      await staff
        .getByRole('button', { name: 'Resolve case', exact: true })
        .click();
      const dialog = staff.getByRole('dialog', {
        name: 'Resolve case',
        exact: true,
      });
      await dialog.getByLabel('Resolution code').selectOption('fixed');
      await dialog.getByLabel('Public resolution summary').fill(summary);
      await dialog
        .getByRole('button', { name: 'Resolve case', exact: true })
        .click();
      await expect(
        staff.getByText('Resolution posted.', { exact: true }),
      ).toBeVisible();
    };
    const firstSummary = 'Access restored by correcting the project setting.';
    await resolve(firstSummary);
    const first = await readCase();
    expect(first.state).toBe('resolved');
    await alpha.reload();
    await expect(alpha.getByText(firstSummary, { exact: true })).toBeVisible();
    await expect(alpha.getByLabel('Reply', { exact: true })).toHaveCount(0);
    await alpha
      .getByLabel('Reopening message')
      .fill('The issue returned after a new sign-in.');
    await alpha
      .getByRole('button', { name: 'Reopen request', exact: true })
      .click();
    await expect(
      alpha.getByText('Request reopened.', { exact: true }),
    ).toBeVisible();
    const reopened = await readCase();
    expect(reopened.state).toBe('open');
    expect(reopened.current_cycle.cycle_number).toBe(2);
    expect(reopened.cycles[0]).toEqual(first.cycles[0]);
    expect(reopened.first_response_at).toBe(first.first_response_at);
    await staff.reload();
    await resolve('Access rechecked and restored for the second cycle.');
    await staff
      .getByRole('button', { name: 'Close case', exact: true })
      .click();
    const closing = staff.getByRole('dialog', {
      name: 'Close case',
      exact: true,
    });
    await closing
      .getByLabel('Reason', { exact: true })
      .fill('Resolution confirmed in the synthetic test.');
    await closing
      .getByRole('button', { name: 'Close case', exact: true })
      .click();
    await expect.poll(async () => (await readCase()).state).toBe('closed');
    await alpha.reload();
    await expect(
      alpha.getByRole('heading', { name: 'This request is closed' }),
    ).toBeVisible();
    await expect(
      alpha.getByRole('link', { name: 'Create a related request' }),
    ).toBeVisible();
    await expect(alpha.getByText(privateNote)).toHaveCount(0);
    for (const page of [staff, alpha, beta]) {
      expect(
        await page.evaluate(() => localStorage.length + sessionStorage.length),
      ).toBe(0);
      const cookie = (await page.context().cookies()).find(
        (item) => item.name === 'atlas_session',
      );
      expect(cookie?.httpOnly).toBe(true);
      expect(cookie?.secure).toBe(true);
    }
  } finally {
    await alphaContext.close();
    await betaContext.close();
  }
});
