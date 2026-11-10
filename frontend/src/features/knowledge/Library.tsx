import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from 'react-router-dom';
import { api, queryString } from '../../api/client';
import { ErrorMessage } from '../../components/Feedback';
import { useSession } from '../identity/session';
import { dateTime, useReplayKeys } from '../support/data';
import { base, indexError, knowledge, useKnowledgePages } from './data';
import type {
  Doc,
  DocDetail,
  Job,
  Publication,
  Revision,
  RevisionView,
  Source,
} from './data';
import {
  ArticleText,
  KnowledgeHeader,
  QueryState,
  SourceReference,
} from './shared';

function stateLabel(state: string) {
  return state.charAt(0).toUpperCase() + state.slice(1);
}

function SourceSearch() {
  const { identity } = useSession();
  const [q, setQ] = useState('');
  const result = useQuery({
    queryKey: [identity?.workspace_id, 'staff', 'knowledge-search', q],
    queryFn: ({ signal }) =>
      api<Source[]>(knowledge + '/search?' + queryString({ q }), { signal }),
    enabled: !!q,
    gcTime: 0,
  });
  return (
    <section
      className="work-surface surface-padding knowledge-panel"
      aria-labelledby="source-search"
    >
      <h2 id="source-search">Search approved sources</h2>
      <form
        className="knowledge-filter"
        onSubmit={(event) => {
          event.preventDefault();
          setQ(String(new FormData(event.currentTarget).get('q')).trim());
        }}
      >
        <label>
          Words or phrases{' '}
          <input name="q" type="search" maxLength={200} required />
        </label>
        <button className="button secondary">Search sources</button>
      </form>
      {q && (
        <QueryState
          pending={result.isPending}
          error={result.error}
          retry={() => void result.refetch()}
          label="Searching approved sources…"
        >
          {result.data?.data.length ? (
            <ul className="knowledge-rows">
              {result.data.data.map((item) => (
                <SourceReference key={item.chunk_id} item={item} />
              ))}
            </ul>
          ) : (
            <p>No approved passages match this search.</p>
          )}
        </QueryState>
      )}
    </section>
  );
}

export function Library() {
  const { identity } = useSession();
  const [params, setParams] = useSearchParams();
  const manager = identity?.permissions.includes('knowledge:manage');
  const search = queryString({
    q: params.get('q'),
    status: manager ? params.get('status') : null,
  });
  const query = useKnowledgePages<Doc[]>(knowledge + '/documents?' + search);
  const rows = query.data?.pages.flatMap((page) => page.data) ?? [];
  return (
    <>
      <KnowledgeHeader />
      <section
        className="work-surface surface-padding knowledge-panel"
        aria-labelledby="library-title"
      >
        <div className="page-heading-row">
          <h2 id="library-title">Library</h2>
          {manager && (
            <div className="form-actions">
              <Link className="button" to={base + '/new'}>
                Add article
              </Link>
              <Link to="/app/settings/jobs">Indexing jobs</Link>
            </div>
          )}
        </div>
        <form
          key={search}
          className="knowledge-filter"
          onSubmit={(event) => {
            event.preventDefault();
            const fields = new FormData(event.currentTarget);
            setParams(
              queryString({
                q: String(fields.get('q')).trim(),
                status: fields.get('status')?.toString(),
              }),
            );
          }}
        >
          <label>
            Article title{' '}
            <input
              name="q"
              type="search"
              maxLength={200}
              defaultValue={params.get('q') ?? ''}
            />
          </label>
          {manager && (
            <label>
              Status{' '}
              <select name="status" defaultValue={params.get('status') ?? ''}>
                <option value="">Current articles</option>
                {[
                  'published',
                  'draft',
                  'queued',
                  'indexing',
                  'failed',
                  'archived',
                ].map((state) => (
                  <option key={state} value={state}>
                    {stateLabel(state)}
                  </option>
                ))}
              </select>
            </label>
          )}
          <button className="button secondary">Apply filters</button>
          <button
            type="button"
            className="text-button"
            onClick={() => setParams({})}
          >
            Reset
          </button>
        </form>
        <QueryState
          pending={query.isPending}
          error={query.error}
          retry={() => void query.refetch()}
          label="Loading articles…"
        >
          {rows.length ? (
            <table className="knowledge-table">
              <caption>Knowledge articles</caption>
              <thead>
                <tr>
                  <th scope="col">Article</th>
                  <th scope="col">Active revision</th>
                  <th scope="col">Status</th>
                  <th scope="col">Updated</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <th scope="row">
                      <Link to={base + '/' + row.id}>{row.title}</Link>
                    </th>
                    <td>
                      <span className="mobile-label">Active revision </span>
                      {row.active_revision_number ?? '—'}
                    </td>
                    <td>
                      <span className="mobile-label">Status </span>
                      {row.archived_at
                        ? 'Archived'
                        : row.latest_revision?.id === row.active_version_id
                          ? 'Published'
                          : stateLabel(row.latest_revision?.status ?? 'draft')}
                    </td>
                    <td>
                      <span className="mobile-label">Updated </span>
                      <time dateTime={row.updated_at}>
                        {dateTime(row.updated_at, identity?.timezone ?? 'UTC')}
                      </time>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p>
              {search
                ? 'No articles match these filters.'
                : 'No approved articles yet.'}
              {!search && !manager && ' Ask a manager to publish an article.'}
            </p>
          )}
        </QueryState>
        {query.hasNextPage && (
          <button
            type="button"
            className="button secondary"
            disabled={query.isFetchingNextPage}
            onClick={() => void query.fetchNextPage()}
          >
            Load more articles
          </button>
        )}
      </section>
      <SourceSearch />
    </>
  );
}

