import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api, apiPages } from '../../api/client';
import type { Contact, Workspace } from '../../api/client';
import { ErrorMessage, Loading } from '../../components/Feedback';
import { UnsavedChanges, ValidationSummary } from '../../components/FormSafety';
import { useSession } from '../identity/session';
import { CustomFields, CustomerPicker } from './components';
import {
  customValues,
  reference,
  useHeadingFocus,
  useReplayKeys,
} from './data';
import type {
  CaseConfig,
  CaseDetail,
  CaseField,
  PortalCase,
  PortalConfig,
} from './data';

const schema = z.object({
  category_key: z.string().min(1, 'Choose a category.'),
  subject: z.string().trim().min(1, 'Enter a subject.').max(200),
  description: z.string().trim().min(1, 'Describe the request.').max(10000),
  priority: z.enum(['urgent', 'high', 'normal', 'low']),
  source: z.enum(['manual_phone', 'manual_email', 'manual_other']),
});
type Values = z.infer<typeof schema>;

export function CreateCase({ portal = false }: { portal?: boolean }) {
  const { identity } = useSession();
  const [params] = useSearchParams();
  const [selectedCustomer, setCustomer] = useState<string | null>(null);
  const [selectedContact, setContact] = useState<string | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [referenceErrors, setReferenceErrors] = useState<
    { field: string; message: string }[]
  >([]);
  const [customDirty, setCustomDirty] = useState(false);
  const navigate = useNavigate();
  const client = useQueryClient();
  const keys = useReplayKeys();
  const workspace = useQuery({
    queryKey: [identity?.workspace_id, 'staff', 'workspace'],
    queryFn: ({ signal }) => api<Workspace>('/workspace', { signal }),
    enabled: !portal,
  });
  const configs = useQuery({
    queryKey: [identity?.workspace_id, 'staff', 'case-configs'],
    queryFn: ({ signal }) => api<CaseConfig[]>('/case-configs', { signal }),
    enabled: !portal,
  });
  const portalConfig = useQuery({
    queryKey: [identity?.workspace_id, 'portal', 'config'],
    queryFn: ({ signal }) => api<PortalConfig>('/portal/config', { signal }),
    enabled: portal,
  });
  const relatedId = params.get('related');
  const related = useQuery({
    queryKey: [
      identity?.workspace_id,
      portal ? 'portal' : 'staff',
      'related-case',
      relatedId,
    ],
    queryFn: ({ signal }) =>
      api<CaseDetail | PortalCase>(
        `${portal ? '/portal' : ''}/cases/${relatedId}`,
        { signal },
      ),
    enabled: !!relatedId,
  });
  const relatedStaff =
    related.data?.data && 'customer' in related.data.data
      ? related.data.data
      : undefined;
  const customerId =
    selectedCustomer ??
    params.get('customer') ??
    relatedStaff?.customer.id ??
    '';
  const contactId =
    selectedContact ??
    (relatedStaff?.customer.id === customerId ? relatedStaff.requester.id : '');
  const contacts = useQuery({
    queryKey: [identity?.workspace_id, 'staff', 'contact-options', customerId],
    queryFn: ({ signal }) =>
      apiPages<Contact>(`/contacts?customer_id=${customerId}`, signal),
    enabled: !portal && !!customerId,
  });
  const {
    register,
    handleSubmit,
    formState: { errors, isDirty, isSubmitting, submitCount },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    shouldFocusError: false,
    defaultValues: {
      category_key: '',
      subject: '',
      description: '',
      priority: 'normal',
      source: 'manual_other',
    },
  });
  const configuration = configs.data?.data.find(
    (row) => row.id === workspace.data?.data.active_case_config_id,
  )?.definition;
  const categories = portal
    ? portalConfig.data?.data.categories
    : configuration?.categories;
  const fields: CaseField[] = portal
    ? (portalConfig.data?.data.fields ?? [])
    : (configuration?.fields ?? []).map((field) => ({
        key: field.key,
        label: field.label,
        type: field.type,
        required_on_create: field.required_on_create ?? false,
        portal_editable_on_create: field.portal_editable_on_create ?? false,
        allowed_values: field.allowed_values ?? [],
        minimum: field.minimum ?? null,
        maximum: field.maximum ?? null,
      }));
  const loading = portal
    ? portalConfig.isPending
    : configs.isPending || workspace.isPending;
  const failure =
    portalConfig.error ?? configs.error ?? workspace.error ?? related.error;
  useHeadingFocus(
    'page-heading',
    !loading && !!categories && (!relatedId || !!related.data),
  );
  if (loading || (relatedId && related.isPending))
    return <Loading label="Loading request form..." />;
  if (failure) return <ErrorMessage error={failure} />;
  if (!categories)
    return (
      <p role="alert">
        Case configuration is unavailable. Ask a workspace administrator.
      </p>
    );
  if (!portal && !identity?.permissions.includes('cases:write'))
    return <p>You don’t have permission to create a case.</p>;
  const back = portal ? '/portal' : '/app/support/inbox';
  return (
    <div className={portal ? 'portal-reading' : ''}>
      <UnsavedChanges
        dirty={
          (isDirty ||
            customDirty ||
            selectedCustomer !== null ||
            selectedContact !== null) &&
          !isSubmitting
        }
      />
      <Link to={back}>
        {portal ? 'Back to your requests' : 'Back to inbox'}
      </Link>
      <h1 id="page-heading" tabIndex={-1}>
        {portal ? 'How can we help?' : 'Create case'}
      </h1>
      <p className="small-reading">
        {portal
          ? 'Describe the issue and what you expected to happen.'
          : 'Record a customer request. Public replies appear in the customer portal.'}
      </p>
      {related.data && (
        <p>
          Related to{' '}
          <Link
            to={
              portal
                ? `/portal/requests/${relatedId}`
                : `/app/support/cases/${relatedId}`
            }
          >
            {reference(related.data.data.number)} · {related.data.data.subject}
          </Link>
        </p>
      )}
      <form
        className="work-surface form-surface"
        noValidate
        onChange={(event) => {
          if (
            event.target instanceof HTMLElement &&
            event.target.getAttribute('name')?.startsWith('field-')
          )
            setCustomDirty(true);
        }}
        onSubmit={(event) => {
          const formElement = event.currentTarget;
          void handleSubmit(async (values) => {
            setError(null);
            const missing = !portal
              ? [
                  ...(!customerId
                    ? [
                        {
                          field: 'customer-choice',
                          message: 'Choose a customer.',
                        },
                      ]
                    : []),
                  ...(!contactId
                    ? [
                        {
                          field: 'requester-contact',
                          message: 'Choose the requesting contact.',
                        },
                      ]
                    : []),
                ]
              : [];
            setReferenceErrors(missing);
            if (missing.length) return;
            const path = portal ? '/portal/cases' : '/cases';
            const body = {
              category_key: values.category_key,
              subject: values.subject,
              description: values.description,
              custom_values: customValues(formElement, fields),
              ...(relatedId ? { related_case_id: relatedId } : {}),
              ...(!portal
                ? {
                    customer_id: customerId,
                    requester_contact_id: contactId,
                    priority: values.priority,
                    source: values.source,
                  }
                : {}),
            };
            try {
              const response = await api<CaseDetail | PortalCase>(path, {
                method: 'POST',
                body,
                idempotencyKey: keys.keyFor(path, body),
              });
              keys.completed(path, body);
              await client.invalidateQueries({
                queryKey: [
                  identity?.workspace_id,
                  portal ? 'portal' : 'staff',
                  'cases',
                ],
              });
              navigate(
                portal
                  ? `/portal/requests/${response.data.id}`
                  : `/app/support/cases/${response.data.id}`,
                {
                  state: {
                    notice: portal ? 'Request submitted.' : 'Case created.',
                  },
                },
              );
            } catch (cause) {
              setError(cause as Error);
            }
          })(event);
        }}
      >
        <ErrorMessage error={error} />
        <ValidationSummary
          submitCount={submitCount}
          messages={[
            ...Object.entries(errors).map(([field, value]) => ({
              field,
              message: value.message ?? 'Review this field.',
            })),
            ...referenceErrors,
          ]}
        />
        {!portal && (
          <>
            <CustomerPicker
              value={customerId}
              onChange={(id) => {
                setCustomer(id);
                setContact('');
              }}
            />
            <label htmlFor="requester-contact">Requesting contact</label>
            <select
              id="requester-contact"
              value={contactId}
              onChange={(event) => setContact(event.target.value)}
              disabled={!customerId || contacts.isPending}
            >
              <option value="">Choose a contact</option>
              {contacts.data?.data
                .filter((row) => !row.archived_at)
                .map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.name}
                  </option>
                ))}
            </select>
            {contacts.error && <ErrorMessage error={contacts.error} />}
          </>
        )}
        <label htmlFor="category_key">Category</label>
        <select
          id="category_key"
          {...register('category_key')}
          aria-invalid={!!errors.category_key}
          aria-describedby={errors.category_key ? 'category-error' : undefined}
        >
          <option value="">Choose a category</option>
          {categories.map((row) => (
            <option key={row.key} value={row.key}>
              {row.label}
            </option>
          ))}
        </select>
        {errors.category_key && (
          <p id="category-error">{errors.category_key.message}</p>
        )}
        <label htmlFor="subject">Subject</label>
        <input
          id="subject"
          {...register('subject')}
          maxLength={200}
          aria-invalid={!!errors.subject}
          aria-describedby={errors.subject ? 'subject-error' : undefined}
        />
        {errors.subject && <p id="subject-error">{errors.subject.message}</p>}
        <label htmlFor="description">
          {portal ? 'Description' : 'Initial public description'}
        </label>
        <textarea
          id="description"
          {...register('description')}
          maxLength={10000}
          aria-invalid={!!errors.description}
          aria-describedby={
            errors.description ? 'description-error' : undefined
          }
        />
        {errors.description && (
          <p id="description-error">{errors.description.message}</p>
        )}
        {!portal && (
          <>
            <label htmlFor="priority">Priority</label>
            <select id="priority" {...register('priority')}>
              {['urgent', 'high', 'normal', 'low'].map((value) => (
                <option key={value} value={value}>
                  {value.charAt(0).toUpperCase() + value.slice(1)}
                </option>
              ))}
            </select>
            <label htmlFor="source">Request origin</label>
            <select id="source" {...register('source')}>
              <option value="manual_other">Other · Logged manually</option>
              <option value="manual_phone">Phone · Logged manually</option>
              <option value="manual_email">Email · Logged manually</option>
            </select>
          </>
        )}
        <CustomFields fields={fields} />
        <div className="form-actions">
          <button
            className="button"
            disabled={isSubmitting || (!portal && !!contacts.error)}
          >
            {isSubmitting
              ? 'Submitting...'
              : portal
                ? 'Submit request'
                : 'Create case'}
          </button>
          <Link to={back}>Cancel</Link>
        </div>
      </form>
    </div>
  );
}
