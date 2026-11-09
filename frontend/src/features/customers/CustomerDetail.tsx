import { useState } from 'react';
import { CustomerCases } from '../support/CustomerCases';
import { CustomerActivity, Timeline } from '../activity/CustomerActivity';
import {
  useInfiniteQuery,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import {
  Link,
  useLocation,
  useParams,
  useSearchParams,
} from 'react-router-dom';
import { api, queryString } from '../../api/client';
import type { Contact, Customer } from '../../api/client';
import { ErrorMessage, Loading } from '../../components/Feedback';
import { useSession } from '../identity/session';

export function CustomerDetail() {
  const { id } = useParams();
  const { identity } = useSession();
  const location = useLocation();
  const [params] = useSearchParams();
  const view = params.get('view') ?? 'timeline';
  const client = useQueryClient();
  const [error, setError] = useState<Error | null>(null);
  const [pending, setPending] = useState(false);
  const [setupUrl, setSetupUrl] = useState('');
  const [notice, setNotice] = useState(
    (location.state as { notice?: string } | null)?.notice ?? '',
  );
  const customer = useQuery({
    queryKey: [identity?.workspace_id, 'staff', 'customer', id],
    queryFn: ({ signal }) => api<Customer>(`/customers/${id}`, { signal }),
  });
  const contacts = useInfiniteQuery({
    queryKey: [identity?.workspace_id, 'staff', 'contacts', id],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ signal, pageParam }) =>
      api<Contact[]>(
        `/contacts?${queryString({ customer_id: id, cursor: pageParam })}`,
        { signal },
      ),
    getNextPageParam: (last) =>
      last.meta.has_more ? (last.meta.next_cursor ?? undefined) : undefined,
  });
  const contactRows = contacts.data?.pages.flatMap((page) => page.data) ?? [];
  const canWrite = identity?.permissions.includes('customers:write');
  const canArchive = identity?.permissions.includes('customers:archive');
  const admin = identity?.role === 'admin';
  if (customer.isPending) return <Loading label="Loading customer…" />;
  if (customer.error || !customer.data)
    return (
      <>
        <ErrorMessage error={customer.error} />
        <button
          className="button secondary"
          onClick={() => void customer.refetch()}
        >
          Retry customer
        </button>
      </>
    );
  const row = customer.data.data;
  const back =
    (location.state as { from?: string } | null)?.from ?? '/app/customers';
  const time = (stamp: string) =>
    new Intl.DateTimeFormat('en-GB', {
      dateStyle: 'medium',
      timeStyle: 'short',
      timeZone: identity?.timezone,
    }).format(new Date(stamp));
  async function changed() {
    await Promise.all([
      client.invalidateQueries({
        queryKey: [identity?.workspace_id, 'staff', 'contacts', id],
      }),
      client.invalidateQueries({
        queryKey: [identity?.workspace_id, 'staff', 'customers'],
      }),
      client.invalidateQueries({
        queryKey: [identity?.workspace_id, 'staff', 'customer', id],
      }),
    ]);
  }
  return (
    <>
      <Link to={back} state={{ focusCustomer: id }}>
        Back to customers
      </Link>
      <div className="page-heading-row">
        <h1 id="page-heading" tabIndex={-1}>
          {row.name}
        </h1>
        {canWrite && !row.archived_at && (
          <Link className="button secondary" to={`/app/customers/${id}/edit`}>
            Edit customer
          </Link>
        )}
      </div>
      <p>
        {row.kind === 'business' ? 'Business' : 'Person'} ·{' '}
        <span className="sentence-label">{row.lifecycle}</span> ·{' '}
        {row.owner_name ?? 'Unassigned'}
      </p>
      {row.archived_at && <p className="status-label">Archived customer</p>}
      <p role="status" className="notice">
        {notice}
      </p>
      <ErrorMessage error={error} />
      {setupUrl && (
        <section
          className="work-surface secret-surface"
          aria-label="One-time setup link"
        >
          <h2>Setup link created</h2>
          <p>
            Share this link through a verified channel. It expires in 24 hours
            and can be used once.
          </p>
          <p className="small-reading">
            This link is displayed only here. Closing this message removes it
            from this screen.
          </p>
          <button
            className="button secondary"
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(setupUrl);
                setNotice('Setup link copied.');
              } catch {
                setError(new Error('Clipboard unavailable'));
              }
            }}
          >
            Copy setup link
          </button>
          <button className="text-button" onClick={() => setSetupUrl('')}>
            Close setup link
          </button>
          <details>
            <summary>Reveal setup link</summary>
            <code className="secret-value">{setupUrl}</code>
          </details>
        </section>
      )}
      <div className="customer-detail-layout">
        <section
          className="work-surface surface-padding"
          aria-label="Customer 360"
        >
          <div className="customer-views">
            {identity?.capabilities.activity && (
              <nav className="local-navigation" aria-label="Customer 360 views">
                {(['Timeline', 'Cases', 'Activity', 'Follow-ups'] as const).map(
                  (name) => {
                    const tab = name.toLowerCase();
                    return (
                      <Link
                        key={name}
                        to={'?view=' + tab}
                        state={location.state}
                        aria-current={view === tab ? 'page' : undefined}
                      >
                        {name}
                      </Link>
                    );
                  },
                )}
              </nav>
            )}
            {identity?.capabilities.activity && view === 'timeline' && (
              <Timeline customerId={row.id} />
            )}
            {identity?.capabilities.activity && view === 'activity' && (
              <CustomerActivity customer={row} />
            )}
            {(!identity?.capabilities.activity || view === 'cases') && (
              <CustomerCases customerId={row.id} archived={!!row.archived_at} />
            )}
            {identity?.permissions.includes('tasks:read') &&
              (!identity.capabilities.activity || view === 'follow-ups') && (
                <section className="ruled-section">
                  <h2>Follow-ups</h2>
                  <div className="form-actions">
                    <Link to={'/app/follow-ups/tasks?customer_id=' + row.id}>
                      View customer follow-ups
                    </Link>
                    {!row.archived_at &&
                      identity.permissions.includes('tasks:write') && (
                        <Link
                          to={'/app/follow-ups/tasks/new?customer=' + row.id}
                        >
                          Create follow-up
                        </Link>
                      )}
                  </div>
                </section>
              )}
          </div>
        </section>
        <div className="customer-context">
          <section
            className="work-surface surface-padding"
            aria-labelledby="customer-details-title"
          >
            <h2 id="customer-details-title">Customer details</h2>
            <dl className="record-details">
              <dt>External ID</dt>
              <dd>{row.external_id ?? 'Not recorded'}</dd>
              <dt>Owner</dt>
              <dd>{row.owner_name ?? 'Unassigned'}</dd>
              <dt>Tags</dt>
              <dd>{row.tags.length ? row.tags.join(', ') : 'None recorded'}</dd>
              <dt>Created</dt>
              <dd>
                <time dateTime={row.created_at}>{time(row.created_at)}</time>
              </dd>
              <dt>Time zone</dt>
              <dd>{identity?.timezone}</dd>
              <dt>Product activity expected</dt>
              <dd>{row.activity_expected ? 'Yes' : 'No'}</dd>
              <dt>Tracking began</dt>
              <dd>
                {row.tracking_started_at ? (
                  <time dateTime={row.tracking_started_at}>
                    {time(row.tracking_started_at)}
                  </time>
                ) : (
                  'Not recorded'
                )}
              </dd>
              <dt>Last event received</dt>
              <dd>
                {row.last_event_received_at ? (
                  <time dateTime={row.last_event_received_at}>
                    {time(row.last_event_received_at)}
                  </time>
                ) : (
                  'None recorded'
                )}
              </dd>
              <dt>Last meaningful activity</dt>
              <dd>
                {row.last_meaningful_activity_at ? (
                  <time dateTime={row.last_meaningful_activity_at}>
                    {time(row.last_meaningful_activity_at)}
                  </time>
                ) : (
                  'None recorded'
                )}
              </dd>
            </dl>
            {canArchive && !row.archived_at && (
              <details className="ruled-section">
                <summary>Archive customer</summary>
                <form
                  className="compact-form"
                  onSubmit={async (event) => {
                    event.preventDefault();
                    setPending(true);
                    setError(null);
                    const reason = new FormData(event.currentTarget).get(
                      'reason',
                    );
                    try {
                      await api(`/customers/${id}/archive`, {
                        method: 'POST',
                        version: row.version,
                        body: { reason },
                      });
                      await changed();
                      setNotice(
                        'Customer archived. Portal access is disabled.',
                      );
                    } catch (failure) {
                      setError(failure as Error);
                    } finally {
                      setPending(false);
                    }
                  }}
                >
                  <p>
                    Archiving keeps this record and disables its contacts’
                    portal access. Archived records cannot be edited.
                  </p>
                  <label htmlFor="archive-reason">Reason</label>
                  <textarea
                    id="archive-reason"
                    name="reason"
                    required
                    maxLength={2000}
                  />
                  <button className="button secondary" disabled={pending}>
                    {pending ? 'Archiving…' : 'Confirm archive customer'}
                  </button>
                </form>
              </details>
            )}
          </section>
          <section
            className="work-surface surface-padding"
            aria-labelledby="contacts-title"
          >
            <div className="page-heading-row">
              <h2 id="contacts-title">Contacts</h2>
              {canWrite && !row.archived_at && (
                <Link
                  className="button secondary"
                  to={`/app/customers/${id}/contacts/new`}
                >
                  Add contact
                </Link>
              )}
            </div>
            {contacts.isPending ? (
              <Loading label="Loading contacts…" />
            ) : contacts.error ? (
              <>
                <ErrorMessage error={contacts.error} />
                <button
                  className="button secondary"
                  onClick={() => void contacts.refetch()}
                >
                  Retry contacts
                </button>
              </>
            ) : contactRows.length === 0 ? (
              <p>No contacts yet. Add a contact to record who you work with.</p>
            ) : (
              <ul className="contact-list">
                {contactRows.map((contact) => (
                  <li key={contact.id}>
                    <h3>{contact.name}</h3>
                    <p>{contact.email}</p>
                    {contact.phone && <p>{contact.phone}</p>}
                    <p className="small-reading">
                      {contact.archived_at
                        ? 'Archived contact'
                        : contact.portal_enabled
                          ? 'Portal access enabled'
                          : 'Portal access not active'}
                    </p>
                    {!row.archived_at && !contact.archived_at && (
                      <div className="contact-actions">
                        {canWrite && (
                          <Link
                            to={`/app/customers/${id}/contacts/${contact.id}/edit`}
                          >
                            Edit contact
                          </Link>
                        )}
                        {admin && (
                          <button
                            className="text-button"
                            disabled={pending}
                            onClick={async () => {
                              setPending(true);
                              setError(null);
                              setSetupUrl('');
                              try {
                                const response = await api<{
                                  contact: Contact;
                                  setup_url: string;
                                }>(`/contacts/${contact.id}/portal-access`, {
                                  method: 'POST',
                                  version: contact.version,
                                });
                                setSetupUrl(response.data.setup_url);
                                await changed();
                                setNotice(
                                  'Setup link created. No email was sent.',
                                );
                              } catch (failure) {
                                setError(failure as Error);
                              } finally {
                                setPending(false);
                              }
                            }}
                          >
                            Create setup link for {contact.name}
                          </button>
                        )}
                        {admin && contact.portal_enabled && (
                          <button
                            className="text-button"
                            disabled={pending}
                            onClick={async () => {
                              setPending(true);
                              setError(null);
                              try {
                                await api(
                                  `/contacts/${contact.id}/portal-access`,
                                  {
                                    method: 'PATCH',
                                    version: contact.version,
                                    body: { active: false },
                                  },
                                );
                                await changed();
                                setNotice('Portal access disabled.');
                              } catch (failure) {
                                setError(failure as Error);
                              } finally {
                                setPending(false);
                              }
                            }}
                          >
                            Disable portal access for {contact.name}
                          </button>
                        )}
                      </div>
                    )}
                    {canArchive && !contact.archived_at && !row.archived_at && (
                      <details>
                        <summary>Archive {contact.name}</summary>
                        <form
                          className="compact-form"
                          onSubmit={async (event) => {
                            event.preventDefault();
                            setPending(true);
                            setError(null);
                            const reason = new FormData(
                              event.currentTarget,
                            ).get('reason');
                            try {
                              await api(`/contacts/${contact.id}/archive`, {
                                method: 'POST',
                                version: contact.version,
                                body: { reason },
                              });
                              await changed();
                              setNotice(
                                'Contact archived. Portal access is disabled.',
                              );
                            } catch (failure) {
                              setError(failure as Error);
                            } finally {
                              setPending(false);
                            }
                          }}
                        >
                          <p>
                            The contact remains in the customer record. Portal
                            access will be disabled.
                          </p>
                          <label htmlFor={`reason-${contact.id}`}>Reason</label>
                          <input
                            id={`reason-${contact.id}`}
                            name="reason"
                            required
                            maxLength={2000}
                          />
                          <button
                            className="button secondary"
                            disabled={pending}
                          >
                            Confirm archive contact
                          </button>
                        </form>
                      </details>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {contacts.hasNextPage && (
              <button
                className="button secondary"
                disabled={contacts.isFetchingNextPage}
                onClick={() => void contacts.fetchNextPage()}
              >
                {contacts.isFetchingNextPage
                  ? 'Loading contacts…'
                  : 'Load more contacts'}
              </button>
            )}
          </section>
        </div>
      </div>
    </>
  );
}