function DraftForm({
  existing,
  onSaved,
}: {
  existing?: Doc;
  onSaved: (revision: Revision) => void;
}) {
  const [method, setMethod] = useState<'paste' | 'upload'>('paste');
  const [error, setError] = useState<Error | null>(null);
  const [saving, setSaving] = useState(false);
  return (
    <form
      className="compact-form"
      onSubmit={async (event) => {
        event.preventDefault();
        const data = new FormData(event.currentTarget);
        setError(null);
        setSaving(true);
        try {
          const path =
            knowledge + '/documents' + (existing ? '/' + existing.id : '');
          if (method === 'upload') {
            const file = data.get('file');
            if (!(file instanceof File) || !file.size || file.size > 1048576) {
              setError(new Error('Choose a TXT or Markdown file up to 1 MiB.'));
              return;
            }
            const upload = new FormData();
            upload.set('file', file);
            if (!existing) upload.set('title', String(data.get('title')));
            const result = await api<Revision>(
              path + (existing ? '/upload-version' : '/upload'),
              {
                method: 'POST',
                body: upload,
                version: existing?.version,
              },
            );
            onSaved(result.data);
          } else {
            const result = await api<Revision>(
              path + (existing ? '/versions' : ''),
              {
                method: 'POST',
                version: existing?.version,
                body: {
                  title: String(data.get('title')),
                  content_text: data.get('content'),
                  source_kind: 'pasted',
                },
              },
            );
            onSaved(result.data);
          }
        } catch (failure) {
          setError(failure as Error);
        } finally {
          setSaving(false);
        }
      }}
    >
      {(!existing || method === 'paste') && (
        <label>
          Article title
          <input
            name="title"
            required
            maxLength={200}
            defaultValue={existing?.title ?? ''}
          />
        </label>
      )}
      <label>
        Content source{' '}
        <select
          value={method}
          onChange={(event) =>
            setMethod(event.target.value as 'paste' | 'upload')
          }
        >
          <option value="paste">Pasted text</option>
          <option value="upload">TXT or Markdown upload</option>
        </select>
      </label>
      {method === 'paste' ? (
        <label>
          Article text
          <textarea
            name="content"
            required
            maxLength={200000}
            aria-describedby="text-limit"
          />
        </label>
      ) : (
        <label>
          Text file{' '}
          <input
            name="file"
            type="file"
            required
            accept=".txt,.md,.markdown"
            aria-describedby="text-limit"
          />
        </label>
      )}
      <p className="small-reading" id="text-limit">
        UTF-8 text or Markdown. Up to 1 MiB per file and 200,000 characters per
        revision.
      </p>
      {error &&
        (error.message.startsWith('Choose a TXT') ? (
          <p role="alert">{error.message}</p>
        ) : (
          <ErrorMessage error={error} />
        ))}
      <button className="button" disabled={saving}>
        {saving ? 'Saving draft…' : 'Save draft'}
      </button>
    </form>
  );
}

