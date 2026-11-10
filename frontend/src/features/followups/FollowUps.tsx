import { useInfiniteQuery } from '@tanstack/react-query';
import { Link, NavLink, useLocation, useSearchParams } from 'react-router-dom';
import { api, queryString } from '../../api/client';
import type { components } from '../../api/schema';
import { ErrorMessage, Loading } from '../../components/Feedback';
import { useSession } from '../identity/session';
import { CustomerPicker } from '../support/components';
import { dateTime } from '../support/data';
import { ratingLabels, taskBase, taskStates } from './data';
import type { Task } from './data';

type Feedback = components['schemas']['StaffFeedbackView'];
const feedbackPath = '/app/follow-ups/feedback';

export function FollowUps() {
  const feedback = useLocation().pathname === feedbackPath;
  const { identity } = useSession();
  const [params, setParams] = useSearchParams();
  const update = (name: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(name, value);
    else next.delete(name);
    setParams(next);
  };
  const mine =
    params.get('scope') !== 'all' &&
    !params.has('case_id') &&
    !params.has('customer_id');
  const state = params.get('state') ?? (mine ? 'open,in_progress' : null);
  const filters = {
    customer_id: params.get('customer_id'),
    case_id: params.get('case_id'),
    ...(!feedback
      ? {
          assignee_id: mine ? identity?.member_id : undefined,
          state,
          overdue: params.get('overdue'),
          sort: params.get('sort'),
        }
      : { rating: params.get('rating') }),
  };
  const path = feedback ? '/feedback' : '/tasks';
  const query = useInfiniteQuery({
    queryKey: [identity?.workspace_id, 'staff', path, filters],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ signal, pageParam }) =>
      api<(Task | Feedback)[]>(
        path + '?' + queryString({ ...filters, cursor: pageParam }),
        { signal },
      ),
    getNextPageParam: (page) => page.meta.next_cursor ?? undefined,
  });
  const rows = query.data?.pages.flatMap((page) => page.data) ?? [];
  return (
    <>
      <div className="page-heading-row">
        <h1 id="page-heading" tabIndex={-1}>
          Follow-ups
        </h1>
        {!feedback && identity?.permissions.includes('tasks:write') && (
          <Link
            className="button"
            to={
              taskBase +
              '/new?' +
              queryString({
                customer: filters.customer_id,
                case: filters.case_id,
              })
            }
          >
            Create follow-up
          </Link>
        )}
      </div>
      <nav className="local-navigation" aria-label="Follow-up views">
        <NavLink to={taskBase}>Tasks</NavLink>
        <NavLink to={feedbackPath}>Feedback</NavLink>
      </nav>
      <details className="work-surface m3-surface task-filters">
        <summary>Filters</summary>
        <div className="m3-filter-grid">
          {!feedback ? (
            <>
              <div>
                <label htmlFor="task-scope">Scope</label>
                <select
                  id="task-scope"
                  value={mine ? 'mine' : 'all'}
                  onChange={(event) => {
                    const next = new URLSearchParams(params);
                    next.set('scope', event.target.value);
                    if (event.target.value === 'mine') {
                      next.delete('customer_id');
                      next.delete('case_id');
                    }
                    setParams(next);
                  }}
                >
                  <option value="mine">My tasks</option>
                  <option value="all">All tasks</option>
                </select>
              </div>
              <div>
                <label htmlFor="task-state">State</label>
                <select
                  id="task-state"
                  value={state ?? ''}
                  onChange={(event) => update('state', event.target.value)}
                >
                  <option value={mine ? 'open,in_progress' : ''}>
                    {mine ? 'Open and in progress' : 'Any state'}
                  </option>
                  {taskStates.map((state) => (
                    <option value={state} key={state}>
                      {state.replaceAll('_', ' ')}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="task-overdue">Due status</label>
                <select
                  id="task-overdue"
                  value={params.get('overdue') ?? ''}
                  onChange={(event) => update('overdue', event.target.value)}
                >
                  <option value="">Any</option>
                  <option value="true">Overdue</option>
                </select>
              </div>
              <div>
                <label htmlFor="task-sort">Sort</label>
                <select
                  id="task-sort"
                  value={params.get('sort') ?? 'due_at'}
                  onChange={(event) => update('sort', event.target.value)}
                >
                  <option value="due_at">Due</option>
                  <option value="created_at">Created</option>
                </select>
              </div>
            </>
          ) : (
            <div>
              <label htmlFor="feedback-rating">Rating</label>
              <select
                id="feedback-rating"
                value={params.get('rating') ?? ''}
                onChange={(event) => update('rating', event.target.value)}
              >
                <option value="">Any rating</option>
                {ratingLabels.map((label, index) => (
                  <option key={label} value={index + 1}>
                    {index + 1} · {label}
                  </option>
                ))}
              </select>
            </div>
          )}
          <CustomerPicker
            value={filters.customer_id ?? ''}
            onChange={(id) => {
              const next = new URLSearchParams(params);
              if (id) next.set('customer_id', id);
              else next.delete('customer_id');
              next.delete('case_id');
              setParams(next);
            }}
          />
          {filters.case_id && (
            <button
              className="button secondary"
              onClick={() => update('case_id', '')}
            >
              Clear case filter
            </button>
          )}
        </div>
      </details>
      {query.isPending ? (
        <Loading
          label={feedback ? 'Loading feedback…' : 'Loading follow-ups…'}
        />
      ) : query.error ? (
        <>
          <ErrorMessage error={query.error} />
          <button
            className="button secondary"
            onClick={() => void query.refetch()}
          >
            Retry
          </button>
        </>
      ) : rows.length === 0 ? (
        <p className="work-surface m3-surface">
          {feedback
            ? 'No resolution ratings have been submitted.'
            : mine
              ? 'You have no open follow-ups.'
              : 'No follow-ups yet. Create one from a customer or case.'}
        </p>
      ) : feedback ? (
        <FeedbackRows rows={rows as Feedback[]} timezone={identity!.timezone} />
      ) : (
        <TaskRows rows={rows as Task[]} timezone={identity!.timezone} />
      )}
      {query.hasNextPage && (
        <button
          className="button secondary"
          disabled={query.isFetchingNextPage}
          onClick={() => void query.fetchNextPage()}
        >
          Load more
        </button>
      )}
    </>
  );
}

function TaskRows({ rows, timezone }: { rows: Task[]; timezone: string }) {
  const due = (row: Task) =>
    dateTime(row.due_at, timezone) + (row.overdue ? ' · Overdue' : '');
  return (
    <section className="work-surface m3-surface" aria-label="Follow-up tasks">
      <div className="m3-table-region task-table">
        <table className="case-table">
          <thead>
            <tr>
              {['Task', 'Customer and case', 'Owner', 'Due', 'State'].map(
                (heading) => (
                  <th scope="col" key={heading}>
                    {heading}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <th scope="row">
                  <Link to={taskBase + '/' + row.id}>{row.title}</Link>
                </th>
                <td>
                  {row.customer.name}
                  {row.case && <p>{row.case.name}</p>}
                </td>
                <td>{row.assignee.name}</td>
                <td>{due(row)}</td>
                <td>{row.state.replaceAll('_', ' ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="message-list task-records">
        {rows.map((row) => (
          <li key={row.id}>
            <Link to={taskBase + '/' + row.id}>{row.title}</Link>
            <p>
              {row.customer.name}
              {row.case ? ' · ' + row.case.name : ''}
            </p>
            <p>
              Owner {row.assignee.name} · {row.state.replaceAll('_', ' ')}
            </p>
            <p>Due {due(row)}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

function FeedbackRows({
  rows,
  timezone,
}: {
  rows: Feedback[];
  timezone: string;
}) {
  return (
    <ul
      className="work-surface m3-surface message-list"
      aria-label="Resolution ratings"
    >
      {rows.map((row) => (
        <li key={row.id} id={'feedback-' + row.id}>
          <h2>
            {row.rating} of 5 · {ratingLabels[row.rating - 1]}
          </h2>
          <p>
            {row.customer.name} ·{' '}
            <Link to={'/app/support/cases/' + row.case.id}>
              {row.case.name}
            </Link>
          </p>
          <p>
            Cycle {row.cycle_number} · {dateTime(row.created_at, timezone)}
          </p>
          {row.comment && <p className="message-body">{row.comment}</p>}
          {row.task_id && (
            <Link to={taskBase + '/' + row.task_id}>Review follow-up task</Link>
          )}
        </li>
      ))}
    </ul>
  );
}
