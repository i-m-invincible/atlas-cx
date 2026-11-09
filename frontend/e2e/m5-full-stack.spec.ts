import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

test.use({ trace: 'off', screenshot: 'off', video: 'off' });

test('M5 full stack publishes real MiniLM knowledge and sends a reviewed reply', async ({
  page: manager,
  browser,
}) => {
  test.skip(
    !process.env.E2E_BASE_URL,
    'Requires migrated Compose, pinned model assets, and synthetic identities.',
  );
  test.setTimeout(120000);
  const fixture: {
    workspace: string;
    password: string;
    m5_manager_email: string;
    m5_agent_email: string;
    m5_case_id: string;
    other_workspace: string;
    other_admin_email: string;
  } = JSON.parse(readFileSync('../tmp/m5-browser.json', 'utf8'));
  async function login(
    page: Page,
    email: string,
    workspace = fixture.workspace,
  ) {
    await page.goto('/sign-in');
    await page.getByLabel('Workspace address').fill(workspace);
    await page.getByLabel('Email', { exact: true }).fill(email);
    try {
      await page.getByLabel('Password', { exact: true }).fill(fixture.password);
    } catch {
      throw new Error('Could not enter the synthetic credential.');
    }
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    await expect(
      page.getByRole('heading', { name: 'Customers', level: 1 }),
    ).toBeVisible();
  }
  const title = 'Synthetic M5 badge desk rules';
  const policy = 'The fictional M5 badge desk opens at 08:20 on business days.';
  await login(manager, fixture.m5_manager_email);
  await manager.goto('/app/knowledge/new');
  await manager.getByLabel('Article title', { exact: true }).fill(title);
  await manager
    .getByRole('combobox', { name: 'Content source', exact: true })
    .selectOption('upload');
  await manager.getByLabel('Text file').setInputFiles({
    name: 'synthetic-badges.md',
    mimeType: 'text/markdown',
    buffer: Buffer.from('# Desk hours\n\n' + policy),
  });
  await manager
    .getByRole('button', { name: 'Save draft', exact: true })
    .click();
  await expect(
    manager.getByRole('heading', { name: title, exact: true }),
  ).toBeVisible();
  const docId = new URL(manager.url()).pathname.split('/').at(-1)!;
  const revision = new URL(manager.url()).searchParams.get('revision')!;
  await manager.getByText('Review publication', { exact: true }).click();
  await manager.getByRole('button', { name: 'Publish revision' }).click();
  await expect(
    manager.getByText('Revision 1 · Published', { exact: true }),
  ).toBeVisible({ timeout: 45000 });
  const published = (
    await (
      await manager.request.get('/api/v1/knowledge/versions/' + revision)
    ).json()
  ).data;
  expect(published.embedding_model_revision).toBe(
    '1110a243fdf4706b3f48f1d95db1a4f5529b4d41',
  );

  const agentContext = await browser.newContext({
    baseURL: process.env.E2E_BASE_URL,
  });
  const otherContext = await browser.newContext({
    baseURL: process.env.E2E_BASE_URL,
  });
  try {
    const agent = await agentContext.newPage();
    const other = await otherContext.newPage();
    await login(agent, fixture.m5_agent_email);
    await agent.goto('/app/support/cases/' + fixture.m5_case_id);
    await agent.getByRole('link', { name: 'Use knowledge' }).click();
    await agent
      .getByLabel('Your question')
      .fill('When does the fictional M5 badge desk open?');
    await agent.getByRole('button', { name: 'Find an answer' }).click();
    await expect(
      agent.getByRole('heading', { name: 'Source excerpts', exact: true }),
    ).toBeVisible({ timeout: 40000 });
    await expect(
      agent.getByRole('button', { name: 'Use draft', exact: true }),
    ).toHaveCount(0);
    const requestId = new URL(agent.url()).searchParams.get('request')!;
    const resultPath = '/api/v1/assistant/requests/' + requestId;
    const result = (await (await agent.request.get(resultPath)).json()).data;
    expect(result.mode).toBe('sources_only');
    expect(result.error_code).toBe('generation_unavailable');
    expect(result.answer_text).toBeNull();
    const source = agent.getByRole('link', { name: 'S1 · ' + title });
    await source.click();
    await expect(
      agent
        .getByRole('region', { name: 'Source passage' })
        .getByText(policy, { exact: false }),
    ).toBeVisible();
    await agent.goBack();
    await agent.getByRole('link', { name: /Returning to case/ }).click();
    await agent.getByLabel('Public reply message').fill(policy);
    await expect(
      agent
        .getByRole('list', { name: 'Conversation' })
        .getByText(policy, { exact: true }),
    ).toHaveCount(0);
    await agent.getByRole('button', { name: 'Send reply' }).click();
    await expect(
      agent
        .getByRole('list', { name: 'Conversation' })
        .getByText(policy, { exact: true }),
    ).toBeVisible();
    await agent.reload();
    await expect(
      agent
        .getByRole('list', { name: 'Conversation' })
        .getByText(policy, { exact: true }),
    ).toBeVisible();

    await login(other, fixture.other_admin_email, fixture.other_workspace);
    expect(
      (
        await other.request.get('/api/v1/knowledge/documents/' + docId)
      ).status(),
    ).toBe(404);
    expect((await other.request.get(resultPath)).status()).toBe(404);
    expect(
      (
        await other.request.get(
          '/api/v1/knowledge/chunks/' + result.sources[0].chunk_id,
        )
      ).status(),
    ).toBe(404);
    await manager.getByText('Archive article', { exact: true }).click();
    await manager
      .getByLabel('Reason', { exact: true })
      .fill('Synthetic verification complete');
    await manager.getByRole('button', { name: 'Confirm archive' }).click();
    await expect(
      manager.getByText('Article archived.', { exact: true }),
    ).toBeVisible();
    const archived = (await (await agent.request.get(resultPath)).json()).data;
    expect(archived.error_code).toBe('sources_changed');
    expect(archived.sources).toEqual([]);
  } finally {
    await agentContext.close();
    await otherContext.close();
  }
});
