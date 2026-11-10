import { useCallback, useEffect, useRef } from 'react';
import { useBeforeUnload, useBlocker } from 'react-router-dom';

export function ValidationSummary({
  messages,
  submitCount,
}: {
  messages: { field: string; message: string }[];
  submitCount: number;
}) {
  const summary = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (submitCount > 0) summary.current?.focus();
  }, [submitCount]);
  if (messages.length === 0) return null;
  return (
    <div className="error-message" ref={summary} tabIndex={-1} role="alert">
      <p>Review these fields:</p>
      <ul>
        {messages.map((message) => (
          <li key={message.field}>
            <a
              href={`#${message.field}`}
              onClick={(event) => {
                event.preventDefault();
                document.getElementById(message.field)?.focus();
              }}
            >
              {message.message}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function UnsavedChanges({ dirty }: { dirty: boolean }) {
  const blocker = useBlocker(dirty);
  const dialog = useRef<HTMLDialogElement>(null);
  useBeforeUnload(
    useCallback(
      (event) => {
        if (dirty) {
          event.preventDefault();
          event.returnValue = '';
        }
      },
      [dirty],
    ),
  );
  useEffect(() => {
    if (blocker.state === 'blocked') dialog.current?.showModal();
    else dialog.current?.close();
  }, [blocker.state]);
  return (
    <dialog
      className="unsaved-dialog"
      ref={dialog}
      aria-labelledby="unsaved-title"
      onCancel={(event) => {
        event.preventDefault();
        blocker.reset?.();
      }}
      onKeyDown={(event) => {
        if (event.key !== 'Tab') return;
        const buttons = event.currentTarget.querySelectorAll('button');
        const first = buttons[0];
        const last = buttons[buttons.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }}
    >
      <h2 id="unsaved-title">Discard unsaved changes?</h2>
      <p>Your changes are kept only in this tab until you save them.</p>
      <div className="form-actions">
        <button className="button" onClick={() => blocker.reset?.()}>
          Keep editing
        </button>
        <button
          className="button secondary"
          onClick={() => blocker.proceed?.()}
        >
          Discard changes
        </button>
      </div>
    </dialog>
  );
}
