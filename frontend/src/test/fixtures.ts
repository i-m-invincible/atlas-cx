import type { Contact, Customer, Identity, Member } from '../api/client';

// Synthetic test fixtures only. These are never imported by the application.
export const identity: Identity = {
  user_id: '11111111-1111-4111-8111-111111111111',
  workspace_id: '22222222-2222-4222-8222-222222222222',
  workspace_name: 'Synthetic workspace',
  workspace_slug: 'synthetic',
  display_name: 'Synthetic agent',
  email: 'agent@example.com',
  timezone: 'Asia/Kolkata',
  audience: 'staff',
  role: 'admin',
  member_id: '33333333-3333-4333-8333-333333333333',
  contact_id: null,
  permissions: [
    'customers:read',
    'customers:write',
    'customers:archive',
    'workspace:manage',
  ],
  capabilities: { customers: true, cases: false, rag: false },
};
export const customer: Customer = {
  id: '44444444-4444-4444-8444-444444444444',
  name: 'Synthetic customer',
  kind: 'business',
  lifecycle: 'active',
  external_id: 'synthetic-001',
  owner_member_id: identity.member_id,
  owner_name: identity.display_name,
  tags: ['pilot'],
  activity_expected: false,
  tracking_started_at: null,
  version: 1,
  created_at: '2026-11-08T10:00:00Z',
  updated_at: '2026-11-08T10:00:00Z',
  archived_at: null,
  latest_health: null,
  last_meaningful_activity_at: null,
};
export const member: Member = {
  id: identity.member_id!,
  user_id: identity.user_id,
  display_name: identity.display_name,
  email: identity.email,
  role: 'admin',
  active: true,
  version: 1,
  created_at: customer.created_at,
};
export const contact: Contact = {
  id: '55555555-5555-4555-8555-555555555555',
  customer_id: customer.id,
  name: 'Synthetic contact',
  email: 'contact@example.com',
  phone: null,
  archived_at: null,
  portal_enabled: false,
  version: 1,
  created_at: customer.created_at,
  updated_at: customer.created_at,
};
export function envelope<T>(
  data: T,
  more = false,
  cursor: string | null = null,
) {
  return {
    data,
    meta: {
      request_id: 'synthetic-test-request',
      has_more: more,
      next_cursor: cursor,
    },
  };
}
