import { useEffect, useState } from 'react';
import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { api, apiPages, queryString } from '../../api/client';
import type { Customer, Member } from '../../api/client';
import { ErrorMessage, Loading } from '../../components/Feedback';
import { useSession } from '../identity/session';

export function CustomerList() {
  const { identity } = useSession();
  const [parameters, setParameters] = useSearchParams();
  const location = useLocation();
  const q = parameters.get('q') ?? '';
  const [search, setSearch] = useState(q);
  const [added, setAdded] = useState('');
  useEffect(() => {
    const timer = window.setTimeout(() => setSearch(q), 300);
    return () => window.clearTimeout(timer);
  }, [q]);
  const filters = {
    q: search,
    lifecycle: parameters.get('lifecycle'),
    owner_id: parameters.get('owner_id'),
    tag: parameters.get('tag'),
    archived: parameters.get('archived') === 'true',
    sort: parameters.get('sort') ?? 'created_at',
  };
  const members = useQuery({
    queryKey: [identity?.workspace_id, 'staff', 'members'],
    queryFn: ({ signal }) => apiPages<Member>('/members?active=true', signal),
    enabled: !!identity,
  });
  const customers = useInfiniteQuery({
    queryKey: [identity?.workspace_id, 'staff', 'customers', filters],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ signal, pageParam }) =>
      api<Customer[]>(
        `/customers?${queryString({ ...filters, cursor: pageParam })}`,
        { signal },
      ),
    getNextPageParam: (last) =>
      last.meta.has_more ? (last.meta.next_cursor ?? undefined) : undefined,
    enabled: !!identity,
  });
  const rows = customers.data?.pages.flatMap((page) => page.data) ?? [];
  const canWrite = identity?.permissions.includes('customers:write');
  useEffect(() => {
    const id = (location.state as { focusCustomer?: string } | null)
      ?.focusCustomer;
    if (!id || customers.isPending) return;
    const link = [
      ...document.querySelectorAll<HTMLElement>('[data-customer-id]'),
    ].find(
      (element) =>
        element.dataset.customerId === id &&
        element.getClientRects().length > 0,
    );
    link?.focus();
  }, [customers.isPending, location.state]);
  function nameLink(customer: Customer) {
    return (
      <Link
        data-customer-id={customer.id}
        to={`/app/customers/${customer.id}`}
        state={{ from: location.pathname + location.search }}
      >
        {customer.name}
      </Link>
    );
  }
  return (
    <>
      <div className="page-heading-row">
        <h1 id="page-heading" tabIndex={-1}>
          Customers
        </h1>
        {canWrite && (
          <Link className="button" to="/app/customers/new">
            Add customer
          </Link>
        )}
      </div>
      <p className="small-reading">
        Keep customer identities, contacts, and ownership together.
      </p>
      <section
        className="work-surface customer-workspace"
        aria-label="Customer records"
      >
        <div className="filter-region">
          <label htmlFor="customer-search">Search customers</label>
          <input
            id="customer-search"
            type="search"
            maxLength={200}
            placeholder="Name or external ID"
            value={q}
            onChange={(event) => {
              const next = new URLSearchParams(parameters);
              if (event.target.value) next.set('q', event.target.value);
              else next.delete('q');
              setParameters(next, { replace: true });
            }}
          />
          <form
            className="filter-form"
            key={[
              parameters.get('lifecycle'),
              parameters.get('owner_id'),
              parameters.get('tag'),
              parameters.get('archived'),
              parameters.get('sort'),
            ].join(':')}
            onSubmit={(event) => {
              event.preventDefault();
              const data = new FormData(event.currentTarget);
              const next = new URLSearchParams(parameters);
              for (const field of ['lifecycle', 'owner_id', 'tag', 'sort']) {
                const value = String(data.get(field) ?? '');
                if (value) next.set(field, value);
                else next.delete(field);
              }
              if (data.get('archived')) next.set('archived', 'true');
              else next.delete('archived');
              setParameters(next);
            }}
          >
            <div>
              <label htmlFor="lifecycle-filter">Lifecycle</label>
              <select
                id="lifecycle-filter"
                name="lifecycle"
                defaultValue={parameters.get('lifecycle') ?? ''}
              >
                <option value="">All lifecycles</option>
                <option value="prospect">Prospect</option>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </div>
            <div>
              <label htmlFor="owner-filter">Owner</label>
              <select
                id="owner-filter"
                name="owner_id"
                disabled={members.isPending || !!members.error}
                defaultValue={parameters.get('owner_id') ?? ''}
              >
                <option value="">All owners</option>
                {members.data?.data
                  .filter((member) => member.role !== 'viewer')
                  .map((member) => (
                    <option key={member.id} value={member.id}>
                      {member.display_name}
                    </option>
                  ))}
              </select>
            </div>
            <div>
              <label htmlFor="tag-filter">Tag</label>
              <input
                id="tag-filter"
                name="tag"
                maxLength={40}
                defaultValue={parameters.get('tag') ?? ''}
              />
            </div>
            <div>
              <label htmlFor="sort-filter">Sort by</label>
              <select
                id="sort-filter"
                name="sort"
                defaultValue={parameters.get('sort') ?? 'created_at'}
              >
                <option value="created_at">Newest first</option>
                <option value="name">Name</option>
              </select>
            </div>
            <label className="checkbox-label">
              <input
                name="archived"
                type="checkbox"
                defaultChecked={parameters.get('archived') === 'true'}
              />
              Archived customers
            </label>
            <button className="button secondary">Apply filters</button>
            <button
              className="text-button"
              type="button"
              onClick={() => setParameters({})}
            >
              Clear filters
            </button>
          </form>
          {members.isPending && <p role="status">Loading owners...</p>}
          {members.error && (
            <>
              <ErrorMessage error={members.error} />
              <button
                className="button secondary"
                type="button"
                onClick={() => void members.refetch()}
              >
                Retry owners
              </button>
            </>
          )}
        </div>
        {customers.isPending || search !== q ? (
          <div className="surface-padding">
            <Loading label="Loading customers…" />
          </div>
        ) : customers.isError ? (
          <div className="surface-padding">
            <ErrorMessage error={customers.error} />
            <button
              className="button secondary"
              onClick={() => void customers.refetch()}
            >
              Retry customers
            </button>
          </div>
        ) : rows.length === 0 ? (
          <div className="empty-state">
            <h2>
              {q || parameters.size
                ? 'No customers match these filters.'
                : 'No customers yet.'}
            </h2>
            <p>
              {q || parameters.size
                ? 'Adjust the search or clear the filters.'
                : canWrite
                  ? 'Add a customer to connect their requests, activity, and follow-ups.'
                  : 'Ask a workspace administrator to add a customer.'}
            </p>
          </div>
        ) : (
          <>
            <table className="customer-table">
              <caption className="sr-only">
                Customers in {identity?.workspace_name}
              </caption>
              <thead>
                <tr>
                  <th>Customer</th>
                  <th className="wide-column">Type</th>
                  <th>Owner</th>
                  <th>Lifecycle</th>
                  <th>Health</th>
                  <th className="wide-column">Last activity</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((customer) => (
                  <tr key={customer.id}>
                    <th scope="row">
                      {nameLink(customer)}
                      {customer.external_id && (
                        <span className="row-detail">
                          {customer.external_id}
                        </span>
                      )}
                    </th>
                    <td className="wide-column">
                      {customer.kind === 'business' ? 'Business' : 'Person'}
                    </td>
                    <td>{customer.owner_name ?? 'Unassigned'}</td>
                    <td className="sentence-label">{customer.lifecycle}</td>
                    <td>Unknown</td>
                    <td className="wide-column">No recorded activity</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <ul className="customer-records">
              {rows.map((customer) => (
                <li key={customer.id}>
                  {nameLink(customer)}
                  <p>
                    {customer.kind === 'business' ? 'Business' : 'Person'} ·{' '}
                    {customer.owner_name ?? 'Unassigned'} ·{' '}
                    <span className="sentence-label">{customer.lifecycle}</span>
                  </p>
                  <p className="small-reading">
                    Health unknown · No recorded activity
                  </p>
                  {customer.external_id && (
                    <p className="small-reading">
                      External ID: {customer.external_id}
                    </p>
                  )}
                </li>
              ))}
            </ul>
            {customers.hasNextPage && (
              <div className="surface-padding">
                <button
                  className="button secondary"
                  disabled={customers.isFetchingNextPage}
                  onClick={async () => {
                    const previous = rows.length;
                    const next = await customers.fetchNextPage();
                    const count =
                      next.data?.pages.flatMap((page) => page.data).length ??
                      previous;
                    setAdded(`Added ${count - previous} customers.`);
                  }}
                >
                  {customers.isFetchingNextPage
                    ? 'Loading more…'
                    : 'Load more customers'}
                </button>
                <p role="status">{added}</p>
              </div>
            )}
          </>
        )}
      </section>
    </>
  );
}
