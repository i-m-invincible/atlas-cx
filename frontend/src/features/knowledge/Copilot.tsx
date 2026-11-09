import { Fragment, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api, ApiError } from '../../api/client';
import type { components } from '../../api/schema';
import { ErrorMessage, Loading } from '../../components/Feedback';
import { useSession } from '../identity/session';
import { reference, useReplayKeys } from '../support/data';
import type { CaseDetail } from '../support/data';
import { base, knowledge, replyDraftKey } from './data';
import type { Answer } from './data';
import { KnowledgeHeader, SourceReference } from './shared';

type Availability = components['schemas']['Availability'];
const assistantRequests = '/assistant/requests';

function pending(row?: Answer) {
  return row?.state === 'queued' || row?.state === 'running';
}

function DraftText({ row }: { row: Answer }) {
  return row.answer_text?.split(/\n\n+/).map((paragraph, index) => (
    <p key={index} className="knowledge-text">
      {paragraph.split(/(\[S[1-6]\])/g).map((part, i) => {
        const source = /^\[S[1-6]\]$/.test(part)
          ? row.sources.find((item) => '[' + item.label + ']' === part)
          : null;
        return source ? (
          <Link
            key={i}
            aria-label={part + ' · ' + source.title}
            to={base + '/sources/' + source.chunk_id}
          >
            {part}
          </Link>
        ) : (
          <Fragment key={i}>{part}</Fragment>
        );
      })}
    </p>
  ));
}

export function Copilot() {
  const { identity } = useSession();
  return (
    <>
      <KnowledgeHeader />
      {identity?.permissions.includes('assistant:ask') ? (
        <QuestionWorkspace />
      ) : (
        <p>You don’t have permission to ask the assistant.</p>
      )}
    </>
  );
}

