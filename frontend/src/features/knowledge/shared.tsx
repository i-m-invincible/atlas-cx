import type { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ErrorMessage, Loading } from '../../components/Feedback';
import { useSession } from '../identity/session';
import { base } from './data';
import type { AssistantSource, Source } from './data';

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
