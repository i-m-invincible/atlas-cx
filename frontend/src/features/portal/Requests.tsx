import { useEffect, useState } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { api, queryString } from '../../api/client';
import { ErrorMessage, Loading } from '../../components/Feedback';
import { useSession } from '../identity/session';
import { dateTime, reference, stateLabels, usePolling } from '../support/data';
import type { PortalSummary } from '../support/data';

export function Requests() {
  const { identity } = useSession();
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const q = params.get('q') ?? '';
  const [search, setSearch] = useState(q);
  const [announcement, setAnnouncement] = useState('');
  useEffect(() => {
    const timer = setTimeout(() => setSearch(q), 300);
    return () => clearTimeout(timer);
  }, [q]);
  const filters = { q: search, state: params.get('state') };
  const poll = usePolling();
  const query = useInfiniteQuery({
    queryKey: [identity?.workspace_id, 'portal', 'cases', filters],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ signal, pageParam }) =>
      api<PortalSummary[]>(
        `/portal/cases?${queryString({ ...filters, cursor: pageParam })}`,
        { signal },
      ),
    getNextPageParam: (last) =>
      last.meta.has_more ? (last.meta.next_cursor ?? undefined) : undefined,
    refetchInterval: poll,
    refetchIntervalInBackground: false,
  });
  const rows = query.data?.pages.flatMap((page) => page.data) ?? [];
  return (
    <>
      <div className="page-heading-row">
        <h1 id="page-heading" tabIndex={-1}>
          Your requests
        </h1>
        <Link className="button" to="/portal/new">
          New request
        </Link>
      </div>
      <div className="portal-filter work-surface">
        <label htmlFor="request-search">Search your requests</label>
        <input
          id="request-search"
          type="search"
          value={q}
          maxLength={200}
          onChange={(event) => {
            const next = new URLSearchParams(params);
            if (event.target.value) next.set('q', event.target.value);
            else next.delete('q');
            setParams(next, { replace: true });
          }}
        />
        <label htmlFor="request-state">State</label>
        <select
          id="request-state"
          value={params.get('state') ?? ''}
          onChange={(event) => {
            const next = new URLSearchParams(params);
            if (event.target.value) next.set('state', event.target.value);
            else next.delete('state');
            setParams(next);
          }}
        >
          <option value="">All states</option>
          {Object.entries(stateLabels).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
        <button className="text-button" onClick={() => setParams({})}>
          Clear filters
        </button>
      </div>
      {query.isPending || search !== q ? (
        <Loading label="Loading requests..." />
      ) : query.error ? (
        <>
          <ErrorMessage error={query.error} />
          <button
            className="button secondary"
            onClick={() => void query.refetch()}
          >
            Retry requests
          </button>
        </>
      ) : rows.length === 0 ? (
        <div className="empty-state">
          <h2>
            {search || filters.state
              ? 'No requests match these filters.'
              : 'You haven’t submitted a request yet.'}
          </h2>
          <p>Submit a request when you need help.</p>
        </div>
      ) : (
        <ul className="portal-request-list work-surface">
          {rows.map((row) => (
            <li key={row.id}>
              <Link
                to={`/portal/requests/${row.id}`}
                state={{ from: '/portal' + location.search }}
              >
                {row.subject}
              </Link>
              <p>
                {reference(row.number)} · {row.state_label}
              </p>
              <p className="small-reading">
                Submitted{' '}
                <time dateTime={row.created_at}>
                  {dateTime(row.created_at, identity!.timezone)}
                </time>
              </p>
            </li>
          ))}
        </ul>
      )}
      {query.hasNextPage && (
        <button
          className="button secondary"
          disabled={query.isFetchingNextPage}
          onClick={async () => {
            const before = rows.length;
            const result = await query.fetchNextPage();
            setAnnouncement(
              `${(result.data?.pages.flatMap((page) => page.data).length ?? before) - before} requests added.`,
            );
          }}
        >
          {query.isFetchingNextPage ? 'Loading...' : 'Load more requests'}
        </button>
      )}
      <p role="status">{announcement}</p>
    </>
  );
}
