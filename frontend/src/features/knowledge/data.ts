import { useInfiniteQuery } from '@tanstack/react-query';
import { api } from '../../api/client';
import type { components } from '../../api/schema';
import { useSession } from '../identity/session';

export const base = '/app/knowledge';
export const knowledge = '/knowledge';
export type Doc = components['schemas']['DocumentView'];
export type DocDetail = components['schemas']['DocumentDetail'];
export type Revision = components['schemas']['RevisionSummary'];
export type RevisionView = components['schemas']['RevisionView'];
export type Source = components['schemas']['Source'];
export type AssistantSource = components['schemas']['AssistantSource'];
export type Answer = components['schemas']['Answer'];
export type Job = components['schemas']['JobView'];
export type Publication = components['schemas']['Publication'];

export function useKnowledgePages<T>(
  path: string,
  poll?: (first: T) => boolean,
) {
  const { identity } = useSession();
  return useInfiniteQuery({
    queryKey: [identity?.workspace_id, 'staff', 'knowledge', path],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ signal, pageParam }) => {
      const [resource, filter] = path.split('?');
      const query = new URLSearchParams(filter);
      if (pageParam) query.set('cursor', pageParam);
      return api<T>(resource + '?' + query, { signal });
    },
    getNextPageParam: (last) =>
      last.meta.has_more ? (last.meta.next_cursor ?? undefined) : undefined,
    refetchInterval: (query) => {
      const first = query.state.data?.pages[0]?.data;
      return first && poll?.(first) ? 2000 : false;
    },
  });
}

const errors: Record<string, string> = {
  capacity_exceeded:
    'This workspace has reached its active article or passage limit.',
  embedding_unavailable: 'The pinned embedding model is unavailable.',
  embedding_failed: 'The worker could not embed this revision.',
  invalid_index_text: 'The text could not be split into indexable passages.',
  publication_superseded: 'A newer revision was submitted.',
  document_archived: 'The article was archived.',
  lease_expired: 'The indexing worker stopped before finishing.',
};

export function indexError(code: string | null | undefined) {
  return code
    ? (errors[code] ??
        'Indexing could not finish. Review the revision and try again.')
    : '';
}

export function replyDraftKey(workspace: string | undefined, caseId: string) {
  return [workspace, 'staff', 'assistant-reply-draft', caseId] as const;
}
