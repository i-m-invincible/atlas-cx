import { useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api, ApiError } from '../../api/client';
import type { components } from '../../api/schema';
import { ErrorMessage, Loading } from '../../components/Feedback';
import { useSession } from '../identity/session';
import { dateTime } from '../support/data';
import { useRows } from './data';
import type { EventDefinition } from './data';

type Credential = components['schemas']['CredentialView'];
type Issued = components['schemas']['CredentialIssued'];
type Rule = components['schemas']['PropertyRule'];
type Values = components['schemas']['DefinitionCreate'];
type DraftRule = {
  id: number;
  name: string;
  type: Rule['type'];
  length: number;
};

function DefinitionEditor({
  row,
  save,
  cancel,
  pending,
}: {
  row: EventDefinition | null;
  save: (values: Values) => void;
  cancel: () => void;
  pending: boolean;
}) {
  const [rules, setRules] = useState<DraftRule[]>(() =>
    Object.entries(row?.allowed_properties ?? {}).map(([name, rule], id) => ({
      id,
      name,
      type: rule.type,
      length: rule.max_length ?? 120,
    })),
  );
  const nextId = useRef(rules.length);
  const [error, setError] = useState('');
  function change(id: number, fields: Partial<DraftRule>) {
    setRules((items) =>
      items.map((item) => (item.id === id ? { ...item, ...fields } : item)),
    );
  }
  return (
    <form
      className="compact-form ruled-section"
      onSubmit={(event) => {
        event.preventDefault();
        if (new Set(rules.map((rule) => rule.name)).size !== rules.length) {
          setError('Use each property key once.');
          return;
        }
        setError('');
        const data = new FormData(event.currentTarget);
        save({
          key: row?.key ?? String(data.get('key')),
          label: String(data.get('label')).trim(),
          allowed_properties: Object.fromEntries(
            rules.map((rule) => [
              rule.name,
              rule.type === 'string'
                ? { type: rule.type, max_length: rule.length }
                : { type: rule.type },
            ]),
          ),
          enabled: data.has('enabled'),
          counts_as_activity: data.has('meaningful'),
        });
      }}
    >
      <h3>{row ? 'Edit event definition' : 'New event definition'}</h3>
      <label>
        Event key{' '}
        <input
          name="key"
          required
          readOnly={!!row}
          defaultValue={row?.key ?? ''}
          pattern="[a-z0-9_]{1,50}"
          maxLength={50}
          aria-describedby="event-key-help"
        />
      </label>
      <p id="event-key-help" className="small-reading">
        Use lowercase letters, numbers, or underscores. The key stays fixed
        after creation.
      </p>
      <label>
        Display label{' '}
        <input
          name="label"
          required
          maxLength={120}
          defaultValue={row?.label ?? ''}
        />
      </label>
      <label className="checkbox-label">
        <input
          type="checkbox"
          name="enabled"
          defaultChecked={row?.enabled ?? true}
        />{' '}
        Accept new events
      </label>
      <label className="checkbox-label">
        <input
          type="checkbox"
          name="meaningful"
          defaultChecked={row?.counts_as_activity ?? false}
        />{' '}
        Counts as meaningful activity
      </label>
      <p className="small-reading">
        Changes to this setting apply to newly ingested events.
      </p>
      <fieldset>
        <legend>Allowed properties</legend>
        {rules.map(({ id, name, type, length }, index) => (
          <div className="property-fields" key={id}>
            <label>
              Property key {index + 1}{' '}
              <input
                required
                value={name}
                maxLength={50}
                pattern="[a-z0-9_]{1,50}"
                onChange={(event) => change(id, { name: event.target.value })}
              />
            </label>
            <label>
              Type {index + 1}{' '}
              <select
                value={type}
                onChange={(event) =>
                  change(id, { type: event.target.value as Rule['type'] })
                }
              >
                <option value="string">String</option>
                <option value="integer">Integer</option>
                <option value="number">Number</option>
                <option value="boolean">Boolean</option>
              </select>
            </label>
            {type === 'string' && (
              <label>
                Maximum length {index + 1}{' '}
                <input
                  type="number"
                  required
                  value={length || ''}
                  min={1}
                  max={8192}
                  onChange={(event) =>
                    change(id, { length: Number(event.target.value) })
                  }
                />
              </label>
            )}
            <button
              type="button"
              className="text-button"
              onClick={() =>
                setRules((items) => items.filter((item) => item.id !== id))
              }
            >
              Remove property {index + 1}
            </button>
          </div>
        ))}
        <button
          type="button"
          className="button secondary"
          disabled={rules.length >= 20}
          onClick={() => {
            const id = nextId.current++;
            setRules((items) => [
              ...items,
              { id, name: '', type: 'string', length: 120 },
            ]);
          }}
        >
          Add property
        </button>
      </fieldset>
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
      <div className="activity-actions">
        <button className="button" disabled={pending}>
          {pending ? 'Saving…' : 'Save event definition'}
        </button>
        <button
          type="button"
          className="text-button"
          disabled={pending}
          onClick={cancel}
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

function Tracking() {
  const { identity } = useSession();
  const client = useQueryClient();
  const definitions = useRows<EventDefinition>('/event-definitions');
  const credentials = useRows<Credential>('/api-credentials');
  const [edit, setEdit] = useState<EventDefinition | null | undefined>(
    undefined,
  );
  const [issued, setIssued] = useState<Issued | null>(null);
  const [confirm, setConfirm] = useState<string | null>(null);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState<Error | null>(null);
  const [pending, setPending] = useState(false);
  const newKeyName = useRef<HTMLInputElement>(null);
  const zone = identity?.timezone ?? 'UTC';

  async function run(operation: () => Promise<void>, message: string) {
    setPending(true);
    setError(null);
    setNotice('');
    try {
      await operation();
      await client.invalidateQueries({
        queryKey: [identity?.workspace_id, 'staff', 'activity-rows'],
      });
      setNotice(message);
    } catch (failure) {
      setError(failure as Error);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="settings-layout">
      <nav className="settings-sections" aria-label="Settings sections">
        <Link to="/app/settings/workspace">Workspace</Link>
        <Link to="/app/settings/case-configuration">Case configuration</Link>
        <Link to="/app/settings/event-tracking" aria-current="page">
          Event tracking
        </Link>
      </nav>
      <div>
        <p role="status">{notice}</p>
        <ErrorMessage error={error} />
        <section
          className="work-surface surface-padding activity-panel"
          aria-labelledby="event-definitions"
        >
          <h2 id="event-definitions">Event definitions</h2>
          <p>Define the events and scalar properties this workspace accepts.</p>
          <button
            type="button"
            className="button secondary"
            disabled={pending}
            onClick={() => setEdit(null)}
          >
            New event definition
          </button>
          {edit !== undefined && (
            <DefinitionEditor
              key={edit?.id ?? 'new'}
              row={edit}
              pending={pending}
              cancel={() => setEdit(undefined)}
              save={(values) =>
                void run(async () => {
                  if (edit) {
                    const { key, ...changes } = values;
                    if (key !== edit.key)
                      throw new ApiError(422, {
                        detail: 'The event key cannot change.',
                      });
                    await api('/event-definitions/' + edit.id, {
                      method: 'PATCH',
                      version: edit.version,
                      body: changes,
                    });
                  } else {
                    await api('/event-definitions', {
                      method: 'POST',
                      body: values,
                    });
                  }
                  setEdit(undefined);
                }, 'Event definition saved.')
              }
            />
          )}
          {definitions.isPending ? (
            <Loading label="Loading event definitions…" />
          ) : (
            <>
              {definitions.error && (
                <>
                  <ErrorMessage error={definitions.error} />
                  <button
                    className="text-button"
                    onClick={() => void definitions.refetch()}
                  >
                    Retry event definitions
                  </button>
                </>
              )}
              <ul className="activity-rows">
                {definitions.data?.pages
                  .flatMap((page) => page.data)
                  .map((row) => (
                    <li key={row.id}>
                      <h3>{row.label}</h3>
                      <p className="small-reading">
                        <code>{row.key}</code> ·{' '}
                        {row.enabled ? 'Enabled' : 'Disabled'}
                        {' · '}
                        {row.counts_as_activity
                          ? 'Counts as activity'
                          : 'Recorded only'}
                      </p>
                      <button
                        type="button"
                        className="text-button"
                        disabled={pending}
                        onClick={() => setEdit(row)}
                      >
                        Edit {row.label}
                      </button>
                    </li>
                  ))}
              </ul>
              {!definitions.error &&
                definitions.data?.pages[0]?.data.length === 0 && (
                  <p>No event definitions yet.</p>
                )}
              {definitions.hasNextPage && (
                <button
                  className="button secondary"
                  disabled={definitions.isFetchingNextPage}
                  onClick={() => void definitions.fetchNextPage()}
                >
                  Load more definitions
                </button>
              )}
            </>
          )}
        </section>
        <section
          className="work-surface surface-padding activity-panel"
          aria-labelledby="event-credentials"
        >
          <h2 id="event-credentials">Ingestion credentials</h2>
          <p>Each key can submit events for this workspace.</p>
          <form
            className="activity-filters"
            onSubmit={(event) => {
              event.preventDefault();
              const data = new FormData(event.currentTarget);
              void run(async () => {
                const { data: key } = await api<Issued>('/api-credentials', {
                  method: 'POST',
                  body: { name: data.get('name') },
                });
                setIssued(key);
                if (newKeyName.current) newKeyName.current.value = '';
              }, 'Ingestion credential created.');
            }}
          >
            <label>
              Credential name{' '}
              <input name="name" required maxLength={120} ref={newKeyName} />
            </label>
            <button className="button" disabled={pending || !!issued}>
              Create credential
            </button>
          </form>
          {issued && (
            <section
              className="secret-surface work-surface"
              aria-label="One-time ingestion key"
            >
              <h3>New ingestion key</h3>
              <p>You won’t be able to view this key again.</p>
              <code className="secret-value">{issued.secret}</code>
              <div className="activity-actions">
                <button
                  type="button"
                  className="button secondary"
                  onClick={async () => {
                    try {
                      await navigator.clipboard.writeText(issued.secret);
                      setNotice('Ingestion key copied.');
                    } catch {
                      setError(
                        new ApiError(400, {
                          detail:
                            'Clipboard unavailable. Select and copy the key.',
                        }),
                      );
                    }
                  }}
                >
                  Copy key
                </button>
                <button
                  type="button"
                  className="text-button"
                  onClick={() => {
                    setIssued(null);
                    newKeyName.current?.focus();
                  }}
                >
                  Dismiss key
                </button>
              </div>
            </section>
          )}
          {credentials.isPending ? (
            <Loading label="Loading credentials…" />
          ) : (
            <>
              {credentials.error && (
                <>
                  <ErrorMessage error={credentials.error} />
                  <button
                    className="text-button"
                    onClick={() => void credentials.refetch()}
                  >
                    Retry credentials
                  </button>
                </>
              )}
              <ul className="activity-rows">
                {credentials.data?.pages
                  .flatMap((page) => page.data)
                  .map((row) => (
                    <li key={row.id}>
                      <h3>{row.name}</h3>
                      <p className="small-reading">
                        <code>{row.token_prefix}…</code> ·{' '}
                        {row.revoked_at ? 'Revoked' : 'Active'}
                      </p>
                      <p className="small-reading">
                        Last used{' '}
                        {row.last_used_at
                          ? dateTime(row.last_used_at, zone)
                          : 'never'}
                      </p>
                      {!row.revoked_at &&
                        (confirm === row.id ? (
                          <div className="activity-actions">
                            <p>Revoke this key immediately?</p>
                            <button
                              type="button"
                              className="button secondary"
                              disabled={pending}
                              onClick={() =>
                                void run(async () => {
                                  await api(
                                    '/api-credentials/' + row.id + '/revoke',
                                    { method: 'POST', version: row.version },
                                  );
                                  setConfirm(null);
                                }, 'Ingestion credential revoked.')
                              }
                            >
                              Confirm revocation
                            </button>
                            <button
                              type="button"
                              className="text-button"
                              disabled={pending}
                              onClick={() => setConfirm(null)}
                            >
                              Keep key
                            </button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            className="text-button"
                            disabled={pending}
                            onClick={() => setConfirm(row.id)}
                          >
                            Revoke {row.name}
                          </button>
                        ))}
                    </li>
                  ))}
              </ul>
              {!credentials.error &&
                credentials.data?.pages[0]?.data.length === 0 && (
                  <p>No ingestion credentials yet.</p>
                )}
              {credentials.hasNextPage && (
                <button
                  className="button secondary"
                  disabled={credentials.isFetchingNextPage}
                  onClick={() => void credentials.fetchNextPage()}
                >
                  Load more credentials
                </button>
              )}
            </>
          )}
        </section>
      </div>
    </div>
  );
}

export function EventSettings() {
  const { identity } = useSession();
  return (
    <>
      <h1 id="page-heading" tabIndex={-1}>
        Event tracking
      </h1>
      {identity?.role === 'admin' ? (
        <Tracking key={identity.workspace_id} />
      ) : (
        <p>You don’t have permission to manage event tracking.</p>
      )}
    </>
  );
}
