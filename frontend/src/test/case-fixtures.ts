import type {
  CaseConfig,
  CaseDetail,
  CaseMessage,
  PortalCase,
  PortalConfig,
  PortalSummary,
} from '../features/support/data';
import { contact, customer, identity, member } from './fixtures';

// Entirely synthetic fixtures, imported only by tests.
export const caseIdentity = {
  ...identity,
  permissions: [
    ...identity.permissions,
    'cases:read',
    'cases:write',
    'cases:close',
  ],
  capabilities: { ...identity.capabilities, cases: true, demo: true },
};
export const config: CaseConfig = {
  id: '66666666-6666-4666-8666-666666666666',
  version: 1,
  number: 1,
  status: 'published',
  published_at: customer.created_at,
  definition: {
    categories: [
      { key: 'access', label: 'Access', default_team_id: null },
      { key: 'product_issue', label: 'Product issue', default_team_id: null },
    ],
    priorities: {
      urgent: { response_minutes: 60, resolution_minutes: 480 },
      high: { response_minutes: 240, resolution_minutes: 1440 },
      normal: { response_minutes: 480, resolution_minutes: 2880 },
      low: { response_minutes: 1440, resolution_minutes: 5760 },
    },
    state_labels: {
      new: 'New',
      open: 'Open',
      pending_customer: 'Awaiting customer',
      resolved: 'Resolved',
      closed: 'Closed',
    },
    fields: [],
    portal_default_priority: 'normal',
  },
};
export const portalConfiguration: PortalConfig = {
  categories: [
    { key: 'access', label: 'Access' },
    { key: 'product_issue', label: 'Product issue' },
  ],
  state_labels: config.definition.state_labels,
  fields: [],
};
export const syntheticCase: CaseDetail = {
  id: '77777777-7777-4777-8777-777777777777',
  number: 1,
  version: 1,
  subject: 'Synthetic access request',
  state: 'new',
  state_label: 'New',
  category_key: 'access',
  category_label: 'Access',
  priority: 'normal',
  customer: { id: customer.id, name: customer.name },
  requester: { id: contact.id, name: contact.name },
  team: null,
  assignee: null,
  unread: true,
  created_at: customer.created_at,
  updated_at: customer.updated_at,
  last_message_at: customer.created_at,
  config_version_id: config.id,
  source: 'portal',
  custom_values: {},
  field_definitions: [],
  first_response_at: null,
  first_response_target_at: '2026-11-08T18:00:00Z',
  first_response_status: {
    status: 'due',
    elapsed_seconds: 3600,
    remaining_seconds: 25200,
    target_seconds: 28800,
    is_overdue: false,
    due_at: '2026-11-08T18:00:00Z',
  },
  target_status: {
    status: 'due',
    elapsed_seconds: 3600,
    remaining_seconds: 169200,
    target_seconds: 172800,
    is_overdue: false,
    due_at: '2026-11-10T10:00:00Z',
  },
  current_cycle: {
    cycle_number: 1,
    opened_at: customer.created_at,
    target_seconds: 172800,
    paused_seconds: 0,
    pause_started_at: null,
    resolved_at: null,
    resolution_code: null,
    resolution_summary: null,
  },
  cycles: [
    {
      cycle_number: 1,
      opened_at: customer.created_at,
      target_seconds: 172800,
      paused_seconds: 0,
      pause_started_at: null,
      resolved_at: null,
      resolution_code: null,
      resolution_summary: null,
    },
  ],
  related_case_id: null,
};
export const initialMessage: CaseMessage = {
  id: '88888888-8888-4888-8888-888888888888',
  sequence: 1,
  body: 'Synthetic customer request: I cannot access the project.',
  author_display: contact.name,
  author_kind: 'contact',
  visibility: 'public',
  message_kind: 'initial',
  created_at: customer.created_at,
  updated_case_version: 1,
};

export function publicSummary(row: CaseDetail): PortalSummary {
  return {
    id: row.id,
    number: row.number,
    version: row.version,
    subject: row.subject,
    category_label: row.category_label,
    state: row.state,
    state_label: row.state_label,
    created_at: row.created_at,
  };
}
export function publicCase(row: CaseDetail): PortalCase {
  return {
    ...publicSummary(row),
    custom_values: {},
    field_definitions: [],
    latest_public_resolution: row.current_cycle.resolution_summary,
    current_cycle_number: row.current_cycle.cycle_number,
    can_reply: ['new', 'open', 'pending_customer'].includes(row.state),
    can_reopen: row.state === 'resolved',
    can_rate: false,
    related_case_id: row.related_case_id,
  };
}
export { contact, customer, member };