export function NewArticle() {
  const navigate = useNavigate();
  const { identity } = useSession();
  return (
    <>
      <KnowledgeHeader />
      <Link to={base}>Back to library</Link>
      {identity?.permissions.includes('knowledge:manage') ? (
        <section className="work-surface form-surface">
          <h2>Add article</h2>
          <DraftForm
            onSaved={(revision) =>
              navigate(
                base + '/' + revision.document_id + '?revision=' + revision.id,
              )
            }
          />
        </section>
      ) : (
        <p>You don’t have permission to draft articles.</p>
      )}
    </>
  );
}

function EditDraft({
  row,
  save,
  pending,
}: {
  row: RevisionView;
  save: (values: { title: string; content_text: string }) => void;
  pending: boolean;
}) {
  return (
    <form
      className="compact-form"
      onSubmit={(event) => {
        event.preventDefault();
        const data = new FormData(event.currentTarget);
        save({
          title: String(data.get('title')),
          content_text: String(data.get('text')),
        });
      }}
    >
      <label>
        Draft title{' '}
        <input name="title" required maxLength={200} defaultValue={row.title} />
      </label>
      <label>
        Draft text{' '}
        <textarea
          name="text"
          required
          maxLength={200000}
          defaultValue={row.content_text}
        />
      </label>
      <button className="button" disabled={pending}>
        {pending ? 'Saving…' : 'Save draft changes'}
      </button>
    </form>
  );
}

