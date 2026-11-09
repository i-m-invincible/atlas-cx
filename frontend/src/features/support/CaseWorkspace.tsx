import { useCallback, useEffect, useRef, useState } from 'react';
import {
  useInfiniteQuery,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import {
  Link,
  useBeforeUnload,
  useBlocker,
  useLocation,
  useSearchParams,
} from 'react-router-dom';
import { api } from '../../api/client';
import type { ApiEnvelope } from '../../api/client';
import { ErrorMessage, Loading } from '../../components/Feedback';
import { ValidationSummary } from '../../components/FormSafety';
import { useSession } from '../identity/session';
import { replyDraftKey } from '../knowledge/data';
import { ConflictReview, CustomFields } from './components';
import {
  customValues,
  dateTime,
  reference,
  useHeadingFocus,
  usePolling,
  useReplayKeys,
} from './data';
import type {
  CaseDetail,
  CaseSummary,
  CaseField,
  CaseMessage,
  HistoryItem,
  TransitionResult,
} from './data';

type Action = 'ask_customer' | 'resume' | 'resolve' | 'reopen' | 'close';
type Mode = 'public' | 'internal';
const actionTitles: Record<Action, string> = {
  ask_customer: 'Ask customer',
  resume: 'Resume case',
  resolve: 'Resolve case',
  reopen: 'Reopen case',
  close: 'Close case',
};
const actionStates: Record<Action, string[]> = {
  ask_customer: ['open'],
  resume: ['pending_customer'],
  resolve: ['new', 'open', 'pending_customer'],
  reopen: ['resolved'],
  close: ['resolved'],
};

export function CaseWorkspace({
  identifier,
  origin,
}: {
  identifier: string;
  origin: string;
}) {
  const { identity } = useSession();
  const poll = usePolling();
  const query = useQuery({
    queryKey: [identity?.workspace_id, 'staff', 'case', identifier],
    queryFn: ({ signal }) =>
      api<CaseDetail>(`/cases/${identifier}`, { signal }),
    refetchInterval: poll,
  });
  if (query.isPending) return <Loading label="Loading case..." />;
  if (query.error)
    return (
      <section>
        <ErrorMessage error={query.error} />
        <button
          className="button secondary"
          onClick={() => void query.refetch()}
        >
          Retry case
        </button>
      </section>
    );
  return <CaseWork key={identifier} row={query.data.data} origin={origin} />;
}

function CaseWork({ row, origin }: { row: CaseDetail; origin: string }) {
  const { identity } = useSession();
  const client = useQueryClient();
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const panel = params.get('panel') ?? 'conversation';
  const poll = usePolling();
  const [mode, setMode] = useState<Mode>('public');
  const draftKey = replyDraftKey(identity?.workspace_id, row.id);
  const [drafts, setDrafts] = useState(() => ({
    public: client.getQueryData<string>(draftKey) ?? '',
    internal: '',
  }));
  useEffect(() => {
    client.removeQueries({
      queryKey: replyDraftKey(identity?.workspace_id, row.id),
      exact: true,
    });
  }, [client, identity?.workspace_id, row.id]);
  const [versions, setVersions] = useState({
    public: row.version,
    internal: row.version,
  });
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [notice, setNotice] = useState(
    (location.state as { notice?: string } | null)?.notice ?? '',
  );
  const [invalid, setInvalid] = useState(false);
  const [attempts, setAttempts] = useState(0);
  const [action, setAction] = useState<Action | null>(null);
  const [actionVersion, setActionVersion] = useState(row.version);
  const [actionDirty, setActionDirty] = useState(false);
  const [actionTexts, setActionTexts] = useState<Record<Action, string>>({
    ask_customer: '',
    resume: '',
    resolve: '',
    reopen: '',
    close: '',
  });
  const [actionError, setActionError] = useState<Error | null>(null);
  const [actionAttempts, setActionAttempts] = useState(0);
  const [actionValidation, setActionValidation] = useState<
    { field: string; message: string }[]
  >([]);
  const [confirmClose, setConfirmClose] = useState(false);
  const [readError, setReadError] = useState<Error | null>(null);
  const [addedMessages, setAddedMessages] = useState('');
  const [resolutionCode, setResolutionCode] = useState('answered');
  const [relatedId, setRelatedId] = useState(row.related_case_id ?? '');
  const dialog = useRef<HTMLDialogElement>(null);
  const actionForm = useRef<HTMLFormElement>(null);
  const safeChoice = useRef<HTMLButtonElement>(null);
  const lastMarked = useRef(0);
  const keys = useReplayKeys();
  const dirty = !!drafts.public || !!drafts.internal || actionDirty;
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      dirty && !pending && currentLocation.pathname !== nextLocation.pathname,
  );
  const messages = useInfiniteQuery({
    queryKey: [identity?.workspace_id, 'staff', 'messages', row.id],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ signal, pageParam }) =>
      api<CaseMessage[]>(
        `/cases/${row.id}/messages${pageParam ? '?cursor=' + encodeURIComponent(pageParam) : ''}`,
        { signal },
      ),
    getNextPageParam: (last) =>
      last.meta.has_more ? (last.meta.next_cursor ?? undefined) : undefined,
    enabled: panel === 'conversation',
    refetchInterval: poll,
  });
  const history = useInfiniteQuery({
    queryKey: [identity?.workspace_id, 'staff', 'case-history', row.id],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ signal, pageParam }) =>
      api<HistoryItem[]>(
        `/cases/${row.id}/history${pageParam ? '?cursor=' + encodeURIComponent(pageParam) : ''}`,
        { signal },
      ),
    getNextPageParam: (last) =>
      last.meta.has_more ? (last.meta.next_cursor ?? undefined) : undefined,
    enabled: panel === 'history',
  });
  const relatedCases = useQuery({
    queryKey: [
      identity?.workspace_id,
      'staff',
      'related-options',
      row.customer.id,
    ],
    queryFn: ({ signal }) =>
      api<CaseSummary[]>(`/cases?customer_id=${row.customer.id}&limit=100`, {
        signal,
      }),
    enabled: action === 'resolve' && resolutionCode === 'duplicate',
  });
  const latestSequence =
    messages.data?.pages.at(-1)?.data.at(-1)?.sequence ?? 0;
  const mark = useCallback(
    async (sequence: number) => {
      lastMarked.current = sequence;
      try {
        await api(`/cases/${row.id}/read-marker`, {
          method: 'POST',
          body: { last_read_sequence: sequence },
        });
        setReadError(null);
        await client.invalidateQueries({
          queryKey: [identity?.workspace_id, 'staff', 'cases'],
        });
      } catch (cause) {
        setReadError(cause as Error);
      }
    },
    [row.id, client, identity],
  );
  useEffect(() => {
    if (panel === 'conversation' && latestSequence > lastMarked.current)
      void mark(latestSequence);
  }, [latestSequence, panel, mark]);
  useHeadingFocus('case-heading', true);
  useBeforeUnload(
    useCallback(
      (event) => {
        if (dirty) {
          event.preventDefault();
          event.returnValue = '';
        }
      },
      [dirty],
    ),
  );
  useEffect(() => {
    if (action || blocker.state === 'blocked') {
      if (blocker.state === 'blocked')
        document
          .querySelector<HTMLDialogElement>('#case-filter-dialog')
          ?.close();
      if (!dialog.current?.open) dialog.current?.showModal();
      if (blocker.state === 'blocked' || confirmClose)
        safeChoice.current?.focus();
    } else dialog.current?.close();
  }, [action, blocker.state, confirmClose]);
  const canWrite = identity?.permissions.includes('cases:write');
  const canClose = identity?.permissions.includes('cases:close');
  const backParams = new URLSearchParams(params);
  backParams.delete('panel');
  backParams.delete('from');
  const back = `/app/support/${origin}${backParams.size ? '?' + backParams : ''}`;
  const setPanel = (value: string) => {
    const next = new URLSearchParams(params);
    next.set('panel', value);
    setParams(next);
  };
  const refresh = async () => {
    await Promise.all([
      client.invalidateQueries({
        queryKey: [identity?.workspace_id, 'staff', 'case', row.id],
      }),
      client.invalidateQueries({
        queryKey: [identity?.workspace_id, 'staff', 'messages', row.id],
      }),
      client.invalidateQueries({
        queryKey: [identity?.workspace_id, 'staff', 'case-history', row.id],
      }),
      client.invalidateQueries({
        queryKey: [identity?.workspace_id, 'staff', 'cases'],
      }),
    ]);
  };
  const openAction = (value: Action) => {
    const confirmed = client.getQueryData<ApiEnvelope<CaseDetail>>([
      identity?.workspace_id,
      'staff',
      'case',
      row.id,
    ]);
    setAction(value);
    setActionVersion(confirmed?.data.version ?? row.version);
    setActionError(null);
    setActionValidation([]);
    setActionAttempts(0);
  };
  const closeAction = () => {
    if (actionDirty) setConfirmClose(true);
    else setAction(null);
  };
  const clearAction = () => {
    if (action) setActionTexts((current) => ({ ...current, [action]: '' }));
    setAction(null);
    setActionDirty(false);
    setConfirmClose(false);
    setResolutionCode('answered');
    setActionError(null);
  };
  const perform = async (body: unknown, version: number) => {
    const path = `/cases/${row.id}/transitions`;
    const response = await api<TransitionResult>(path, {
      method: 'POST',
      body,
      version,
      idempotencyKey: keys.keyFor(path, body),
    });
    keys.completed(path, body);
    client.setQueryData([identity?.workspace_id, 'staff', 'case', row.id], {
      ...response,
      data: response.data.case,
    });
    await refresh();
    return response.data.case;
  };
  const resolutionFields: CaseField[] = row.field_definitions
    .filter((field) => field.required_on_resolve)
    .map((field) => ({
      key: field.key,
      label: field.label,
      type: field.type,
      required_on_create: false,
      required_on_resolve: true,
      portal_editable_on_create: field.portal_editable_on_create ?? false,
      allowed_values: field.allowed_values ?? [],
      minimum: field.minimum ?? null,
      maximum: field.maximum ?? null,
    }));
  return (
    <section className="case-workspace" aria-label="Selected case">
      <div className="case-main work-surface">
        <Link className="back-to-inbox" to={back} state={{ focusCase: row.id }}>
          Back to {origin === 'cases' ? 'cases' : 'inbox'}
        </Link>
        <h2 id="case-heading" tabIndex={-1}>
          {row.subject}
        </h2>
        <p>
          {reference(row.number)} · {row.state_label}
        </p>
        <p className="small-reading">
          {row.customer.name} · {row.assignee?.name ?? 'Unassigned'}
        </p>
        <nav className="case-view-navigation" aria-label="Case views">
          {['conversation', 'details', 'history'].map((value) => (
            <button
              key={value}
              className="text-button"
              aria-current={panel === value ? 'page' : undefined}
              onClick={() => setPanel(value)}
            >
              {value.charAt(0).toUpperCase() + value.slice(1)}
            </button>
          ))}
        </nav>
        <div className="case-actions">
          {canWrite &&
            identity?.permissions.includes('assistant:ask') &&
            ['new', 'open', 'pending_customer'].includes(row.state) && (
              <Link
                className="button secondary"
                to={'/app/knowledge/assistant?case=' + row.id}
              >
                Use knowledge
              </Link>
            )}
          {canWrite && row.state === 'new' && (
            <button
              className="button secondary"
              disabled={pending}
              onClick={async () => {
                setPending(true);
                setError(null);
                try {
                  await perform(
                    {
                      action: 'triage',
                      assignee_member_id:
                        row.assignee?.id ?? identity?.member_id,
                    },
                    row.version,
                  );
                  setNotice(row.assignee ? 'Case opened.' : 'Case claimed.');
                } catch (cause) {
                  setError(cause as Error);
                } finally {
                  setPending(false);
                }
              }}
            >
              {row.assignee ? 'Open case' : 'Claim case'}
            </button>
          )}
          {canWrite && row.state === 'open' && (
            <button
              className="button secondary"
              disabled={pending}
              onClick={() => openAction('ask_customer')}
            >
              Ask customer
            </button>
          )}
          {canWrite && row.state === 'pending_customer' && (
            <button
              className="button secondary"
              disabled={pending}
              onClick={() => openAction('resume')}
            >
              Resume case
            </button>
          )}
          {canWrite &&
            ['new', 'open', 'pending_customer'].includes(row.state) && (
              <button
                className="button secondary"
                disabled={pending}
                onClick={() => openAction('resolve')}
              >
                Resolve case
              </button>
            )}
          {canWrite && row.state === 'resolved' && (
            <button
              className="button secondary"
              disabled={pending}
              onClick={() => openAction('reopen')}
            >
              Reopen case
            </button>
          )}
          {canClose && row.state === 'resolved' && (
            <button
              className="button secondary"
              disabled={pending}
              onClick={() => openAction('close')}
            >
              Close case
            </button>
          )}
        </div>
        <p role="status">{notice}</p>
        <ErrorMessage error={error} />
        <ConflictReview<CaseDetail>
          error={error}
          path={`/cases/${row.id}`}
          accept={(latest) => {
            client.setQueryData(
              [identity?.workspace_id, 'staff', 'case', row.id],
              latest,
            );
            setVersions({
              public: latest.data.version,
              internal: latest.data.version,
            });
            setError(null);
          }}
        />
        {panel === 'details' ? (
          <CaseContext row={row} />
        ) : panel === 'history' ? (
          <>
            <h3>Case history</h3>
            {history.isPending ? (
              <Loading label="Loading history..." />
            ) : history.error ? (
              <>
                <ErrorMessage error={history.error} />
                <button
                  className="text-button"
                  onClick={() => void history.refetch()}
                >
                  Retry history
                </button>
              </>
            ) : (
              <ol className="message-list">
                {history.data?.pages
                  .flatMap((page) => page.data)
                  .map((item) => (
                    <li key={item.id}>
                      <p>
                        {item.kind === 'transition'
                          ? `${item.from_state ?? 'Created'} → ${item.to_state}`
                          : item.action.replaceAll('.', ' ')}
                      </p>
                      <time className="metadata" dateTime={item.occurred_at}>
                        {dateTime(item.occurred_at, identity!.timezone)}
                      </time>
                      {item.reason && <p>{item.reason}</p>}
                      {(item.changed_fields ?? []).length > 0 && (
                        <p className="small-reading">
                          Changed: {(item.changed_fields ?? []).join(', ')}
                        </p>
                      )}
                    </li>
                  ))}
              </ol>
            )}
            {history.hasNextPage && (
              <button
                className="button secondary"
                onClick={() => void history.fetchNextPage()}
              >
                Load more history
              </button>
            )}
            <h3>Resolution cycles</h3>
            <ol className="message-list">
              {row.cycles.map((cycle) => (
                <li key={cycle.cycle_number}>
                  <h4>Cycle {cycle.cycle_number}</h4>
                  <p>Opened {dateTime(cycle.opened_at, identity!.timezone)}</p>
                  <p>
                    {cycle.resolved_at
                      ? `Resolved ${dateTime(cycle.resolved_at, identity!.timezone)}`
                      : 'Active cycle'}
                  </p>
                  {cycle.resolution_summary && (
                    <p>{cycle.resolution_summary}</p>
                  )}
                </li>
              ))}
            </ol>
          </>
        ) : (
          <>
            {messages.isPending ? (
              <Loading label="Loading conversation..." />
            ) : messages.error ? (
              <>
                <ErrorMessage error={messages.error} />
                <button
                  className="button secondary"
                  onClick={() => void messages.refetch()}
                >
                  Retry messages
                </button>
              </>
            ) : (
              <ol className="message-list" aria-label="Conversation">
                {messages.data?.pages
                  .flatMap((page) => page.data)
                  .map((message) => (
                    <li
                      key={message.id}
                      className={
                        message.visibility === 'internal' ? 'internal-note' : ''
                      }
                    >
                      {message.visibility === 'internal' && (
                        <h3 className="note-label">
                          <svg
                            aria-hidden="true"
                            width="18"
                            height="18"
                            viewBox="0 0 20 20"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="1.5"
                          >
                            <rect x="4" y="8" width="12" height="9" rx="2" />
                            <path d="M6 8V5a4 4 0 0 1 8 0v3" />
                          </svg>
                          Staff only
                        </h3>
                      )}
                      <p>
                        <strong>{message.author_display}</strong>
                        {message.message_kind === 'resolution'
                          ? ' · Resolution'
                          : message.message_kind === 'info_request'
                            ? ' · Request for information'
                            : ''}
                      </p>
                      <time className="metadata" dateTime={message.created_at}>
                        {dateTime(message.created_at, identity!.timezone)}
                      </time>
                      <p className="message-body">{message.body}</p>
                    </li>
                  ))}
              </ol>
            )}
            {messages.hasNextPage && (
              <button
                className="button secondary"
                disabled={messages.isFetchingNextPage}
                onClick={async () => {
                  const before =
                    messages.data?.pages.flatMap((page) => page.data).length ??
                    0;
                  const response = await messages.fetchNextPage();
                  setAddedMessages(
                    `${(response.data?.pages.flatMap((page) => page.data).length ?? before) - before} messages added.`,
                  );
                }}
              >
                Load more messages
              </button>
            )}
            <p role="status">{addedMessages}</p>
            {readError && (
              <>
                <p className="small-reading">
                  The conversation loaded, but its read state could not be
                  saved.
                </p>
                <button
                  className="text-button"
                  onClick={() => void mark(latestSequence)}
                >
                  Retry marking read
                </button>
              </>
            )}
            {['resolved', 'closed'].includes(row.state) ? (
              <section className="case-terminal">
                <h3>This case is {row.state}</h3>
                <p>
                  {row.state === 'closed'
                    ? 'Create a related case if more help is needed.'
                    : 'Reopen the case before posting a public reply.'}
                </p>
                {row.state === 'closed' && canWrite && (
                  <Link
                    className="button secondary"
                    to={`/app/support/cases/new?related=${row.id}`}
                  >
                    Create a related case
                  </Link>
                )}
                {(drafts.public || drafts.internal) && (
                  <details>
                    <summary>Unsent drafts retained in this tab</summary>
                    <p className="message-body">
                      Public reply: {drafts.public || 'None'}
                    </p>
                    <p className="message-body">
                      Staff-only note: {drafts.internal || 'None'}
                    </p>
                    <button
                      className="text-button"
                      onClick={() => setDrafts({ public: '', internal: '' })}
                    >
                      Discard unsent drafts
                    </button>
                  </details>
                )}
              </section>
            ) : canWrite ? (
              <form
                className="case-composer"
                noValidate
                onSubmit={async (event) => {
                  event.preventDefault();
                  setAttempts((value) => value + 1);
                  setInvalid(!drafts[mode].trim());
                  if (!drafts[mode].trim()) return;
                  setPending(true);
                  setError(null);
                  setNotice('');
                  const path = `/cases/${row.id}/messages`,
                    body = { body: drafts[mode], visibility: mode },
                    version = versions[mode];
                  try {
                    const response = await api<CaseMessage>(path, {
                      method: 'POST',
                      version,
                      body,
                      idempotencyKey: keys.keyFor(path, body),
                    });
                    keys.completed(path, body);
                    setDrafts((current) => ({ ...current, [mode]: '' }));
                    setVersions((current) => ({
                      public:
                        current.public === version
                          ? response.data.updated_case_version
                          : current.public,
                      internal:
                        current.internal === version
                          ? response.data.updated_case_version
                          : current.internal,
                    }));
                    await refresh();
                    setNotice(
                      mode === 'public'
                        ? 'Reply posted to the portal.'
                        : 'Internal note added.',
                    );
                  } catch (cause) {
                    setError(cause as Error);
                  } finally {
                    setPending(false);
                  }
                }}
              >
                <div
                  role="tablist"
                  aria-label="Composer visibility"
                  className="composer-tabs"
                  onKeyDown={(event) => {
                    const order = ['public', 'internal'] as const;
                    const current = order.indexOf(mode);
                    const next =
                      event.key === 'ArrowRight'
                        ? 1 - current
                        : event.key === 'ArrowLeft'
                          ? 1 - current
                          : event.key === 'Home'
                            ? 0
                            : event.key === 'End'
                              ? 1
                              : null;
                    if (next !== null) {
                      event.preventDefault();
                      setMode(order[next]!);
                      document
                        .getElementById(`composer-${order[next]}`)
                        ?.focus();
                    }
                  }}
                >
                  {(['public', 'internal'] as const).map((value) => (
                    <button
                      type="button"
                      role="tab"
                      key={value}
                      id={`composer-${value}`}
                      aria-selected={mode === value}
                      aria-controls="composer-panel"
                      tabIndex={mode === value ? 0 : -1}
                      onClick={() => {
                        setMode(value);
                        setInvalid(false);
                      }}
                    >
                      {value === 'public' ? 'Public reply' : 'Internal note'}
                    </button>
                  ))}
                </div>
                <div
                  role="tabpanel"
                  id="composer-panel"
                  aria-labelledby={`composer-${mode}`}
                >
                  <p
                    className={
                      mode === 'internal' ? 'note-label' : 'small-reading'
                    }
                  >
                    {mode === 'public'
                      ? 'Visible to the customer in the portal'
                      : 'Staff only'}
                  </p>
                  <ValidationSummary
                    submitCount={attempts}
                    messages={
                      invalid
                        ? [
                            {
                              field: 'case-reply',
                              message:
                                mode === 'public'
                                  ? 'Enter a reply.'
                                  : 'Enter an internal note.',
                            },
                          ]
                        : []
                    }
                  />
                  <label htmlFor="case-reply">
                    {mode === 'public'
                      ? 'Public reply message'
                      : 'Internal note message'}
                  </label>
                  <textarea
                    id="case-reply"
                    value={drafts[mode]}
                    maxLength={10000}
                    disabled={pending}
                    aria-invalid={invalid}
                    onChange={(event) => {
                      if (!drafts[mode])
                        setVersions((current) => ({
                          ...current,
                          [mode]: row.version,
                        }));
                      setDrafts((current) => ({
                        ...current,
                        [mode]: event.target.value,
                      }));
                    }}
                  />
                  <button className="button" disabled={pending}>
                    {pending
                      ? 'Posting...'
                      : mode === 'public'
                        ? 'Send reply'
                        : 'Add note'}
                  </button>
                </div>
              </form>
            ) : (
              <p className="small-reading">
                Read-only access. A staff member with editing access can reply
                or change this case.
              </p>
            )}
          </>
        )}
      </div>
      {panel === 'conversation' && (
        <aside
          className="wide-case-context work-surface"
          aria-label="Customer and case context"
        >
          <CaseContext row={row} />
        </aside>
      )}
      <dialog
        className="case-dialog"
        ref={dialog}
        aria-labelledby="case-dialog-title"
        onCancel={(event) => {
          event.preventDefault();
          if (blocker.state === 'blocked') blocker.reset();
          else closeAction();
        }}
        onKeyDown={(event) => {
          if (event.key !== 'Tab') return;
          const controls = [
            ...event.currentTarget.querySelectorAll<HTMLElement>(
              'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), a[href]',
            ),
          ].filter((item) => item.getClientRects().length > 0);
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
        {blocker.state === 'blocked' || confirmClose ? (
          <>
            <h2 id="case-dialog-title">Discard unsaved changes?</h2>
            <p>Your drafts are kept only in this tab until posted.</p>
            <div className="form-actions">
              <button
                ref={safeChoice}
                className="button"
                onClick={() => {
                  if (blocker.state === 'blocked') blocker.reset();
                  else setConfirmClose(false);
                }}
              >
                Keep editing
              </button>
              <button
                className="button secondary"
                onClick={() => {
                  if (blocker.state === 'blocked') {
                    setDrafts({ public: '', internal: '' });
                    setActionDirty(false);
                    blocker.proceed();
                  } else clearAction();
                }}
              >
                Discard changes
              </button>
            </div>
          </>
        ) : (
          action && (
            <>
              <div className="page-heading-row">
                <h2 id="case-dialog-title">{actionTitles[action]}</h2>
                <button className="text-button" onClick={closeAction}>
                  Close
                </button>
              </div>
              {action === 'close' && (
                <p>
                  Closed cases cannot be reopened. A new related request can be
                  created.
                </p>
              )}
              <form
                ref={actionForm}
                className="compact-form"
                noValidate
                onChange={() => setActionDirty(true)}
                onSubmit={async (event) => {
                  event.preventDefault();
                  setActionAttempts((value) => value + 1);
                  setActionError(null);
                  const data = new FormData(event.currentTarget),
                    field =
                      action === 'ask_customer'
                        ? 'message'
                        : action === 'resolve'
                          ? 'resolution_summary'
                          : 'reason';
                  const text = String(data.get(field) ?? '').trim();
                  setActionValidation(
                    text
                      ? []
                      : [
                          {
                            field: `action-${field}`,
                            message:
                              action === 'resolve'
                                ? 'Explain the resolution publicly.'
                                : action === 'ask_customer'
                                  ? 'Enter a public question.'
                                  : 'Enter a reason.',
                          },
                        ],
                  );
                  if (!text) return;
                  const body = {
                    action,
                    [field]: text,
                    ...(action === 'resolve'
                      ? {
                          resolution_code: resolutionCode,
                          ...(resolutionFields.length
                            ? {
                                custom_values: customValues(
                                  actionForm.current!,
                                  resolutionFields,
                                ),
                              }
                            : {}),
                          ...(resolutionCode === 'duplicate' && relatedId
                            ? { related_case_id: relatedId }
                            : {}),
                        }
                      : {}),
                  };
                  setPending(true);
                  try {
                    await perform(body, actionVersion);
                    clearAction();
                    setNotice(
                      action === 'resolve'
                        ? 'Resolution posted.'
                        : action === 'ask_customer'
                          ? 'Question posted to the portal.'
                          : 'Case updated.',
                    );
                    requestAnimationFrame(() =>
                      document.getElementById('case-heading')?.focus(),
                    );
                  } catch (cause) {
                    setActionError(cause as Error);
                  } finally {
                    setPending(false);
                  }
                }}
              >
                <ErrorMessage error={actionError} />
                <ConflictReview<CaseDetail>
                  error={actionError}
                  path={`/cases/${row.id}`}
                  accept={(latest) => {
                    setActionVersion(latest.data.version);
                    setActionError(null);
                    client.setQueryData(
                      [identity?.workspace_id, 'staff', 'case', row.id],
                      latest,
                    );
                  }}
                />
                <ValidationSummary
                  submitCount={actionAttempts}
                  messages={actionValidation}
                />
                {action === 'resolve' && (
                  <>
                    <label htmlFor="resolution-code">Resolution code</label>
                    <select
                      id="resolution-code"
                      value={resolutionCode}
                      onChange={(event) =>
                        setResolutionCode(event.target.value)
                      }
                    >
                      {[
                        'answered',
                        'fixed',
                        'fulfilled',
                        'declined',
                        'duplicate',
                        'other',
                      ].map((value) => (
                        <option key={value}>{value}</option>
                      ))}
                    </select>
                    {resolutionCode === 'duplicate' && (
                      <>
                        <label htmlFor="related-resolution">Related case</label>
                        <select
                          id="related-resolution"
                          value={relatedId}
                          onChange={(event) => setRelatedId(event.target.value)}
                        >
                          <option value="">Choose a related case</option>
                          {relatedCases.data?.data
                            .filter((item) => item.id !== row.id)
                            .map((item) => (
                              <option key={item.id} value={item.id}>
                                {reference(item.number)} · {item.subject}
                              </option>
                            ))}
                        </select>
                        {relatedCases.error && (
                          <ErrorMessage error={relatedCases.error} />
                        )}
                      </>
                    )}
                  </>
                )}
                <label
                  htmlFor={`action-${action === 'ask_customer' ? 'message' : action === 'resolve' ? 'resolution_summary' : 'reason'}`}
                >
                  {action === 'resolve'
                    ? 'Public resolution summary'
                    : action === 'ask_customer'
                      ? 'Public question'
                      : 'Reason'}
                </label>
                <textarea
                  id={`action-${action === 'ask_customer' ? 'message' : action === 'resolve' ? 'resolution_summary' : 'reason'}`}
                  name={
                    action === 'ask_customer'
                      ? 'message'
                      : action === 'resolve'
                        ? 'resolution_summary'
                        : 'reason'
                  }
                  value={actionTexts[action]}
                  onChange={(event) =>
                    setActionTexts((current) => ({
                      ...current,
                      [action]: event.target.value,
                    }))
                  }
                  maxLength={4000}
                  disabled={pending}
                />
                {action === 'resolve' && (
                  <CustomFields
                    fields={resolutionFields}
                    values={row.custom_values}
                    resolving
                  />
                )}
                {!actionStates[action].includes(row.state) && (
                  <p>
                    This action is no longer available. Review the updated case.
                  </p>
                )}
                <button
                  className="button"
                  disabled={
                    pending || !actionStates[action].includes(row.state)
                  }
                >
                  {pending ? 'Saving...' : actionTitles[action]}
                </button>
              </form>
            </>
          )
        )}
      </dialog>
    </section>
  );
}

function CaseContext({ row }: { row: CaseDetail }) {
  const { identity } = useSession();
  const target = row.target_status;
  return (
    <div className="case-context">
      <h3>Case details</h3>
      {identity?.permissions.includes('tasks:read') && (
        <div className="form-actions">
          <Link to={'/app/follow-ups/tasks?case_id=' + row.id}>
            Case follow-ups
          </Link>
          {identity.permissions.includes('tasks:write') && (
            <Link to={'/app/follow-ups/tasks/new?case=' + row.id}>
              Create follow-up
            </Link>
          )}
        </div>
      )}
      <dl className="record-details">
        <dt>Customer</dt>
        <dd>
          <Link to={`/app/customers/${row.customer.id}`}>
            {row.customer.name}
          </Link>
        </dd>
        <dt>Requesting contact</dt>
        <dd>{row.requester.name}</dd>
        <dt>Assignee</dt>
        <dd>{row.assignee?.name ?? 'Unassigned'}</dd>
        <dt>Team</dt>
        <dd>{row.team?.name ?? 'No team'}</dd>
        <dt>Priority</dt>
        <dd>{row.priority}</dd>
        <dt>Category</dt>
        <dd>{row.category_label}</dd>
        <dt>Origin</dt>
        <dd>
          {row.source === 'portal'
            ? 'Customer portal'
            : row.source === 'manual_phone'
              ? 'Phone · Logged manually'
              : row.source === 'manual_email'
                ? 'Email · Logged manually'
                : 'Other · Logged manually'}
        </dd>
      </dl>
      {identity?.permissions.includes('cases:write') &&
        row.state !== 'closed' && (
          <Link
            className="button secondary"
            to={`/app/support/cases/${row.id}/edit`}
          >
            Edit assignment and priority
          </Link>
        )}
      <section className="ruled-section">
        <h3>Operational targets</h3>
        <p>
          {row.first_response_at
            ? `First response ${dateTime(row.first_response_at, identity!.timezone)}`
            : `Response due ${dateTime(row.first_response_target_at, identity!.timezone)}`}
        </p>
        {row.first_response_status.is_overdue && (
          <p>
            First response target {row.first_response_at ? 'missed' : 'overdue'}
            .
          </p>
        )}
        <p>
          {target.status === 'paused'
            ? 'Resolution clock paused'
            : target.status === 'met'
              ? 'Resolution target met'
              : target.status === 'missed'
                ? 'Resolution target missed'
                : target.is_overdue
                  ? 'Resolution overdue'
                  : 'Resolution within target'}
        </p>
        {target.status === 'paused' && (
          <p>
            {Math.ceil(target.remaining_seconds / 60)} active minutes remaining
            {target.is_overdue ? ' · Already overdue' : ''}
          </p>
        )}
        {target.due_at && (
          <p>
            Resolution due{' '}
            <time dateTime={target.due_at}>
              {dateTime(target.due_at, identity!.timezone)}
            </time>
          </p>
        )}
        <p className="small-reading">
          Resolution pauses only while awaiting customer information. First
          response never pauses. Reopening starts a separate resolution cycle.
        </p>
      </section>
      {row.field_definitions.length > 0 && (
        <section className="ruled-section">
          <h3>Configured fields</h3>
          <dl className="record-details">
            {row.field_definitions.map((field) => (
              <div key={field.key}>
                <dt>{field.label}</dt>
                <dd>
                  {String(row.custom_values[field.key] ?? 'Not recorded')}
                </dd>
              </div>
            ))}
          </dl>
        </section>
      )}
    </div>
  );
}
