import { useInfiniteQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api } from '../../api/client';
import { ErrorMessage, Loading } from '../../components/Feedback';
import { useSession } from '../identity/session';
import { reference } from './data';
import type { CaseSummary } from './data';

export function CustomerCases({
  customerId,
  archived,
}: {
  customerId: string;
  archived: boolean;
}) {
  const { identity } = useSession();
  const query = useInfiniteQuery({
    queryKey: [
      identity?.workspace_id,
      'staff',
      'cases',
      { customer_id: customerId },
    ],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ signal, pageParam }) =>
      api<CaseSummary[]>(
        `/cases?customer_id=${customerId}${pageParam ? '&cursor=' + encodeURIComponent(pageParam) : ''}`,
        { signal },
      ),
    getNextPageParam: (last) =>
      last.meta.has_more ? (last.meta.next_cursor ?? undefined) : undefined,
  });
  const rows = query.data?.pages.flatMap((page) => page.data) ?? [];
  return (
    <section className="ruled-section">
      <h2>Cases</h2>
      {identity?.permissions.includes('cases:write') && !archived && (
        <Link
          className="button secondary"
          to={`/app/support/cases/new?customer=${customerId}`}
        >
          Create case
        </Link>
      )}
      {query.isPending ? (
        <Loading label="Loading customer cases..." />
      ) : query.error ? (
        <>
          <ErrorMessage error={query.error} />
          <button className="text-button" onClick={() => void query.refetch()}>
            Retry customer cases
          </button>
        </>
      ) : rows.length ? (
        <ul className="message-list">
          {rows.map((row) => (
            <li key={row.id}>
              <Link to={`/app/support/cases/${row.id}`}>
                {reference(row.number)} · {row.subject}
              </Link>
              <p>
                {row.state_label} · {row.assignee?.name ?? 'Unassigned'}
              </p>
            </li>
          ))}
        </ul>
      ) : (
        <p>No cases recorded for this customer.</p>
      )}
      {query.hasNextPage && (
        <button
          className="button secondary"
          disabled={query.isFetchingNextPage}
          onClick={() => void query.fetchNextPage()}
        >
          Load more customer cases
        </button>
      )}
    </section>
  );
}
