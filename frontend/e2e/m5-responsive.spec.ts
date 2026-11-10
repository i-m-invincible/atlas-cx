import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import axe from 'axe-core';
import type {
  Answer,
  AssistantSource,
  DocDetail,
  RevisionView,
} from '../src/features/knowledge/data';
import { caseIdentity, syntheticCase } from '../src/test/case-fixtures';
import { envelope } from '../src/test/fixtures';
import { supportFixture } from './support-fixture';

const title = 'Synthetic badge desk policy';
const text = 'The badge desk opens at 08:20 on business days.';
const revisionId = '6b8838ec-b154-47cc-9cf4-1c761c499ad5';
const docId = '6ba2563b-f9df-43cb-92a5-1f80d11073a3';
const questionId = '79fb4df4-d507-4e38-8fb0-4e42e9e10615';
const now = '2026-11-09T08:00:00Z';
const excerpt = text + ' <img src="remote" onerror="alert(1)">';
const cited: AssistantSource = {
  label: 'S1',
  rank: 1,
  document_id: docId,
  version_id: revisionId,
  chunk_id: 'f74372ea-f1a0-4e7b-b482-f0d96c3a578c',
  title,
  ordinal: 0,
  revision_number: 1,
  heading_path: ['Desk hours'],
  start_offset: 0,
  end_offset: excerpt.length,
  excerpt,
  source_url: 'https://example.org/forbidden',
};
const version: RevisionView = {
  id: revisionId,
  document_id: docId,
  title,
  revision_number: 1,
  version: 1,
  source_kind: 'markdown',
  source_name: null,
  content_sha256: 'a'.repeat(64),
  status: 'ready',
  embedding_model_revision: 'synthetic-test',
  error_code: null,
  indexed_at: now,
  created_at: now,
  updated_at: now,
  active_version_id: revisionId,
  content_text: '# Desk hours\n\n' + excerpt,
};
const doc: DocDetail = {
  id: docId,
  title,
  version: 3,
  active_version_id: revisionId,
  active_revision_number: 1,
  pending_version_id: null,
  latest_revision: version,
  archived_at: null,
  created_at: now,
  updated_at: now,
  revisions: [version],
};
const generated: Answer = {
  id: questionId,
  state: 'completed',
  mode: 'generated',
  answer_text: text + ' [S1]',
  abstention_reason: null,
  error_code: null,
  sources: [cited],
  model_id: 'synthetic-browser-double',
  case_id: syntheticCase.id,
  delayed: false,
  completed_at: now,
  created_at: now,
  poll_url: '/api/v1/assistant/requests/' + questionId,
  feedback: null,
};

async function accessibility(page: Page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.evaluate(axe.source);
  const violations = await page.evaluate(async () => {
    const auditor = (window as unknown as { axe: typeof axe }).axe;
    return (await auditor.run('main')).violations
      .filter((item) => ['serious', 'critical'].includes(item.impact ?? ''))
      .map((item) => [item.id, item.nodes.map((node) => node.target)]);
  });
  expect(violations).toEqual([]);
}

