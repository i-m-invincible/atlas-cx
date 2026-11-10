import { useState } from 'react';
import { useInfiniteQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import type { components } from '../../api/schema';
import { ErrorMessage, Loading } from '../../components/Feedback';
import { useSession } from '../identity/session';
import { ratingLabels as labels } from '../followups/data';
import { ConflictReview } from '../support/components';
import { dateTime, useReplayKeys } from '../support/data';
import type { PortalCase } from '../support/data';

type Feedback = components['schemas']['FeedbackView'];

export function ResolutionFeedback({ row }: { row: PortalCase }) {
  const { identity } = useSession();
  const client = useQueryClient();
  const keys = useReplayKeys();
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState('');
  const [version, setVersion] = useState<number | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [pending, setPending] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const prefix = '/portal/cases/' + row.id;
  const caseKey = [identity?.workspace_id, 'portal', 'case', row.id];
  const query = useInfiniteQuery({
    queryKey: [identity?.workspace_id, 'portal', 'feedback', row.id],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ signal, pageParam }) =>
      api<Feedback[]>(
        prefix +
          '/feedback' +
          (pageParam ? '?cursor=' + encodeURIComponent(pageParam) : ''),
        { signal },
      ),
    getNextPageParam: (page) => page.meta.next_cursor ?? undefined,
  });
  const history = query.data?.pages.flatMap((page) => page.data) ?? [];
  if (!row.can_rate && !submitted && !history.length && !query.error)
    return null;
  return (
    <section
      className="work-surface m3-surface portal-details"
      aria-label="Resolution feedback"
    >
      <p role="status">{submitted ? 'Feedback submitted.' : ''}</p>
      <ErrorMessage error={error ?? query.error} />
      <ConflictReview<PortalCase>
        error={error}
        path={prefix}
        accept={(latest) => {
          setVersion(latest.data.version);
          setError(null);
          client.setQueryData(caseKey, latest);
        }}
      />
      {row.can_rate && !submitted && (
        <form
          className="compact-form"
          onSubmit={async (event) => {
            event.preventDefault();
            setError(null);
            setPending(true);
            const path =
              prefix + '/cycles/' + row.current_cycle_number + '/feedback';
            const body = { rating, comment: comment.trim() || null };
            try {
              await api<Feedback>(path, {
                method: 'POST',
                body,
                version: version ?? row.version,
                idempotencyKey: keys.keyFor(path, body),
              });
              keys.completed(path, body);
              setSubmitted(true);
              setComment('');
              await Promise.all([
                query.refetch(),
                client.invalidateQueries({ queryKey: caseKey }),
              ]);
            } catch (failure) {
              setError(failure as Error);
            } finally {
              setPending(false);
            }
          }}
        >
          <fieldset className="m3-fields" disabled={pending}>
            <legend>Did this resolve your request?</legend>
            {labels.map((label, index) => (
              <label className="checkbox-label" key={label}>
                <input
                  type="radio"
                  name="resolution-rating"
                  value={index + 1}
                  required
                  checked={rating === index + 1}
                  onChange={() => {
                    setRating(index + 1);
                    setVersion(version ?? row.version);
                  }}
                />
                {index + 1} · {label}
              </label>
            ))}
            <label htmlFor="feedback-comment">Comment · Optional</label>
            <textarea
              id="feedback-comment"
              maxLength={2000}
              value={comment}
              onChange={(event) => {
                setComment(event.target.value);
                setVersion(version ?? row.version);
              }}
            />
          </fieldset>
          <button className="button" disabled={pending}>
            {pending ? 'Submitting feedback…' : 'Submit feedback'}
          </button>
        </form>
      )}
      {history.length > 0 && (
        <>
          <h2>Your submitted ratings</h2>
          <ul className="message-list">
            {history.map((item) => (
              <li key={item.id}>
                <p>
                  {item.rating} of 5 · {labels[item.rating - 1]}
                </p>
                <p>
                  Resolution cycle {item.cycle_number} ·{' '}
                  {dateTime(item.created_at, identity!.timezone)}
                </p>
                {item.comment && <p className="message-body">{item.comment}</p>}
              </li>
            ))}
          </ul>
        </>
      )}
      {query.isPending && <Loading label="Loading ratings…" />}
      {query.hasNextPage && (
        <button
          className="button secondary"
          onClick={() => void query.fetchNextPage()}
        >
          Load more ratings
        </button>
      )}
    </section>
  );
}
