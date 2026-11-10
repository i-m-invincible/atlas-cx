import type { CaseDetail, CaseMessage } from '../features/support/data';
import {
  config,
  initialMessage,
  syntheticCase,
  publicCase,
  publicSummary,
  portalConfiguration,
  member,
  contact,
  customer,
} from './case-fixtures';
import { envelope } from './fixtures';

type Input = Record<string, unknown>;
export type CaseRequest = {
  path: string;
  method: string;
  body: Input;
  headers: Record<string, string>;
};
type Reply = { status: number; json: unknown };

// A deterministic test double for UI states. PostgreSQL/API tests independently
// verify the actual state machine and authorization; this is not production code.
export class CaseServer {
  row: CaseDetail = structuredClone(syntheticCase);
  messages: CaseMessage[] = [structuredClone(initialMessage)];
  requests: CaseRequest[] = [];
  failMessage = false;
  conflictMessage = false;
  empty = false;
  missing = false;
  delayMessage: Promise<void> | null = null;
  private replays = new Map<string, Reply>();

  async respond(
    url: string,
    method = 'GET',
    body: Input = {},
    headers: Record<string, string> = {},
    portal = false,
  ): Promise<Reply> {
    const parsed = new URL(url, 'http://localhost');
    const path = parsed.pathname.replace('/api/v1', '');
    const ok = (json: unknown, status = 200): Reply => ({
      status,
      json: envelope(json),
    });
    const fail = (status: number, code: string, detail: string): Reply => ({
      status,
      json: { status, code, detail, request_id: 'synthetic-case-request' },
    });
    if (method !== 'GET') this.requests.push({ path, method, body, headers });
    if (path === '/auth/csrf') return ok({ csrf_token: 'synthetic-case-csrf' });
    if (path === '/members') return ok([member]);
    if (path === '/teams') return ok([]);
    if (path === '/workspace')
      return ok({
        id: customer.id,
        version: 1,
        name: 'Synthetic workspace',
        slug: 'synthetic',
        timezone: 'Asia/Kolkata',
        active_case_config_id: config.id,
        feedback_manager_member_id: member.id,
      });
    if (path === '/case-configs') return ok([config]);
    if (path === `/case-configs/${config.id}`) return ok(config);
    if (path === '/portal/config') return ok(portalConfiguration);
    if (path === '/customers') return ok([customer]);
    if (path === `/customers/${customer.id}`) return ok(customer);
    if (path === '/contacts') return ok([contact]);
    if (path === `/contacts/${contact.id}`) return ok(contact);
    const prefix = path.startsWith('/portal/') ? '/portal/cases' : '/cases';
    if (path === prefix && method === 'GET') {
      const q = parsed.searchParams.get('q')?.toLowerCase() ?? '';
      const view = parsed.searchParams.get('view');
      const state = parsed.searchParams.get('state');
      const priority = parsed.searchParams.get('priority');
      const matches =
        !this.empty &&
        this.row.subject.toLowerCase().includes(q) &&
        (!state || state === this.row.state) &&
        (!priority || priority === this.row.priority) &&
        (view !== 'unassigned' || !this.row.assignee);
      return ok(
        matches
          ? [prefix.includes('portal') ? publicSummary(this.row) : this.row]
          : [],
      );
    }
    if (path === prefix && method === 'POST') {
      this.empty = false;
      this.row.subject = String(body.subject);
      this.row.category_key = String(body.category_key);
      this.messages = [{ ...initialMessage, body: String(body.description) }];
      return ok(
        prefix.includes('portal') ? publicCase(this.row) : this.row,
        201,
      );
    }
    if (!path.startsWith(`${prefix}/${this.row.id}`))
      return fail(404, 'not_found', 'This request isn’t available.');
    if (this.missing)
      return fail(404, 'not_found', 'This request isn’t available.');
    const detail = `${prefix}/${this.row.id}`;
    if (path === detail && method === 'GET')
      return ok(prefix.includes('portal') ? publicCase(this.row) : this.row);
    if (path.endsWith('/messages') && method === 'GET')
      return ok(
        this.messages
          .filter(
            (message) =>
              !prefix.includes('portal') || message.visibility === 'public',
          )
          .map((message) =>
            prefix.includes('portal')
              ? {
                  ...message,
                  author_display:
                    message.author_kind === 'contact' ? 'You' : 'Support team',
                }
              : message,
          ),
      );
    if (path.endsWith('/history')) return ok([]);
    if (path.endsWith('/read-marker')) {
      this.row.unread = false;
      return ok(body);
    }
    if (method === 'GET')
      return fail(404, 'not_found', 'This request isn’t available.');
    if (method === 'PATCH') {
      if (headers['If-Match'] !== `"${this.row.version}"`)
        return fail(409, 'version_conflict', 'This record changed.');
      this.row.version += 1;
      if (body.priority)
        this.row.priority = body.priority as CaseDetail['priority'];
      this.row.assignee = body.assignee_member_id
        ? { id: member.id, name: member.display_name }
        : null;
      return ok(this.row);
    }
    const key = headers['Idempotency-Key'] ?? '';
    const replayKey = path + ':' + key;
    if (this.replays.has(replayKey)) return this.replays.get(replayKey)!;
    if (this.delayMessage && path.endsWith('/messages'))
      await this.delayMessage;
    if (this.failMessage && path.endsWith('/messages')) {
      this.failMessage = false;
      return fail(
        503,
        'dependency_unavailable',
        'Your reply could not be posted.',
      );
    }
    if (this.conflictMessage && path.endsWith('/messages')) {
      this.conflictMessage = false;
      this.row.version += 1;
      return fail(
        409,
        'version_conflict',
        'This case changed. Review the latest version.',
      );
    }
    if (headers['If-Match'] !== `"${this.row.version}"`)
      return fail(409, 'version_conflict', 'This case changed.');
    this.row.version += 1;
    const action = String(
      body.action ?? (path.endsWith('/reopen') ? 'reopen' : ''),
    );
    if (action === 'triage') {
      this.row.assignee = { id: member.id, name: member.display_name };
      this.row.state = 'open';
    }
    if (action === 'ask_customer') {
      this.row.state = 'pending_customer';
      this.row.target_status = {
        ...this.row.target_status,
        status: 'paused',
        due_at: null,
      };
    }
    if (action === 'resume') this.row.state = 'open';
    if (action === 'resolve') {
      this.row.state = 'resolved';
      this.row.current_cycle.resolved_at = '2026-11-08T12:00:00Z';
      this.row.current_cycle.resolution_summary = String(
        body.resolution_summary,
      );
      this.row.current_cycle.resolution_code = String(body.resolution_code);
      this.row.target_status = {
        ...this.row.target_status,
        status: 'met',
        due_at: null,
      };
    }
    if (action === 'reopen') {
      this.row.state = 'open';
      this.row.current_cycle = {
        ...this.row.current_cycle,
        cycle_number: this.row.current_cycle.cycle_number + 1,
        paused_seconds: 0,
        pause_started_at: null,
        resolved_at: null,
        resolution_summary: null,
        resolution_code: null,
      };
      this.row.cycles.push(this.row.current_cycle);
    }
    if (action === 'close') this.row.state = 'closed';
    let added: CaseMessage | undefined;
    const text = body.body ?? body.message ?? body.resolution_summary;
    if (text) {
      const internal = body.visibility === 'internal';
      if (!internal && !portal && this.row.state === 'new') {
        this.row.state = 'open';
        this.row.assignee = { id: member.id, name: member.display_name };
      }
      if (portal && this.row.state === 'pending_customer')
        this.row.state = 'open';
      added = {
        id: crypto.randomUUID(),
        sequence: this.messages.length + 1,
        body: String(text),
        author_display: portal ? 'You' : member.display_name,
        author_kind: portal ? 'contact' : 'staff',
        visibility: internal ? 'internal' : 'public',
        message_kind: internal
          ? 'note'
          : action === 'resolve'
            ? 'resolution'
            : action === 'ask_customer'
              ? 'info_request'
              : action === 'reopen'
                ? 'reopen'
                : 'reply',
        created_at: '2026-11-08T11:00:00Z',
        updated_case_version: this.row.version,
      };
      this.messages.push(added);
    }
    this.row.state_label =
      config.definition.state_labels[this.row.state] ?? this.row.state;
    const response = ok(
      path.endsWith('/messages')
        ? added
        : prefix.includes('portal')
          ? publicCase(this.row)
          : {
              case: this.row,
              transition_id: crypto.randomUUID(),
              message_id: added?.id ?? null,
            },
    );
    this.replays.set(replayKey, structuredClone(response));
    return response;
  }
}
