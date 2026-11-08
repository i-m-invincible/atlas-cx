import { UnsavedChanges, ValidationSummary } from '../../components/FormSafety';
import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Temporal } from '@js-temporal/polyfill';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, ApiError } from '../../api/client';
import type { Customer, Member } from '../../api/client';
import { ErrorMessage, Loading } from '../../components/Feedback';
import { useSession } from '../identity/session';

const schema = z.object({
  name: z.string().trim().min(1, 'Enter the customer name.').max(160),
  kind: z.enum(['person', 'business']),
  lifecycle: z.enum(['prospect', 'active', 'inactive']),
  external_id: z.string().trim().max(120),
  owner_member_id: z.string(),
  tags: z.string().max(820),
  activity_expected: z.boolean(),
  tracking_started_at: z.string(),
});
type Values = z.infer<typeof schema>;

export function CustomerForm() {
  const { id } = useParams();
  const { identity } = useSession();
  const query = useQuery({
    queryKey: [identity?.workspace_id, 'staff', 'customer', id],
    queryFn: ({ signal }) => api<Customer>(`/customers/${id}`, { signal }),
    enabled: !!id,
  });
  if (id && query.isPending) return <Loading label="Loading customer…" />;
  if (query.error) return <ErrorMessage error={query.error} />;
  if (!identity?.permissions.includes('customers:write'))
    return <p>You don’t have permission to edit customers.</p>;
  return <CustomerEditor key={id ?? 'new'} customer={query.data?.data} />;
}

