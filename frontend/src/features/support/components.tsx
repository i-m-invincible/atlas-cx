import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, ApiError } from '../../api/client';
import type { ApiEnvelope, Customer } from '../../api/client';
import { ErrorMessage } from '../../components/Feedback';
import { useSession } from '../identity/session';
import { stateLabels } from './data';
import type { CaseField } from './data';

export function ConflictReview<T extends { version: number; state?: string }>({
  error,
  path,
  accept,
  record = 'case',
}: {
  error: Error | null;
  path: string;
  accept: (latest: ApiEnvelope<T>) => void;
  record?: 'case' | 'follow-up' | 'configuration';
}) {
  const [latest, setLatest] = useState<ApiEnvelope<T> | null>(null);
  const [failure, setFailure] = useState<Error | null>(null);
  if (!(error instanceof ApiError) || error.problem.code !== 'version_conflict')
    return null;
  return (
    <section
      className="conflict-review"
      aria-label={'Review ' + record + ' conflict'}
    >
      <p>
        This {record} changed while you were editing. Your draft is still here.
      </p>
      <button
        className="button secondary"
        type="button"
        onClick={async () => {
          try {
            setLatest(await api<T>(path));
            setFailure(null);
          } catch (cause) {
            setFailure(cause as Error);
          }
        }}
      >
        Review latest {record}
      </button>
      <ErrorMessage error={failure} />
      {latest && (
        <>
          <p>
            Saved version {latest.data.version}
            {latest.data.state
              ? ` · ${stateLabels[latest.data.state] ?? latest.data.state.replaceAll('_', ' ')}`
              : ''}
            .
            {record === 'case'
              ? ' Review the latest conversation and details before saving.'
              : ' Review the latest details before saving.'}
          </p>
          <button
            className="button secondary"
            type="button"
            onClick={() => {
              accept(latest);
              setLatest(null);
            }}
          >
            Keep my draft for version {latest.data.version}
          </button>
          <p>
            Your draft will be saved only when you explicitly submit it again.
          </p>
        </>
      )}
    </section>
  );
}

export function CustomerPicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (id: string) => void;
}) {
  const { identity } = useSession();
  const [search, setSearch] = useState('');
  const [q, setQ] = useState('');
  useEffect(() => {
    const timer = setTimeout(() => setQ(search), 300);
    return () => clearTimeout(timer);
  }, [search]);
  const matches = useQuery({
    queryKey: [identity?.workspace_id, 'staff', 'customer-options', q],
    queryFn: ({ signal }) =>
      api<Customer[]>(`/customers?q=${encodeURIComponent(q)}`, { signal }),
  });
  const selected = useQuery({
    queryKey: [identity?.workspace_id, 'staff', 'customer-option', value],
    queryFn: ({ signal }) => api<Customer>(`/customers/${value}`, { signal }),
    enabled: !!value,
  });
  const rows = matches.data?.data ?? [];
  const options =
    selected.data && !rows.some((row) => row.id === value)
      ? [selected.data.data, ...rows]
      : rows;
  return (
    <div className="customer-picker">
      <label htmlFor="customer-search">Find a customer</label>
      <input
        id="customer-search"
        type="search"
        value={search}
        maxLength={200}
        onChange={(event) => setSearch(event.target.value)}
      />
      <label htmlFor="customer-choice">Customer</label>
      <select
        id="customer-choice"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={matches.isPending}
      >
        <option value="">Choose a customer</option>
        {options.map((row) => (
          <option key={row.id} value={row.id}>
            {row.name}
          </option>
        ))}
      </select>
      {matches.isPending && <p role="status">Loading customers...</p>}
      {matches.error && (
        <>
          <ErrorMessage error={matches.error} />
          <button
            className="text-button"
            type="button"
            onClick={() => void matches.refetch()}
          >
            Retry customers
          </button>
        </>
      )}
      {matches.data?.meta.has_more && (
        <p className="small-reading">
          Refine the search to find more customers.
        </p>
      )}
    </div>
  );
}

export function CustomFields({
  fields,
  resolving = false,
  values,
}: {
  fields: CaseField[];
  resolving?: boolean;
  values?: Record<string, unknown>;
}) {
  return (
    <>
      {fields.map((field) => {
        const required = resolving
          ? field.required_on_resolve
          : field.required_on_create;
        const label = `${field.label}${required ? ' · Required' : ' · Optional'}`;
        const raw = values ? values[field.key] : field.default_value;
        const initial = raw == null ? '' : String(raw);
        return (
          <div key={field.key} className="custom-field">
            <label htmlFor={`field-${field.key}`}>{label}</label>
            {field.type === 'single_select' ? (
              <select
                id={`field-${field.key}`}
                name={`field-${field.key}`}
                defaultValue={initial}
              >
                <option value="">Choose a value</option>
                {field.allowed_values.map((value) => (
                  <option key={value}>{value}</option>
                ))}
              </select>
            ) : field.type === 'boolean' ? (
              <select
                id={`field-${field.key}`}
                name={`field-${field.key}`}
                defaultValue={initial}
              >
                <option value="">Not specified</option>
                <option value="true">Yes</option>
                <option value="false">No</option>
              </select>
            ) : (
              <input
                id={`field-${field.key}`}
                name={`field-${field.key}`}
                defaultValue={initial}
                type={
                  field.type === 'date'
                    ? 'date'
                    : ['integer', 'decimal'].includes(field.type)
                      ? 'number'
                      : 'text'
                }
                step={field.type === 'decimal' ? 'any' : 1}
                min={field.minimum ?? undefined}
                max={field.maximum ?? undefined}
                maxLength={4000}
              />
            )}
          </div>
        );
      })}
    </>
  );
}
