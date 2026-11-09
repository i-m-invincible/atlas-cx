import { useInfiniteQuery } from '@tanstack/react-query';
import { Temporal } from '@js-temporal/polyfill';
import { api } from '../../api/client';
import type { components } from '../../api/schema';
import { useSession } from '../identity/session';

export type EventRecord = components['schemas']['EventView'];
export type EventDefinition = components['schemas']['DefinitionView'];
export type TimelineEntry = components['schemas']['TimelineEntry'];
export type Report = components['schemas']['Overview'];
export type MetricRecord = components['schemas']['MetricRecord'];

export function useRows<T>(path: string) {
  const { identity } = useSession();
  return useInfiniteQuery({
    queryKey: [identity?.workspace_id, 'staff', 'activity-rows', path],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ signal, pageParam }) => {
      const [resource, query] = path.split('?');
      const params = new URLSearchParams(query);
      if (pageParam) params.set('cursor', pageParam);
      return api<T[]>(resource + '?' + params.toString(), { signal });
    },
    getNextPageParam: (last) =>
      last.meta.has_more ? (last.meta.next_cursor ?? undefined) : undefined,
  });
}

export function localMidnight(date: string, zone: string) {
  return date
    ? Temporal.PlainDate.from(date).toZonedDateTime(zone).toInstant().toString()
    : undefined;
}