function CustomerEditor({ customer }: { customer?: Customer }) {
  const { identity } = useSession();
  const navigate = useNavigate();
  const client = useQueryClient();
  const [error, setError] = useState<Error | null>(null);
  const [saveVersion, setSaveVersion] = useState(customer?.version);
  const [latest, setLatest] = useState<Customer | null>(null);
  const timezone = identity?.timezone ?? 'Asia/Kolkata';
  const members = useQuery({
    queryKey: [identity?.workspace_id, 'staff', 'members'],
    queryFn: ({ signal }) =>
      api<Member[]>('/members?active=true&limit=100', { signal }),
  });
  const form = useForm<Values>({
    shouldFocusError: false,
    resolver: zodResolver(schema),
    defaultValues: {
      name: customer?.name ?? '',
      kind: customer?.kind === 'person' ? 'person' : 'business',
      lifecycle:
        customer?.lifecycle === 'inactive'
          ? 'inactive'
          : customer?.lifecycle === 'prospect'
            ? 'prospect'
            : 'active',
      external_id: customer?.external_id ?? '',
      owner_member_id: customer?.owner_member_id ?? '',
      tags: customer?.tags.join(', ') ?? '',
      activity_expected: customer?.activity_expected ?? false,
      tracking_started_at: customer?.tracking_started_at
        ? Temporal.Instant.from(customer.tracking_started_at)
            .toZonedDateTimeISO(timezone)
            .toPlainDateTime()
            .toString({ smallestUnit: 'minute' })
        : '',
    },
  });
  const {
    register,
    handleSubmit,
    setError: fieldError,
    formState: { errors, isSubmitting, isDirty, submitCount },
  } = form;
  const back = customer ? `/app/customers/${customer.id}` : '/app/customers';
  return (
    <>
      <UnsavedChanges dirty={isDirty && !isSubmitting} />
      <Link to={back}>Back to {customer ? 'customer' : 'customers'}</Link>
      <h1 id="page-heading" tabIndex={-1}>
        {customer ? 'Edit customer' : 'Add customer'}
      </h1>
      <p className="small-reading">Required: customer name and type.</p>
      <form
        className="work-surface form-surface"
        onSubmit={handleSubmit(async (values) => {
          setError(null);
          let tracking: string | null = null;
          try {
            if (values.tracking_started_at)
              tracking = Temporal.PlainDateTime.from(values.tracking_started_at)
                .toZonedDateTime(timezone, { disambiguation: 'reject' })
                .toInstant()
                .toString();
          } catch {
            fieldError('tracking_started_at', {
              message:
                'Choose a valid, unambiguous time in the workspace time zone.',
            });
            return;
          }
          const tags = values.tags
            .split(',')
            .map((tag) => tag.trim())
            .filter(Boolean);
          if (
            tags.length > 20 ||
            new Set(tags).size !== tags.length ||
            tags.some((tag) => tag.length > 40)
          ) {
            fieldError('tags', {
              message: 'Use up to 20 unique tags, each at most 40 characters.',
            });
            return;
          }
          const body: Record<string, unknown> = {
            name: values.name,
            lifecycle: values.lifecycle,
            owner_member_id: values.owner_member_id || null,
            tags,
            activity_expected: values.activity_expected,
            tracking_started_at: tracking,
          };
          if (!customer) {
            body.kind = values.kind;
            body.external_id = values.external_id || null;
          } else if (!customer.external_id && values.external_id)
            body.external_id = values.external_id;
          try {
            const response = await api<Customer>(
              customer ? `/customers/${customer.id}` : '/customers',
              {
                method: customer ? 'PATCH' : 'POST',
                version: saveVersion,
                body,
              },
            );
            await client.invalidateQueries({
              queryKey: [identity?.workspace_id, 'staff', 'customers'],
            });
            client.setQueryData(
              [identity?.workspace_id, 'staff', 'customer', response.data.id],
              response,
            );
            navigate(`/app/customers/${response.data.id}`, {
              state: {
                notice: customer ? 'Customer updated.' : 'Customer added.',
              },
            });
          } catch (failure) {
            setError(failure as Error);
          }
        })}
        noValidate
      >
        <ErrorMessage error={error} />
        <ValidationSummary
          submitCount={submitCount}
          messages={Object.entries(errors).map(([field, value]) => ({
            field,
            message: value.message ?? 'Check this field.',
          }))}
        />
        {error instanceof ApiError &&
          error.problem.code === 'version_conflict' && (
            <section
              className="ruled-section"
              aria-label="Review customer conflict"
            >
              <p>
                Your draft is still here. Review the latest saved record before
                applying it.
              </p>
              <button
                className="button secondary"
                type="button"
                onClick={async () => {
                  try {
                    setLatest(
                      (await api<Customer>(`/customers/${customer!.id}`)).data,
                    );
                  } catch (failure) {
                    setError(failure as Error);
                  }
                }}
              >
                Review latest customer
              </button>
              {latest && (
                <>
                  <h2>Latest saved customer � Version {latest.version}</h2>
                  <dl className="record-details">
                    <dt>Name</dt>
                    <dd>{latest.name}</dd>
                    <dt>Lifecycle</dt>
                    <dd>{latest.lifecycle}</dd>
                    <dt>Owner</dt>
                    <dd>{latest.owner_name ?? 'Unassigned'}</dd>
                    <dt>External ID</dt>
                    <dd>{latest.external_id ?? 'Not recorded'}</dd>
                    <dt>Tags</dt>
                    <dd>{latest.tags.join(', ') || 'None recorded'}</dd>
                  </dl>
                  <button
                    className="button secondary"
                    type="button"
                    onClick={() => {
                      setSaveVersion(latest.version);
                      setLatest(null);
                      setError(null);
                    }}
                  >
                    Keep my draft for version {latest.version}
                  </button>
                  <p>
                    Review your fields, then choose Save customer. This does not
                    save automatically.
                  </p>
                </>
              )}
            </section>
          )}
        {isDirty && <p className="small-reading">Unsaved changes</p>}
        <label htmlFor="name">Customer name</label>
        <input
          id="name"
          {...register('name')}
          aria-invalid={!!errors.name}
          aria-describedby="name-error"
        />
        <p id="name-error" className="field-error">
          {errors.name?.message}
        </p>
        <label htmlFor="kind">Type</label>
        <select id="kind" {...register('kind')} disabled={!!customer}>
          <option value="business">Business</option>
          <option value="person">Person</option>
        </select>
        <label htmlFor="lifecycle">Lifecycle</label>
        <select id="lifecycle" {...register('lifecycle')}>
          <option value="prospect">Prospect</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
        <label htmlFor="owner_member_id">Owner · Optional</label>
        <select id="owner_member_id" {...register('owner_member_id')}>
          <option value="">Unassigned</option>
          {members.data?.data
            .filter((member) => member.role !== 'viewer')
            .map((member) => (
              <option key={member.id} value={member.id}>
                {member.display_name}
              </option>
            ))}
        </select>
        <label htmlFor="external_id">External ID · Optional</label>
        <input
          id="external_id"
          {...register('external_id')}
          readOnly={!!customer?.external_id}
          aria-describedby="external-help"
        />
        <p id="external-help" className="small-reading">
          An existing external ID stays attached to this customer.
        </p>
        <label htmlFor="tags">Tags · Optional</label>
        <input
          id="tags"
          {...register('tags')}
          aria-invalid={!!errors.tags}
          aria-describedby="tags-help tags-error"
        />
        <p id="tags-help" className="small-reading">
          Separate tags with commas. Up to 20 unique tags.
        </p>
        <p id="tags-error" className="field-error">
          {errors.tags?.message}
        </p>
        <fieldset>
          <legend>Activity tracking · Optional</legend>
          <label className="checkbox-label">
            <input type="checkbox" {...register('activity_expected')} />
            Expect product activity
          </label>
          <label htmlFor="tracking_started_at">Tracking began</label>
          <input
            id="tracking_started_at"
            type="datetime-local"
            {...register('tracking_started_at')}
            aria-invalid={!!errors.tracking_started_at}
            aria-describedby="tracking-help tracking-error"
          />
          <p id="tracking-help" className="small-reading">
            Time zone: {timezone}. Set this only when tracking actually began.
            Event ingestion is planned for a later milestone.
          </p>
          <p id="tracking-error" className="field-error">
            {errors.tracking_started_at?.message}
          </p>
        </fieldset>
        <div className="form-actions">
          <button
            className="button"
            disabled={isSubmitting || !!customer?.archived_at}
          >
            {isSubmitting
              ? 'Saving…'
              : customer
                ? 'Save customer'
                : 'Add customer'}
          </button>
          <Link to={back}>Cancel</Link>
        </div>
      </form>
    </>
  );
}
