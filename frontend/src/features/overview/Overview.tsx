import { useEffect, useState } from 'react';
import { checkApi } from '../../api/health';

type Status = 'checking' | 'reachable' | 'unavailable';

export function Overview() {
  const [attempt, setAttempt] = useState(0);
  const [status, setStatus] = useState<Status>('checking');

  useEffect(() => {
    const controller = new AbortController();
    checkApi(controller.signal)
      .then(() => setStatus('reachable'))
      .catch(() => {
        if (!controller.signal.aborted) setStatus('unavailable');
      });
    return () => controller.abort();
  }, [attempt]);

  return (
    <>
      <div className="page-introduction">
        <p className="eyebrow">Atlas CX / Project foundation</p>
        <h1 id="page-heading" tabIndex={-1}>
          Overview
        </h1>
        <p className="small-reading">
          Customer operations &amp; service intelligence
        </p>
      </div>
      <section className="work-surface" aria-labelledby="foundation-title">
        <div className="surface-introduction">
          <span className="status-label">Foundation preview</span>
          <h2 id="foundation-title">The workspace foundation is in place.</h2>
          <p>
            Customer records, support requests, and follow-ups will share this
            work surface. These workflows are not available yet.
          </p>
          <p>
            No customer data or operational metrics are shown in this preview.
          </p>
        </div>
        <div className="service-row">
          <div>
            <h3>Service connection</h3>
            <p className="small-reading">Checks whether the API can respond.</p>
          </div>
          <div className="service-result">
            <p
              role="status"
              aria-live="polite"
              aria-busy={status === 'checking'}
            >
              {status === 'checking' && 'Checking service…'}
              {status === 'reachable' && 'API reachable'}
              {status === 'unavailable' && 'Service unavailable. Try again.'}
            </p>
            <button
              className="button secondary"
              disabled={status === 'checking'}
              onClick={() => {
                setStatus('checking');
                setAttempt((value) => value + 1);
              }}
            >
              {status === 'checking' ? 'Checking…' : 'Check connection'}
            </button>
          </div>
        </div>
      </section>
      <footer className="page-footer">Atlas CX · Project initialization</footer>
    </>
  );
}
