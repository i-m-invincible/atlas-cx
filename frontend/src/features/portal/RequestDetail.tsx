import { useMemo, useState } from 'react';
import {
  useInfiniteQuery,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import { Link, useLocation, useParams } from 'react-router-dom';
import { api } from '../../api/client';
import { ErrorMessage, Loading } from '../../components/Feedback';
import { UnsavedChanges, ValidationSummary } from '../../components/FormSafety';
import { useSession } from '../identity/session';
import { ConflictReview } from '../support/components';
import {
  dateTime,
  explanations,
  reference,
  useHeadingFocus,
  usePolling,
  useReplayKeys,
} from '../support/data';
import type { PortalCase, PortalMessage } from '../support/data';

export function RequestDetail() {
  const { id } = useParams();
  const { identity } = useSession();
  const client = useQueryClient();
  const location = useLocation();
  const poll = usePolling();
  const query = useQuery({
    queryKey: [identity?.workspace_id, 'portal', 'case', id],
    queryFn: ({ signal }) => api<PortalCase>(`/portal/cases/${id}`, { signal }),
    refetchInterval: poll,
  });
  const messages = useInfiniteQuery({
    queryKey: [identity?.workspace_id, 'portal', 'messages', id],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ signal, pageParam }) =>
      api<PortalMessage[]>(
        `/portal/cases/${id}/messages${pageParam ? '?cursor=' + encodeURIComponent(pageParam) : ''}`,
        { signal },
      ),
    getNextPageParam: (last) =>
      last.meta.has_more ? (last.meta.next_cursor ?? undefined) : undefined,
    refetchInterval: poll,
  });
  useHeadingFocus('page-heading', !!query.data);
  if (query.isPending) return <Loading label="Loading request..." />;
  if (query.error)
    return (
      <>
        <ErrorMessage error={query.error} />
        <Link to="/portal">Back to your requests</Link>
      </>
    );
  const row = query.data.data;
  const back = (location.state as { from?: string } | null)?.from;
  return (
    <div className="portal-reading">
      <Link to={back?.startsWith('/portal?') ? back : '/portal'}>
        Back to your requests
      </Link>
      <h1 id="page-heading" tabIndex={-1}>
        {row.subject}
      </h1>
      <p>
        {reference(row.number)} · {row.state_label}
      </p>
      <p>{explanations[row.state]}</p>
      <section
        className="conversation work-surface"
        aria-label="Public conversation"
      >
        <h2>Conversation</h2>
        {messages.isPending ? (
          <Loading label="Loading public messages..." />
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
          <ol className="message-list">
            {messages.data?.pages
              .flatMap((page) => page.data)
              .map((message) => (
                <li key={message.id}>
                  <h3>{message.author_display}</h3>
                  <time className="metadata" dateTime={message.created_at}>
                    {dateTime(message.created_at, identity!.timezone)}
                  </time>
                  <p className="message-body">{message.body}</p>
                  {message.message_kind === 'resolution' && (
                    <p className="small-reading">Resolution</p>
                  )}
                </li>
              ))}
          </ol>
        )}
        {messages.hasNextPage && (
          <button
            className="button secondary"
            disabled={messages.isFetchingNextPage}
            onClick={() => void messages.fetchNextPage()}
          >
            Load more messages
          </button>
        )}
      </section>
      <PortalReply
        key={row.id}
        row={row}
        refresh={async () => {
          await Promise.all([
            client.invalidateQueries({
              queryKey: [identity?.workspace_id, 'portal', 'case', id],
            }),
            client.invalidateQueries({
              queryKey: [identity?.workspace_id, 'portal', 'messages', id],
            }),
            client.invalidateQueries({
              queryKey: [identity?.workspace_id, 'portal', 'cases'],
            }),
          ]);
        }}
      />
      {row.field_definitions.length > 0 && (
        <details className="work-surface portal-details">
          <summary>Request details</summary>
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
        </details>
      )}
    </div>
  );
}

function PortalReply({
  row,
  refresh,
}: {
  row: PortalCase;
  refresh: () => Promise<void>;
}) {
  const [draft, setDraft] = useState('');
  const [version, setVersion] = useState(row.version);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [notice, setNotice] = useState('');
  const [invalid, setInvalid] = useState(false);
  const [attempts, setAttempts] = useState(0);
  const keys = useReplayKeys();
  const [reviewedState, setReviewedState] = useState(row.state);
  const isReopen = row.state === 'resolved';
  const path = `/portal/cases/${row.id}/${isReopen ? 'reopen' : 'messages'}`;
  const client = useQueryClient();
  const { identity } = useSession();
  const dirty = draft.length > 0;
  const messages = useMemo(
    () =>
      invalid
        ? [
            {
              field: 'portal-reply',
              message: isReopen
                ? 'Describe what still needs attention.'
                : 'Enter your reply.',
            },
          ]
        : [],
    [invalid, isReopen],
  );
  if (row.state === 'closed')
    return (
      <section className="portal-details work-surface">
        <h2>This request is closed</h2>
        <p>Create a related request if you need more help.</p>
        <Link className="button" to={`/portal/new?related=${row.id}`}>
          Create a related request
        </Link>
      </section>
    );
  return (
    <>
      <UnsavedChanges dirty={dirty && !pending} />
      <p role="status">{notice}</p>
      <form
        className="work-surface form-surface"
        noValidate
        onSubmit={async (event) => {
          event.preventDefault();
          setAttempts((value) => value + 1);
          setInvalid(!draft.trim());
          if (!draft.trim()) return;
          setPending(true);
          setError(null);
          setNotice('');
          const body = isReopen ? { message: draft } : { body: draft };
          try {
            await api(path, {
              method: 'POST',
              version: dirty ? version : row.version,
              body,
              idempotencyKey: keys.keyFor(path, body),
            });
            keys.completed(path, body);
            setDraft('');
            setNotice(isReopen ? 'Request reopened.' : 'Reply posted.');
            await refresh();
          } catch (failure) {
            setError(failure as Error);
          } finally {
            setPending(false);
          }
        }}
      >
        <h2>{isReopen ? 'What still needs attention?' : 'Your reply'}</h2>
        {reviewedState !== row.state && dirty && (
          <p>
            The request state changed. Review the conversation before posting.
          </p>
        )}
        <p className="small-reading">
          {isReopen
            ? 'The support team will see this message when you reopen the request.'
            : 'Your reply will be visible in this request.'}
        </p>
        <ErrorMessage error={error} />
        <ConflictReview<PortalCase>
          error={error}
          path={`/portal/cases/${row.id}`}
          accept={(latest) => {
            setVersion(latest.data.version);
            setError(null);
            client.setQueryData(
              [identity?.workspace_id, 'portal', 'case', row.id],
              latest,
            );
            setReviewedState(latest.data.state);
          }}
        />
        <ValidationSummary submitCount={attempts} messages={messages} />
        <label htmlFor="portal-reply">
          {isReopen ? 'Reopening message' : 'Reply'}
        </label>
        <textarea
          id="portal-reply"
          value={draft}
          maxLength={isReopen ? 4000 : 10000}
          disabled={pending}
          aria-invalid={invalid}
          onChange={(event) => {
            if (!dirty) setVersion(row.version);
            setDraft(event.target.value);
          }}
        />
        <button className="button" disabled={pending}>
          {pending
            ? 'Posting reply...'
            : isReopen
              ? 'Reopen request'
              : 'Post reply'}
        </button>
      </form>
    </>
  );
}
