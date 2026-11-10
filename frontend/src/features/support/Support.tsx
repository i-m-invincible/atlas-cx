import { useEffect, useRef, useState } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import {
  Link,
  NavLink,
  useLocation,
  useParams,
  useSearchParams,
} from 'react-router-dom';
import { api, queryString } from '../../api/client';
import { ErrorMessage, Loading } from '../../components/Feedback';
import { useSession } from '../identity/session';
import { CustomerPicker } from './components';
import { CaseWorkspace } from './CaseWorkspace';
import { dateTime, reference, stateLabels, usePolling } from './data';
import type { CaseSummary } from './data';

export function Support() {
  const { id } = useParams();
  const { identity } = useSession();
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const tableView = location.pathname === '/app/support/cases';
  const origin = tableView
    ? 'cases'
    : params.get('from') === 'cases'
      ? 'cases'
      : 'inbox';
  const q = params.get('q') ?? '';
  const [search, setSearch] = useState(q);
  const [announcement, setAnnouncement] = useState('');
  const filterDialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const timer = setTimeout(() => setSearch(q), 300);
    return () => clearTimeout(timer);
  }, [q]);
  const filters = {
    q: search,
    view: params.get('view') ?? (origin === 'inbox' ? 'unassigned' : 'all'),
    state: params.get('state'),
    priority: params.get('priority'),
    customer_id: params.get('customer_id'),
    unread: params.get('unread') === 'true' ? true : undefined,
    overdue: params.get('overdue') === 'true' ? true : undefined,
    sort: params.get('sort') ?? 'last_message_at',
  };
  const poll = usePolling();
  const query = useInfiniteQuery({
    queryKey: [identity?.workspace_id, 'staff', 'cases', filters],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ signal, pageParam }) =>
      api<CaseSummary[]>(
        `/cases?${queryString({ ...filters, cursor: pageParam })}`,
        { signal },
      ),
    getNextPageParam: (last) =>
      last.meta.has_more ? (last.meta.next_cursor ?? undefined) : undefined,
    refetchInterval: poll,
    refetchIntervalInBackground: false,
  });
  const rows = query.data?.pages.flatMap((page) => page.data) ?? [];
  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: key === 'q' });
  };
  const selectedParams = new URLSearchParams(params);
  selectedParams.delete('panel');
  selectedParams.set('from', origin);
  const casePath = (row: CaseSummary) =>
    `/app/support/cases/${row.id}?${selectedParams}`;
  useEffect(() => {
    const focused = (location.state as { focusCase?: string } | null)
      ?.focusCase;
    if (!focused || query.isPending || id) return;
    const target = [
      ...document.querySelectorAll<HTMLElement>('[data-case-id]'),
    ].find(
      (item) =>
        item.dataset.caseId === focused && item.getClientRects().length > 0,
    );
    const frame = requestAnimationFrame(() => target?.focus());
    return () => cancelAnimationFrame(frame);
  }, [location.state, query.isPending, id]);
  const content =
    query.isPending || search !== q ? (
      <Loading label="Loading cases..." />
    ) : query.error ? (
      <>
        <ErrorMessage error={query.error} />
        <button
          className="button secondary"
          onClick={() => void query.refetch()}
        >
          Retry cases
        </button>
      </>
    ) : rows.length === 0 ? (
      <div className="empty-state">
        <h2>
          {filters.view === 'unassigned' &&
          !q &&
          !filters.priority &&
          !filters.state
            ? 'No unassigned cases.'
            : 'No cases match this view.'}
        </h2>
        <p>Change the view or clear the filters to inspect other cases.</p>
      </div>
    ) : tableView ? (
      <div
        className="case-table-region"
        role="region"
        aria-label="Cases table"
        tabIndex={0}
      >
        <table className="case-table">
          <thead>
            <tr>
              <th scope="col">Case</th>
              <th scope="col">Customer</th>
              <th scope="col">State</th>
              <th scope="col">Priority</th>
              <th scope="col">Assignee</th>
              <th scope="col">Resolution target</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <th scope="row">
                  <Link to={casePath(row)} data-case-id={row.id}>
                    {row.subject}
                  </Link>
                  <p className="metadata">
                    {reference(row.number)}
                    {row.unread ? ' · Unread' : ''}
                  </p>
                </th>
                <td>{row.customer.name}</td>
                <td>{row.state_label}</td>
                <td>{row.priority}</td>
                <td>{row.assignee?.name ?? 'Unassigned'}</td>
                <td>
                  {row.target_status.status === 'paused'
                    ? 'Clock paused'
                    : row.target_status.is_overdue
                      ? 'Overdue'
                      : row.target_status.status === 'met'
                        ? 'Met'
                        : row.target_status.status === 'missed'
                          ? 'Missed'
                          : 'Within target'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    ) : (
      <ul className="case-queue">
        {rows.map((row) => (
          <li key={row.id} className={row.id === id ? 'selected-case' : ''}>
            <Link
              to={casePath(row)}
              data-case-id={row.id}
              aria-current={row.id === id ? 'page' : undefined}
            >
              {row.subject}
            </Link>
            <p className="metadata">
              {reference(row.number)} · {row.priority}
              {row.unread && <strong> · Unread</strong>}
            </p>
            <p className="small-reading">{row.customer.name}</p>
            <p className="metadata">
              {row.state_label} ·{' '}
              <time dateTime={row.last_message_at}>
                {dateTime(row.last_message_at, identity!.timezone)}
              </time>
            </p>
          </li>
        ))}
      </ul>
    );
  return (
    <>
      <div className="page-heading-row">
        <h1 id="page-heading" tabIndex={-1}>
          Support
        </h1>
        {identity?.permissions.includes('cases:write') && (
          <Link className="button" to="/app/support/cases/new">
            Create case
          </Link>
        )}
      </div>
      <nav className="local-navigation" aria-label="Support views">
        <NavLink to="/app/support/inbox">Inbox</NavLink>
        <NavLink to="/app/support/cases" end>
          Cases
        </NavLink>
      </nav>
      <div
        className={`support-grid ${id ? 'has-selection' : ''} ${tableView ? 'table-view' : ''}`}
      >
        <section className="support-queue work-surface" aria-label="Case queue">
          <div className="queue-filters">
            <label htmlFor="queue-view">Queue view</label>
            <select
              id="queue-view"
              value={filters.view}
              onChange={(event) => setFilter('view', event.target.value)}
            >
              <option value="unassigned">Unassigned</option>
              <option value="mine">Mine</option>
              <option value="awaiting_customer">Awaiting customer</option>
              <option value="recently_resolved">
                Recently resolved · 7 days
              </option>
              <option value="all">All cases</option>
            </select>
            <label htmlFor="case-search">Search cases</label>
            <input
              id="case-search"
              type="search"
              value={q}
              maxLength={200}
              placeholder="Subject or number"
              onChange={(event) => setFilter('q', event.target.value)}
            />
            <button
              className="button secondary"
              onClick={() => filterDialog.current?.showModal()}
            >
              Filters
            </button>
            <dialog
              id="case-filter-dialog"
              className="case-dialog case-filter-details"
              ref={filterDialog}
              aria-labelledby="case-filter-title"
              onKeyDown={(event) => {
                if (event.key !== 'Tab') return;
                const controls = [
                  ...event.currentTarget.querySelectorAll<HTMLElement>(
                    'button, input, select',
                  ),
                ].filter(
                  (item) =>
                    !item.hasAttribute('disabled') &&
                    item.getClientRects().length > 0,
                );
                const first = controls[0],
                  last = controls.at(-1);
                if (event.shiftKey && document.activeElement === first) {
                  event.preventDefault();
                  last?.focus();
                } else if (!event.shiftKey && document.activeElement === last) {
                  event.preventDefault();
                  first?.focus();
                }
              }}
            >
              <div className="page-heading-row">
                <h2 id="case-filter-title">Case filters</h2>
                <button
                  className="text-button"
                  onClick={() => filterDialog.current?.close()}
                >
                  Close filters
                </button>
              </div>
              <label htmlFor="case-state">State</label>
              <select
                id="case-state"
                value={filters.state ?? ''}
                onChange={(event) => setFilter('state', event.target.value)}
              >
                <option value="">All states</option>
                {Object.entries(stateLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
              <label htmlFor="case-priority">Priority</label>
              <select
                id="case-priority"
                value={filters.priority ?? ''}
                onChange={(event) => setFilter('priority', event.target.value)}
              >
                <option value="">All priorities</option>
                {['urgent', 'high', 'normal', 'low'].map((value) => (
                  <option key={value}>{value}</option>
                ))}
              </select>
              <CustomerPicker
                value={filters.customer_id ?? ''}
                onChange={(value) => setFilter('customer_id', value)}
              />
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={!!filters.unread}
                  onChange={(event) =>
                    setFilter('unread', event.target.checked ? 'true' : '')
                  }
                />
                Unread only
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={!!filters.overdue}
                  onChange={(event) =>
                    setFilter('overdue', event.target.checked ? 'true' : '')
                  }
                />
                Overdue only
              </label>
              <label htmlFor="case-sort">Sort by</label>
              <select
                id="case-sort"
                value={filters.sort}
                onChange={(event) => setFilter('sort', event.target.value)}
              >
                <option value="last_message_at">Last message</option>
                <option value="created_at">Newest first</option>
                <option value="priority">Priority</option>
              </select>
              <button
                className="button"
                onClick={() => filterDialog.current?.close()}
              >
                Done
              </button>
            </dialog>
            <button
              className="text-button"
              onClick={() =>
                setParams({ ...(id ? { from: origin } : {}), view: 'all' })
              }
            >
              Clear filters
            </button>
          </div>
          {content}
          {query.hasNextPage && (
            <button
              className="button secondary load-cases"
              disabled={query.isFetchingNextPage}
              onClick={async () => {
                const before = rows.length;
                const response = await query.fetchNextPage();
                setAnnouncement(
                  `${(response.data?.pages.flatMap((page) => page.data).length ?? before) - before} cases added.`,
                );
              }}
            >
              {query.isFetchingNextPage ? 'Loading...' : 'Load more cases'}
            </button>
          )}
          <p role="status">{announcement}</p>
        </section>
        {!tableView &&
          (id ? (
            <CaseWorkspace key={id} identifier={id} origin={origin} />
          ) : (
            <section className="work-surface no-selection">
              <h2>Choose a case to read the conversation.</h2>
              <p>
                The customer context and case actions appear with the selected
                case.
              </p>
            </section>
          ))}
      </div>
    </>
  );
}
