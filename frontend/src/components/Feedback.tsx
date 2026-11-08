import { useEffect, useRef } from 'react';
import { ApiError } from '../api/client';

export function ErrorMessage({ error }: { error: Error | null }) {
  const summary = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (error) summary.current?.focus();
  }, [error]);
  if (!error) return null;
  return (
    <div className="error-message" role="alert" tabIndex={-1} ref={summary}>
      <p>
        {error instanceof ApiError
          ? error.message
          : 'The service couldn’t be reached. Your changes are still here. Try again.'}
      </p>
      {error instanceof ApiError && error.problem.field_errors && (
        <ul>
          {error.problem.field_errors.map((field) => (
            <li key={field.path}>
              {field.path.replace('body.', '')}: {field.message}
            </li>
          ))}
        </ul>
      )}
      {error instanceof ApiError && error.problem.request_id && (
        <details>
          <summary>Request details</summary>
          <p>Reference: {error.problem.request_id}</p>
        </details>
      )}
    </div>
  );
}

export function Loading({ label }: { label: string }) {
  return (
    <p role="status" aria-busy="true">
      {label}
    </p>
  );
}