export function Article() {
  const { documentId } = useParams();
  const { identity } = useSession();
  const client = useQueryClient();
  const [params, setParams] = useSearchParams();
  const [error, setError] = useState<Error | null>(null);
  const [notice, setNotice] = useState('');
  const [pending, setPending] = useState(false);
  const [newDraft, setNewDraft] = useState(false);
  const keys = useReplayKeys();
  const manager = identity?.permissions.includes('knowledge:manage');
  const path = knowledge + '/documents/' + documentId;
  const docQuery = useKnowledgePages<DocDetail>(path, (value) =>
    ['queued', 'indexing'].includes(value.latest_revision?.status ?? ''),
  );
  const doc = docQuery.data?.pages[0]?.data;
  const selected =
    params.get('revision') ??
    doc?.active_version_id ??
    doc?.latest_revision?.id;
  const scope = [identity?.workspace_id, 'staff', 'knowledge'] as const;
  const revision = useQuery({
    queryKey: [...scope, 'revision', selected],
    queryFn: ({ signal }) =>
      api<RevisionView>(knowledge + '/versions/' + selected, { signal }),
    enabled: !!selected,
    refetchInterval: (query) =>
      ['queued', 'indexing'].includes(query.state.data?.data.status ?? '')
        ? 2000
        : false,
  });
  const row =
    revision.data?.data.document_id === documentId
      ? revision.data?.data
      : undefined;
  const revisions =
    docQuery.data?.pages.flatMap((page) => page.data.revisions) ?? [];
  async function refresh() {
    await client.invalidateQueries({ queryKey: scope });
  }
  async function run(action: () => Promise<unknown>, message: string) {
    setPending(true);
    setError(null);
    setNotice('');
    try {
      await action();
      await refresh();
      setNotice(message);
    } catch (failure) {
      setError(failure as Error);
    } finally {
      setPending(false);
    }
  }
  return (
    <>
      <KnowledgeHeader />
      <Link to={base}>Back to library</Link>
      <p role="status">{notice}</p>
      <ErrorMessage error={error} />
      <QueryState
        pending={docQuery.isPending}
        error={docQuery.error}
        retry={() => void docQuery.refetch()}
        label="Loading article…"
      >
        {doc && (
          <div className="knowledge-reading">
            <section className="work-surface surface-padding knowledge-panel">
              <h2>{doc.title}</h2>
              {doc.archived_at && <p>Archived</p>}
              <QueryState
                pending={revision.isPending}
                error={revision.error}
                retry={() => void revision.refetch()}
                label="Loading revision…"
              >
                {row && (
                  <>
                    <p className="small-reading">
                      Revision {row.revision_number} ·{' '}
                      {row.id === row.active_version_id
                        ? 'Published'
                        : stateLabel(row.status)}
                    </p>
                    <p className="small-reading">
                      {row.source_name ??
                        (row.source_kind === 'pasted'
                          ? 'Pasted text'
                          : row.source_kind)}
                    </p>
                    {indexError(row.error_code) && (
                      <p className="field-error">
                        {indexError(row.error_code)}
                      </p>
                    )}
                    {row.status === 'ready' &&
                      doc.active_version_id !== row.id && (
                        <button
                          type="button"
                          className="text-button"
                          onClick={() => void docQuery.refetch()}
                        >
                          Refresh publication status
                        </button>
                      )}
                    {manager && !doc.archived_at && row.status === 'draft' ? (
                      <>
                        <EditDraft
                          key={row.id + row.version}
                          row={row}
                          pending={pending}
                          save={(values) =>
                            void run(
                              () =>
                                api(knowledge + '/versions/' + row.id, {
                                  method: 'PATCH',
                                  body: values,
                                  version: row.version,
                                }),
                              'Draft saved.',
                            )
                          }
                        />
                        <details className="ruled-section">
                          <summary>Review publication</summary>
                          <p>
                            The current article stays available until the new
                            version is ready.
                          </p>
                          <p className="small-reading">
                            This preview shows the saved revision.
                          </p>
                          <ArticleText
                            text={row.content_text}
                            markdown={row.source_kind === 'markdown'}
                          />
                          <button
                            type="button"
                            className="button"
                            disabled={pending}
                            onClick={() => {
                              const route =
                                knowledge + '/versions/' + row.id + '/publish';
                              void run(async () => {
                                await api<Publication>(route, {
                                  method: 'POST',
                                  version: row.version,
                                  idempotencyKey: keys.keyFor(route, {}),
                                });
                                keys.completed(route, {});
                              }, 'Revision queued for indexing.');
                            }}
                          >
                            Publish revision
                          </button>
                        </details>
                      </>
                    ) : (
                      <ArticleText
                        text={row.content_text}
                        markdown={row.source_kind === 'markdown'}
                      />
                    )}
                    {manager &&
                      !doc.archived_at &&
                      row.status === 'failed' &&
                      row.id === doc.pending_version_id && (
                        <button
                          type="button"
                          className="button secondary"
                          disabled={pending}
                          onClick={() =>
                            void run(
                              () =>
                                api(
                                  knowledge + '/versions/' + row.id + '/retry',
                                  { method: 'POST', version: row.version },
                                ),
                              'Revision queued for retry.',
                            )
                          }
                        >
                          Retry indexing
                        </button>
                      )}
                  </>
                )}
              </QueryState>
            </section>
            {manager && (
              <section
                className="work-surface surface-padding knowledge-panel"
                aria-labelledby="revision-history"
              >
                <h2 id="revision-history">Revision history</h2>
                <ul className="knowledge-rows">
                  {revisions.map((item) => (
                    <li key={item.id}>
                      <button
                        type="button"
                        className="text-button"
                        aria-current={selected === item.id ? 'true' : undefined}
                        onClick={() => setParams({ revision: item.id })}
                      >
                        Revision {item.revision_number}
                      </button>
                      <p className="small-reading">
                        {item.id === doc.active_version_id
                          ? 'Published'
                          : stateLabel(item.status)}
                      </p>
                    </li>
                  ))}
                </ul>
                {docQuery.hasNextPage && (
                  <button
                    type="button"
                    className="button secondary"
                    onClick={() => void docQuery.fetchNextPage()}
                  >
                    Load more revisions
                  </button>
                )}
                {!doc.archived_at && (
                  <>
                    <button
                      type="button"
                      className="button secondary"
                      onClick={() => setNewDraft(!newDraft)}
                      aria-expanded={newDraft}
                    >
                      {newDraft ? 'Close new draft form' : 'Add revision'}
                    </button>
                    {newDraft && (
                      <DraftForm
                        existing={doc}
                        onSaved={(item) => {
                          setParams({ revision: item.id });
                          setNewDraft(false);
                          void refresh();
                        }}
                      />
                    )}
                    <details className="ruled-section">
                      <summary>Archive article</summary>
                      <p>
                        Archiving removes this article from search, new answers,
                        and prior source access.
                      </p>
                      <form
                        className="compact-form"
                        onSubmit={(event) => {
                          event.preventDefault();
                          const data = new FormData(event.currentTarget);
                          void run(
                            () =>
                              api(path + '/archive', {
                                method: 'POST',
                                version: doc.version,
                                body: { reason: data.get('reason') },
                              }),
                            'Article archived.',
                          );
                        }}
                      >
                        <label>
                          Reason{' '}
                          <textarea name="reason" required maxLength={1000} />
                        </label>
                        <button className="button secondary" disabled={pending}>
                          Confirm archive
                        </button>
                      </form>
                    </details>
                  </>
                )}
              </section>
            )}
          </div>
        )}
      </QueryState>
    </>
  );
}