for (const width of [1440, 1024, 700, 390]) {
  test(
    'M5 knowledge and reviewed drafts at ' + width + 'px',
    async ({ page }, info) => {
      await page.setViewportSize({ width, height: 1000 });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await supportFixture(page);
      await page.route('**/api/v1/auth/me', async (route) =>
        route.fulfill({
          json: envelope({
            ...caseIdentity,
            role: 'manager',
            permissions: [
              ...caseIdentity.permissions,
              'knowledge:manage',
              'assistant:ask',
            ],
            capabilities: {
              ...caseIdentity.capabilities,
              knowledge: true,
              rag: true,
            },
          }),
        }),
      );
      await page.route('**/api/v1/knowledge/documents?**', async (route) =>
        route.fulfill({ json: envelope([doc]) }),
      );
      await page.route(
        '**/api/v1/knowledge/documents/' + docId + '*',
        async (route) => route.fulfill({ json: envelope(doc) }),
      );
      await page.route(
        '**/api/v1/knowledge/versions/' + revisionId,
        async (route) => route.fulfill({ json: envelope(version) }),
      );
      await page.route(
        '**/api/v1/knowledge/chunks/' + cited.chunk_id,
        async (route) => route.fulfill({ json: envelope(cited) }),
      );
      await page.route('**/api/v1/knowledge/availability', async (route) =>
        route.fulfill({
          json: envelope({
            source_search: true,
            indexing_worker_seen_at: now,
            generation_configured: true,
          }),
        }),
      );
      let payload: unknown;
      let posted = 0;
      let useful: boolean | null = null;
      page.on('request', (request) => {
        if (
          request.method() === 'POST' &&
          new URL(request.url()).pathname.endsWith('/messages')
        )
          posted += 1;
      });
      await page.route('**/api/v1/assistant/requests', async (route) => {
        payload = route.request().postDataJSON();
        return route.fulfill({
          status: 202,
          json: envelope({
            ...generated,
            state: 'queued',
            mode: null,
            answer_text: null,
            sources: [],
            completed_at: null,
          }),
        });
      });
      await page.route(
        '**/api/v1/assistant/requests/' + questionId,
        async (route) =>
          route.fulfill({ json: envelope({ ...generated, feedback: useful }) }),
      );
      await page.route(
        '**/api/v1/assistant/requests/' + questionId + '/feedback',
        async (route) => {
          useful = route.request().postDataJSON().helpful;
          return route.fulfill({
            json: envelope({ ...generated, feedback: useful }),
          });
        },
      );

      await page.goto('/app/knowledge');
      await expect(
        page.getByRole('table', { name: 'Knowledge articles' }),
      ).toBeVisible();
      await page.getByRole('link', { name: title, exact: true }).click();
      await expect(
        page.getByRole('heading', { name: 'Revision history' }),
      ).toBeVisible();
      await expect(page.getByText(excerpt, { exact: false })).toBeVisible();
      await expect(page.locator('main img')).toHaveCount(0);
      await accessibility(page);
      await page.screenshot({
        path: info.outputPath('knowledge.png'),
        fullPage: true,
      });

      await page.goto('/app/support/cases/' + syntheticCase.id);
      await page.getByRole('link', { name: 'Use knowledge' }).click();
      await page
        .getByLabel('Your question')
        .fill('When does the badge desk open?');
      await page.getByRole('button', { name: 'Find an answer' }).click();
      await expect(
        page.getByRole('heading', { name: 'Draft answer' }),
      ).toBeVisible();
      expect(payload).toEqual({
        question: 'When does the badge desk open?',
        case_id: syntheticCase.id,
      });
      expect(page.url()).not.toContain('badge');
      await page.getByRole('button', { name: 'Helpful', exact: true }).click();
      await expect(
        page.getByRole('button', { name: 'Helpful', exact: true }),
      ).toHaveAttribute('aria-pressed', 'true');
      await accessibility(page);
      await page.screenshot({
        path: info.outputPath('copilot.png'),
        fullPage: true,
      });

      const citation = page.getByRole('link', {
        name: '[S1] · ' + title,
        exact: true,
      });
      await citation.focus();
      await page.keyboard.press('Enter');
      await expect(
        page.getByRole('region', { name: 'Source passage' }).getByText(excerpt),
      ).toBeVisible();
      await expect(page.locator('main img')).toHaveCount(0);
      await page.goBack();
      await page
        .getByRole('button', { name: 'Use draft', exact: true })
        .click();
      await expect(page.getByLabel('Public reply message')).toHaveValue(text);
      expect(posted).toBe(0);
      await page
        .getByRole('button', { name: 'Send reply', exact: true })
        .click();
      await expect(
        page
          .getByRole('list', { name: 'Conversation' })
          .getByText(text, { exact: true }),
      ).toBeVisible();
      expect(posted).toBe(1);
    },
  );
}
