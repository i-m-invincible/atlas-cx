import type { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ErrorMessage, Loading } from '../../components/Feedback';
import { useSession } from '../identity/session';
import { base } from './data';
import type { AssistantSource, Source } from './data';

export function ArticleText({
  text,
  markdown,
}: {
  text: string;
  markdown: boolean;
}) {
  if (!markdown) return <pre className="knowledge-text">{text}</pre>;
  const blocks: ReactNode[] = [];
  let buffer: string[] = [];
  let fence: string | null = null;

  function flush(code = false) {
    if (!buffer.length) return;
    const content = buffer.join('\n');
    blocks.push(
      code ? (
        <pre className="knowledge-text" key={blocks.length}>
          {content}
        </pre>
      ) : (
        <p className="knowledge-text" key={blocks.length}>
          {content}
        </p>
      ),
    );
    buffer = [];
  }

  for (const line of text.split('\n')) {
    const marker = /^ {0,3}(`{3,}|~{3,})/.exec(line)?.[1];
    if (fence) {
      if (marker?.startsWith(fence) && line.trim() === marker) {
        flush(true);
        fence = null;
      } else buffer.push(line);
    } else if (marker) {
      flush();
      fence = marker;
    } else {
      const heading = /^ {0,3}(#{1,6})[ \t]+(.+)$/.exec(line);
      const depth = heading?.[1]?.length;
      if (depth && heading?.[2]) {
        flush();
        const Tag =
          depth === 1 ? 'h3' : depth === 2 ? 'h4' : depth === 3 ? 'h5' : 'h6';
        blocks.push(
          <Tag key={blocks.length}>
            {heading[2].replace(/[ \t]+#+[ \t]*$/, '')}
          </Tag>,
        );
      } else if (line.trim()) buffer.push(line);
      else flush();
    }
  }
  flush(!!fence);
  return <div className="knowledge-article-text">{blocks}</div>;
}

export function KnowledgeHeader() {
  const { identity } = useSession();
  const path = useLocation().pathname;
  const assistant = path === base + '/assistant';
  return (
    <>
      <h1 id="page-heading" tabIndex={-1}>
        Knowledge
      </h1>
      <nav className="local-navigation" aria-label="Knowledge views">
        <Link to={base} aria-current={assistant ? undefined : 'page'}>
          Library
        </Link>
        {identity?.permissions.includes('assistant:ask') && (
          <Link
            to={base + '/assistant'}
            aria-current={assistant ? 'page' : undefined}
          >
            Assistant
          </Link>
        )}
      </nav>
    </>
  );
}

export function QueryState({
  pending,
  error,
  retry,
  label,
  children,
}: {
  pending: boolean;
  error: Error | null;
  retry: () => void;
  label: string;
  children: ReactNode;
}) {
  if (pending) return <Loading label={label} />;
  if (error)
    return (
      <>
        <ErrorMessage error={error} />
        <button type="button" className="button secondary" onClick={retry}>
          Retry
        </button>
      </>
    );
  return children;
}

export function SourceReference({ item }: { item: Source | AssistantSource }) {
  return (
    <li>
      <h3>
        <Link to={base + '/sources/' + item.chunk_id}>
          {'label' in item ? item.label + ' · ' : ''}
          {item.title}
        </Link>
      </h3>
      <p className="small-reading">
        Revision {item.revision_number}
        {item.heading_path.length ? ' · ' + item.heading_path.join(' / ') : ''}
      </p>
      <p className="knowledge-text">{item.excerpt}</p>
    </li>
  );
}