export function SourcePage() {
  const { sourceId } = useParams();
  const { identity } = useSession();
  const query = useQuery({
    queryKey: [identity?.workspace_id, 'staff', 'knowledge-source', sourceId],
    queryFn: ({ signal }) =>
      api<Source>(knowledge + '/chunks/' + sourceId, { signal }),
    gcTime: 0,
  });
  return (
    <>
      <KnowledgeHeader />
      <Link to={base}>Back to library</Link>
      <QueryState
        pending={query.isPending}
        error={query.error}
        retry={() => void query.refetch()}
        label="Loading source…"
      >
        {query.data && (
          <section
            className="work-surface surface-padding knowledge-panel"
            aria-label="Source passage"
          >
            <h2>{query.data.data.title}</h2>
            <p className="small-reading">
              Revision {query.data.data.revision_number} ·{' '}
              {query.data.data.heading_path.join(' / ')}
            </p>
            <pre className="knowledge-text">{query.data.data.excerpt}</pre>
            <Link to={base + '/' + query.data.data.document_id}>
              Open article
            </Link>
          </section>
        )}
      </QueryState>
    </>
  );
}

export function IndexingJobs() {
  const { identity } = useSession();
  return (
    <>
      <h1 id="page-heading" tabIndex={-1}>
        Indexing jobs
      </h1>
      <Link to={base}>Back to library</Link>
      {identity?.permissions.includes('knowledge:manage') ? (
        <JobList />
      ) : (
        <p>You don’t have permission to inspect jobs.</p>
      )}
    </>
  );
}

function JobList() {
  const { identity } = useSession();
  const query = useKnowledgePages<Job[]>('/jobs?kind=knowledge_index');
  const rows = query.data?.pages.flatMap((page) => page.data) ?? [];
  return (
    <section
      className="work-surface surface-padding knowledge-panel"
      aria-label="Indexing job status"
    >
      <QueryState
        pending={query.isPending}
        error={query.error}
        retry={() => void query.refetch()}
        label="Loading indexing jobs…"
      >
        {rows.length ? (
          <ul className="knowledge-rows">
            {rows.map((job) => (
              <li key={job.id}>
                <h2>{stateLabel(job.status)}</h2>
                <p>
                  Attempt {job.attempts} · Queued{' '}
                  {dateTime(job.created_at, identity?.timezone ?? 'UTC')}
                </p>
                {job.heartbeat_at && (
                  <p className="small-reading">
                    Last worker heartbeat{' '}
                    {dateTime(job.heartbeat_at, identity?.timezone ?? 'UTC')}
                  </p>
                )}
                {job.last_error_code && (
                  <p>{indexError(job.last_error_code)}</p>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p>No indexing jobs yet.</p>
        )}
      </QueryState>
      {query.hasNextPage && (
        <button
          className="button secondary"
          onClick={() => void query.fetchNextPage()}
        >
          Load more jobs
        </button>
      )}
      <button className="text-button" onClick={() => void query.refetch()}>
        Refresh jobs
      </button>
    </section>
  );
}
