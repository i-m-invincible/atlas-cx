import { useState } from 'react';
import { Temporal } from '@js-temporal/polyfill';
import {
  useInfiniteQuery,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from 'react-router-dom';
import { api, apiPages } from '../../api/client';
import type { Member } from '../../api/client';
import type { components } from '../../api/schema';
import { ErrorMessage, Loading } from '../../components/Feedback';
import { UnsavedChanges } from '../../components/FormSafety';
import { useSession } from '../identity/session';
import { ConflictReview, CustomerPicker } from '../support/components';
import { dateTime, useHeadingFocus, useReplayKeys } from '../support/data';
import type { CaseDetail, CaseSummary } from '../support/data';
import { taskBase } from './data';
import type { Task } from './data';

type History = components['schemas']['TaskHistory'];
const historyLabels: Record<string, string> = {
  'task.created': 'Created',
  'task.created_from_feedback': 'Created from feedback',
  'task.updated': 'Updated',
  'task.completed': 'Completed',
  'task.reopened': 'Reopened',
  'task.cancelled': 'Cancelled',
  'task.assignee_reassigned': 'Reassigned after an access change',
};

export function TaskDetail() {
  const { id } = useParams();
  const { identity } = useSession();
  const [params] = useSearchParams();
  const initialCase = params.get('case');
  const query = useQuery({
    queryKey: [identity?.workspace_id, 'staff', 'task', id],
    queryFn: ({ signal }) => api<Task>('/tasks/' + id, { signal }),
    enabled: !!id,
  });
  const context = useQuery({
    queryKey: [identity?.workspace_id, 'staff', 'case', initialCase],
    queryFn: ({ signal }) =>
      api<CaseDetail>('/cases/' + initialCase, { signal }),
    enabled: !id && !!initialCase,
  });
  const loading =
    (!!id && query.isPending) || (!id && !!initialCase && context.isPending);
  useHeadingFocus('page-heading', !loading);
  if (loading) return <Loading label="Loading follow-up…" />;
  if (query.error || context.error)
    return <ErrorMessage error={query.error ?? context.error} />;
  const row = query.data?.data;
  const writable = !!identity?.permissions.includes('tasks:write');
  if (!row && !writable)
    return <p>You don’t have permission to create follow-ups.</p>;
  return (
    <TaskEditor
      key={id ?? 'new'}
      row={row}
      writable={writable}
      initialCustomer={
        context.data?.data.customer.id ?? params.get('customer') ?? ''
      }
      initialCase={initialCase ?? ''}
    />
  );
}

function TaskEditor({
  row,
  writable,
  initialCustomer,
  initialCase,
}: {
  row?: Task;
  writable: boolean;
  initialCustomer: string;
  initialCase: string;
}) {
  const { identity } = useSession();
  const timezone = identity!.timezone;
  const scope = [identity?.workspace_id, 'staff'];
  const client = useQueryClient();
  const navigate = useNavigate();
  const keys = useReplayKeys();
  const [customer, setCustomer] = useState(row?.customer.id ?? initialCustomer);
  const [caseId, setCaseId] = useState(row?.case?.id ?? initialCase);
  const [version, setVersion] = useState(row?.version);
  const [pending, setPending] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [complete, setComplete] = useState(false);
  const [note, setNote] = useState('');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState<Error | null>(null);
  const members = useQuery({
    queryKey: [...scope, 'assignment-members'],
    queryFn: ({ signal }) => apiPages<Member>('/members?active=true', signal),
    enabled: writable,
  });
  const cases = useQuery({
    queryKey: [...scope, 'task-case-options', customer],
    queryFn: ({ signal }) =>
      apiPages<CaseSummary>('/cases?customer_id=' + customer, signal),
    enabled: writable && !row && !!customer,
  });
  const history = useInfiniteQuery({
    queryKey: [...scope, 'task-history', row?.id],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ signal, pageParam }) =>
      api<History[]>(
        '/tasks/' +
          row?.id +
          '/history' +
          (pageParam ? '?cursor=' + encodeURIComponent(pageParam) : ''),
        { signal },
      ),
    getNextPageParam: (page) => page.meta.next_cursor ?? undefined,
    enabled: !!row,
  });
  const due = row
    ? Temporal.Instant.from(row.due_at)
        .toZonedDateTimeISO(timezone)
        .toPlainDateTime()
        .toString({ smallestUnit: 'second' })
    : '';
  const endpoint = row ? '/tasks/' + row.id : '/tasks';
  async function save(body: object, message: string) {
    setPending(true);
    setError(null);
    setNotice('');
    try {
      const response = await api<Task>(endpoint, {
        method: row ? 'PATCH' : 'POST',
        body,
        version,
        idempotencyKey: row ? undefined : keys.keyFor(endpoint, body),
      });
      keys.completed(endpoint, body);
      client.setQueryData([...scope, 'task', response.data.id], response);
      setVersion(response.data.version);
      setDirty(false);
      setComplete(false);
      setNote('');
      setNotice(message);
      await Promise.all([
        client.invalidateQueries({ queryKey: [...scope, '/tasks'] }),
        client.invalidateQueries({
          queryKey: [...scope, 'task-history', response.data.id],
        }),
      ]);
      if (!row) navigate(taskBase + '/' + response.data.id);
    } catch (failure) {
      setError(failure as Error);
    } finally {
      setPending(false);
    }
  }
  return (
    <>
      <UnsavedChanges dirty={(dirty || !!note) && !pending} />
      <Link to={taskBase}>Back to follow-ups</Link>
      <h1 id="page-heading" tabIndex={-1}>
        {row?.title ?? 'Create follow-up'}
      </h1>
      <p role="status">{notice}</p>
      <ErrorMessage error={error ?? members.error ?? cases.error} />
      {row && (
        <section className="work-surface m3-surface">
          <dl className="record-details">
            <dt>Customer</dt>
            <dd>
              <Link to={'/app/customers/' + row.customer.id}>
                {row.customer.name}
              </Link>
            </dd>
            <dt>Related case</dt>
            <dd>
              {row.case ? (
                <Link to={'/app/support/cases/' + row.case.id}>
                  {row.case.name}
                </Link>
              ) : (
                'None'
              )}
            </dd>
            <dt>Owner</dt>
            <dd>{row.assignee.name}</dd>
            <dt>Due</dt>
            <dd>
              {dateTime(row.due_at, timezone)} · {timezone}
              {row.overdue ? ' · Overdue' : ''}
            </dd>
            <dt>State</dt>
            <dd>{row.state.replaceAll('_', ' ')}</dd>
            {row.completed_at && (
              <>
                <dt>Completed</dt>
                <dd>{dateTime(row.completed_at, timezone)}</dd>
              </>
            )}
            {row.completion_note && (
              <>
                <dt>What was done?</dt>
                <dd className="message-body">{row.completion_note}</dd>
              </>
            )}
          </dl>
          {row.description && <p className="message-body">{row.description}</p>}
          {row.feedback_id && row.case && (
            <Link
              to={
                '/app/follow-ups/feedback?case_id=' +
                row.case.id +
                '#feedback-' +
                row.feedback_id
              }
            >
              View resolution feedback
            </Link>
          )}
        </section>
      )}
      <ConflictReview<Task>
        record="follow-up"
        error={error}
        path={endpoint}
        accept={(latest) => {
          setVersion(latest.data.version);
          setError(null);
          client.setQueryData([...scope, 'task', latest.data.id], latest);
        }}
      />
      {writable && (
        <form
          className="work-surface form-surface"
          onChange={() => setDirty(true)}
          onSubmit={(event) => {
            event.preventDefault();
            const data = new FormData(event.currentTarget);
            const selectedDue = String(data.get('due') ?? '');
            let dueAt: string;
            try {
              dueAt = Temporal.PlainDateTime.from(selectedDue)
                .toZonedDateTime(timezone, { disambiguation: 'reject' })
                .toInstant()
                .toString();
            } catch {
              setError(
                new Error(
                  'Choose a valid, unambiguous due date and time in ' +
                    timezone +
                    '.',
                ),
              );
              return;
            }
            const assignee = String(data.get('assignee') ?? '');
            if (!customer || !assignee) {
              setError(new Error('Choose a customer and an owner.'));
              return;
            }
            void save(
              {
                title: data.get('title'),
                description:
                  String(data.get('description') ?? '').trim() || null,
                due_at: dueAt,
                ...(!row || assignee !== row.assignee.id
                  ? { assignee_member_id: assignee }
                  : {}),
                ...(!row
                  ? { customer_id: customer, case_id: caseId || null }
                  : {}),
              },
              'Follow-up saved.',
            );
          }}
        >
          <h2>{row ? 'Edit follow-up' : 'Follow-up details'}</h2>
          {!row && (
            <>
              <CustomerPicker
                value={customer}
                onChange={(value) => {
                  setCustomer(value);
                  setCaseId('');
                  setDirty(true);
                }}
              />
              <label htmlFor="task-case">Related case · Optional</label>
              <select
                id="task-case"
                value={caseId}
                disabled={!customer || cases.isPending}
                onChange={(event) => setCaseId(event.target.value)}
              >
                <option value="">No case</option>
                {cases.data?.data.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.subject}
                  </option>
                ))}
              </select>
            </>
          )}
          <label htmlFor="task-title">Title</label>
          <input
            id="task-title"
            name="title"
            required
            maxLength={200}
            defaultValue={row?.title}
          />
          <label htmlFor="task-description">Description · Optional</label>
          <textarea
            id="task-description"
            name="description"
            maxLength={4000}
            defaultValue={row?.description ?? ''}
          />
          <label htmlFor="task-owner">Owner</label>
          <select
            id="task-owner"
            name="assignee"
            required
            defaultValue={row?.assignee.id ?? identity?.member_id ?? ''}
          >
            <option value="">Choose an owner</option>
            {members.data?.data
              .filter((member) => member.role !== 'viewer')
              .map((member) => (
                <option key={member.id} value={member.id}>
                  {member.display_name}
                </option>
              ))}
            {row &&
              !members.data?.data.some(
                (member) => member.id === row.assignee.id,
              ) && <option value={row.assignee.id}>{row.assignee.name}</option>}
          </select>
          <label htmlFor="task-due">Due date and time · {timezone}</label>
          <input
            id="task-due"
            name="due"
            type="datetime-local"
            step={1}
            required
            defaultValue={due}
          />
          <button
            className="button"
            disabled={pending || members.isPending || !!members.error}
          >
            {pending ? 'Saving…' : row ? 'Save follow-up' : 'Create follow-up'}
          </button>
        </form>
      )}
      {row && writable && (
        <section className="work-surface m3-surface" aria-label="Task actions">
          {['completed', 'cancelled'].includes(row.state) ? (
            <button
              className="button secondary"
              disabled={pending || dirty}
              onClick={() =>
                void save({ state: 'open' }, 'Follow-up reopened.')
              }
            >
              Reopen follow-up
            </button>
          ) : (
            <>
              <div className="form-actions">
                {row.state === 'open' && (
                  <button
                    className="button secondary"
                    disabled={pending || dirty}
                    onClick={() =>
                      void save({ state: 'in_progress' }, 'Follow-up started.')
                    }
                  >
                    Start follow-up
                  </button>
                )}
                <button
                  className="button secondary"
                  disabled={pending || dirty}
                  onClick={() => setComplete(!complete)}
                >
                  Record completion
                </button>
              </div>
              {complete && (
                <form
                  className="compact-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    if (!note.trim()) {
                      setError(
                        new Error(
                          'Describe what was done before completing this follow-up.',
                        ),
                      );
                      return;
                    }
                    void save(
                      { state: 'completed', completion_note: note.trim() },
                      'Follow-up completed.',
                    );
                  }}
                >
                  <label htmlFor="task-completion">What was done?</label>
                  <textarea
                    id="task-completion"
                    required
                    maxLength={2000}
                    value={note}
                    onChange={(event) => setNote(event.target.value)}
                  />
                  <button className="button" disabled={pending || dirty}>
                    Complete follow-up
                  </button>
                </form>
              )}
              <details>
                <summary>Cancel follow-up</summary>
                <p>Cancel this follow-up and remove it from open work?</p>
                <button
                  className="button secondary"
                  disabled={pending || dirty}
                  onClick={() =>
                    void save({ state: 'cancelled' }, 'Follow-up cancelled.')
                  }
                >
                  Confirm cancellation
                </button>
              </details>
            </>
          )}
        </section>
      )}
      {row && (
        <section className="work-surface m3-surface">
          <h2>Task history</h2>
          {history.isPending ? (
            <Loading label="Loading task history…" />
          ) : (
            <ErrorMessage error={history.error} />
          )}
          <ul className="message-list">
            {history.data?.pages
              .flatMap((page) => page.data)
              .map((event) => (
                <li key={event.id}>
                  {historyLabels[event.action] ?? event.action} ·{' '}
                  {event.actor_name ?? 'System'} ·{' '}
                  {dateTime(event.occurred_at, timezone)}
                </li>
              ))}
          </ul>
          {history.hasNextPage && (
            <button
              className="button secondary"
              onClick={() => void history.fetchNextPage()}
            >
              Load more history
            </button>
          )}
        </section>
      )}
    </>
  );
}
