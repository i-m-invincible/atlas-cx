import { useCallback, useEffect, useRef, useState } from 'react';
import type { components } from '../../api/schema';

export type CaseSummary = components['schemas']['CaseSummary'];
export type CaseDetail = components['schemas']['CaseDetail'];
export type PortalCase = components['schemas']['PortalCaseDetail'];
export type PortalSummary = components['schemas']['PortalCaseSummary'];
export type CaseMessage =
  components['schemas']['app__modules__cases__schemas__MessageView'];
export type PortalMessage = components['schemas']['PortalMessageView'];
export type CaseConfig = components['schemas']['ConfigView'];
export type PortalConfig = components['schemas']['PortalConfig'];
export type TransitionResult = components['schemas']['TransitionResult'];
export type HistoryItem = components['schemas']['HistoryView'];
export type CaseField = components['schemas']['PublicField'] & {
  required_on_resolve?: boolean;
};

export const reference = (number: number) =>
  `CX-${String(number).padStart(6, '0')}`;
export const stateLabels: Record<string, string> = {
  new: 'New',
  open: 'Open',
  pending_customer: 'Awaiting customer',
  resolved: 'Resolved',
  closed: 'Closed',
};
export const explanations: Record<string, string> = {
  new: 'Your request has been received.',
  open: 'The team is working on your request.',
  pending_customer: 'The team needs more information from you.',
  resolved: 'The team has provided a resolution.',
  closed: 'This request is closed.',
};
export function dateTime(value: string, timezone: string) {
  return new Intl.DateTimeFormat('en-GB', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: timezone,
  }).format(new Date(value));
}
export function usePolling() {
  const [visible, setVisible] = useState(
    document.visibilityState === 'visible',
  );
  useEffect(() => {
    const changed = () => setVisible(document.visibilityState === 'visible');
    document.addEventListener('visibilitychange', changed);
    return () => document.removeEventListener('visibilitychange', changed);
  }, []);
  return visible ? 15000 : false;
}

// Keep a key across an uncertain retry. A successful action clears it, allowing
// the user to intentionally post identical text again in a later operation.
export function useReplayKeys() {
  const pending = useRef(new Map<string, string>());
  return {
    keyFor: (route: string, body: unknown) => {
      const signature = route + '\0' + JSON.stringify(body);
      const previous = pending.current.get(signature);
      if (previous) return previous;
      const key = crypto.randomUUID();
      pending.current.set(signature, key);
      return key;
    },
    completed: (route: string, body: unknown) =>
      pending.current.delete(route + '\0' + JSON.stringify(body)),
  };
}

export function customValues(form: HTMLFormElement, fields: CaseField[]) {
  const data = new FormData(form);
  return Object.fromEntries(
    fields.map((field) => {
      const raw = data.get(`field-${field.key}`);
      return [
        field.key,
        field.type === 'boolean'
          ? raw === 'on'
          : !raw
            ? null
            : ['integer', 'decimal'].includes(field.type)
              ? Number(raw)
              : raw,
      ];
    }),
  );
}

export function useHeadingFocus(id: string, ready: boolean) {
  useEffect(() => {
    if (!ready) return;
    const frame = requestAnimationFrame(() => {
      // Route focus must not interrupt someone who already started typing.
      if (
        document.activeElement === document.body ||
        document.activeElement?.matches('h1, h2, h3')
      )
        document.getElementById(id)?.focus();
    });
    return () => cancelAnimationFrame(frame);
  }, [id, ready]);
}

export const useStableNotice = () => {
  const [notice, setNotice] = useState('');
  return [
    notice,
    useCallback((value: string) => setNotice(value), []),
  ] as const;
};