function QuestionWorkspace() {
  const { identity } = useSession();
  const client = useQueryClient();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const requestId = params.get('request');
  const caseId = params.get('case');
  const [question, setQuestion] = useState('');
  const [submitted, setSubmitted] = useState('');
  const [error, setError] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);
  const keys = useReplayKeys();
  const scope = [identity?.workspace_id, 'staff'] as const;
  const requestKey = [...scope, 'assistant', requestId] as const;
  const response = useQuery({
    queryKey: requestKey,
    queryFn: ({ signal }) =>
      api<Answer>(assistantRequests + '/' + requestId, { signal }),
    enabled: !!requestId,
    gcTime: 0,
    retry: false,
    refetchInterval: (query) => {
      if (!pending(query.state.data?.data)) return false;
      const reads = query.state.dataUpdateCount;
      return reads < 2
        ? 1000
        : Math.min(4800, 2000 + Math.max(0, reads - 2) * 500) +
            Math.random() * 200;
    },
    refetchIntervalInBackground: false,
  });
  const context = useQuery({
    queryKey: [...scope, 'assistant-case', caseId],
    queryFn: ({ signal }) => api<CaseDetail>('/cases/' + caseId, { signal }),
    enabled: !!caseId,
    gcTime: 0,
    retry: false,
  });
  const availability = useQuery({
    queryKey: [...scope, 'knowledge-availability'],
    queryFn: ({ signal }) =>
      api<Availability>(knowledge + '/availability', { signal }),
  });
  const row = response.data?.data;
  const record = context.data?.data;
  const casePath = record ? '/app/support/cases/' + record.id : null;
  const allowDraft =
    row?.mode === 'generated' &&
    !!row.answer_text &&
    record &&
    row.case_id === record.id &&
    ['new', 'open', 'pending_customer'].includes(record.state) &&
    identity?.permissions.includes('cases:write');
  const queued = pending(row);

  async function ask() {
    setBusy(true);
    setError(null);
    const prompt = question.trim();
    const payload = {
      question: prompt,
      ...(record ? { case_id: record.id } : {}),
    };
    try {
      const result = await api<Answer>(assistantRequests, {
        method: 'POST',
        body: payload,
        idempotencyKey: keys.keyFor(assistantRequests, payload),
      });
      keys.completed(assistantRequests, payload);
      client.setQueryData([...scope, 'assistant', result.data.id], result);
      setSubmitted(prompt);
      const next = new URLSearchParams(params);
      next.set('request', result.data.id);
      setParams(next);
    } catch (failure) {
      setError(failure as Error);
    } finally {
      setBusy(false);
    }
  }

  async function copyToReply() {
    if (!record || !casePath || !allowDraft || !row) return;
    setBusy(true);
    setError(null);
    try {
      const [latest, freshCase] = await Promise.all([
        api<Answer>(assistantRequests + '/' + row.id),
        api<CaseDetail>('/cases/' + record.id),
      ]);
      client.setQueryData(requestKey, latest);
      if (
        latest.data.mode !== 'generated' ||
        !latest.data.answer_text ||
        latest.data.case_id !== record.id ||
        !['new', 'open', 'pending_customer'].includes(freshCase.data.state)
      )
        throw new ApiError(409, {
          detail:
            'The answer or case changed. Review the current record before using a draft.',
        });
      client.setQueryData(
        replyDraftKey(identity?.workspace_id, record.id),
        latest.data.answer_text.replace(/[ \t]*\[S[1-6]\]/g, '').trim(),
      );
      client.setQueryData([...scope, 'case', record.id], freshCase);
      navigate(casePath);
    } catch (failure) {
      setError(failure as Error);
    } finally {
      setBusy(false);
    }
  }

  async function rate(helpful: boolean) {
    if (!row) return;
    setBusy(true);
    setError(null);
    try {
      const saved = await api<Answer>(
        assistantRequests + '/' + row.id + '/feedback',
        {
          method: 'PUT',
          body: { helpful },
        },
      );
      client.setQueryData(requestKey, saved);
    } catch (failure) {
      setError(failure as Error);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="knowledge-reading">
      <section
        className="work-surface surface-padding knowledge-panel"
        aria-labelledby="ask-title"
      >
        <h2 id="ask-title">Ask your knowledge library</h2>
        <p>
          Answers use approved workspace articles. Review the sources before
          sending a reply.
        </p>
        {availability.data && !availability.data.data.generation_configured && (
          <p className="small-reading">
            Generation is disabled. You can still find source excerpts.
          </p>
        )}
        {caseId &&
          (context.isPending ? (
            <Loading label="Checking linked case…" />
          ) : record ? (
            <Link to={casePath!}>
              Returning to case {reference(record.number)}
            </Link>
          ) : (
            <p className="small-reading">The linked case is unavailable.</p>
          ))}
        <form
          className="compact-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (question.trim()) void ask();
          }}
        >
          <label>
            Your question{' '}
            <textarea
              required
              value={question}
              maxLength={2000}
              onChange={(event) => setQuestion(event.target.value)}
              aria-describedby="question-help"
            />
          </label>
          <p className="small-reading" id="question-help">
            Ask about a policy or procedure. Case conversations and customer
            records stay outside this request.
          </p>
          <button
            className="button knowledge-submit"
            disabled={
              !question.trim() ||
              busy ||
              queued ||
              (!!requestId && response.isPending) ||
              (!!caseId && context.isPending)
            }
          >
            {busy && !requestId ? 'Submitting…' : 'Find an answer'}
          </button>
        </form>
        <ErrorMessage error={error} />
        {!requestId ? (
          <p>Ask a question about your approved knowledge.</p>
        ) : response.isPending ? (
          <Loading label="Loading question status…" />
        ) : response.error ? (
          <>
            <ErrorMessage error={response.error} />
            <button
              type="button"
              className="button secondary"
              onClick={() => void response.refetch()}
            >
              Retry status
            </button>
          </>
        ) : (
          row && (
            <section
              className="ruled-section"
              aria-label="Assistant result"
              aria-live="polite"
            >
              {submitted && (
                <p className="small-reading">Question · {submitted}</p>
              )}
              {row.error_code === 'sources_changed' ? (
                <>
                  <h3>Sources changed</h3>
                  <p>
                    A source changed after this answer was prepared. Ask again
                    to use the current version.
                  </p>
                </>
              ) : row.state === 'queued' ? (
                <p role="status">
                  {row.delayed
                    ? 'Still waiting. You can leave this page and return.'
                    : 'Waiting to search your knowledge…'}
                </p>
              ) : row.state === 'running' ? (
                <p role="status">Finding relevant sources…</p>
              ) : row.state === 'failed' ? (
                <p role="alert">
                  We couldn’t prepare an answer.
                  {question && ' Your question is still here.'}
                </p>
              ) : row.mode === 'sources_only' ? (
                <>
                  <h3>Source excerpts</h3>
                  <p>
                    A generated answer isn’t available. These articles may help.
                  </p>
                </>
              ) : row.mode === 'abstained' ? (
                <p>
                  I couldn’t find enough information in the approved knowledge.
                </p>
              ) : row.mode === 'generated' ? (
                <>
                  <h3>Draft answer</h3>
                  {row.abstention_reason === 'conflicting_evidence' && (
                    <p>
                      The available sources do not give a consistent answer.
                    </p>
                  )}
                  <DraftText row={row} />
                  <p className="small-reading">
                    Review the sources before sending a reply.
                  </p>
                  {allowDraft && (
                    <button
                      type="button"
                      className="button secondary"
                      disabled={busy}
                      onClick={() => void copyToReply()}
                    >
                      Use draft
                    </button>
                  )}
                </>
              ) : null}
              {row.state === 'completed' &&
                row.error_code !== 'sources_changed' && (
                  <div className="form-actions" aria-label="Assistant feedback">
                    <button
                      type="button"
                      className="text-button"
                      aria-pressed={row.feedback === true}
                      disabled={busy}
                      onClick={() => void rate(true)}
                    >
                      Helpful
                    </button>
                    <button
                      type="button"
                      className="text-button"
                      aria-pressed={row.feedback === false}
                      disabled={busy}
                      onClick={() => void rate(false)}
                    >
                      Not helpful
                    </button>
                    {row.feedback !== null && (
                      <p role="status">Feedback saved.</p>
                    )}
                  </div>
                )}
            </section>
          )
        )}
      </section>
      <section
        className="work-surface surface-padding knowledge-panel"
        aria-labelledby="assistant-sources"
      >
        <h2 id="assistant-sources">Sources</h2>
        {row?.sources.length ? (
          <ol className="knowledge-rows">
            {row.sources.map((item) => (
              <SourceReference key={item.chunk_id} item={item} />
            ))}
          </ol>
        ) : (
          <p>
            Sources appear here when a question has matching approved passages.
          </p>
        )}
      </section>
    </div>
  );
}
