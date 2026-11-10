import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { api, queryString } from '../../api/client';
import type { Customer } from '../../api/client';
import { ErrorMessage, Loading } from '../../components/Feedback';
import { useSession } from '../identity/session';
import { dateTime } from '../support/data';
import { localMidnight, useRows } from './data';
import type { EventRecord, TimelineEntry } from './data';

function More({
  label,
  pending,
  load,
}: {
  label: string;
  pending: boolean;
  load: () => void;
}) {
  return (
    <button
      className="button secondary"
      type="button"
      disabled={pending}
      onClick={load}
    >
      {pending ? 'Loading…' : label}
    </button>
  );
}

function Properties({ event }: { event: EventRecord }) {
  const entries = Object.entries(event.properties).sort(([a], [b]) =>
    a.localeCompare(b),
  );
  return (
    <>
      <p className="small-reading">
        {event.counts_as_activity
          ? 'Recorded as meaningful activity at ingestion.'
          : 'Recorded event. It did not count as meaningful activity at ingestion.'}
      </p>
      <p className="small-reading">
        Event ID <code>{event.external_event_id}</code>
      </p>
      {entries.length ? (
        <dl className="record-details activity-properties">
          {entries.map(([key, value]) => (
            <div key={key}>
              <dt>{key}</dt>
              <dd>
                {typeof value === 'string'
                  ? value || 'Empty text'
                  : String(value)}
              </dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="small-reading">No properties recorded.</p>
      )}
    </>
  );
}

function EventTimes({ event, zone }: { event: EventRecord; zone: string }) {
  return (
    <p className="small-reading">
      Occurred{' '}
      <time dateTime={event.occurred_at}>
        {dateTime(event.occurred_at, zone)}
      </time>
      {' · Received '}
      <time dateTime={event.received_at}>
        {dateTime(event.received_at, zone)}
      </time>
    </p>
  );
}

export function CustomerActivity({
  customer,
  analytics = false,
}: {
  customer: Customer;
  analytics?: boolean;
}) {
  const { identity } = useSession();
  const { state } = useLocation();
  const [params, setParams] = useSearchParams();
  const [error, setError] = useState('');
  const zone = identity?.timezone ?? 'UTC';
  const name = params.get('event_name') ?? '';
  const from = params.get('event_from') ?? '';
  const to = params.get('event_to') ?? '';
  const eventId = params.get('event');
  const path = '/customers/' + customer.id + '/events';
  const utcDate = (value: string) => {
    try {
      return localMidnight(value, zone);
    } catch {
      return undefined;
    }
  };
  const query = useRows<EventRecord>(
    path +
      '?' +
      queryString({
        event_name: name,
        from: utcDate(from),
        to: utcDate(to),
      }),
  );
  const selected = useQuery({
    queryKey: [identity?.workspace_id, 'staff', 'event', customer.id, eventId],
    queryFn: ({ signal }) => api<EventRecord>(path + '/' + eventId, { signal }),
    enabled: !!eventId,
  });
  const rows = query.data?.pages.flatMap((page) => page.data) ?? [];
  function apply(values: Record<string, string>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(values)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    next.delete('event');
    setParams(next, { state });
  }

  return (
    <section
      className={
        analytics
          ? 'work-surface surface-padding activity-panel'
          : 'activity-panel'
      }
      aria-labelledby="recorded-activity"
    >
      <h2 id="recorded-activity">Recorded activity</h2>
      <p className="small-reading">Times shown in {zone}.</p>
      {analytics && (
        <Link to={'/app/customers/' + customer.id + '?view=activity'}>
          Open Customer 360
        </Link>
      )}
      <details className="report-filter-disclosure" open>
        <summary>Event filters</summary>
        <form
          className="activity-filters"
          key={[name, from, to].join('|')}
          onSubmit={(event) => {
            event.preventDefault();
            const form = new FormData(event.currentTarget);
            const start = String(form.get('from'));
            const end = String(form.get('to'));
            if (start && end && start >= end) {
              setError('Choose an end date after the start date.');
              return;
            }
            setError('');
            apply({
              event_name: String(form.get('name')).trim(),
              event_from: start,
              event_to: end,
            });
          }}
        >
          <label>
            Event name{' '}
            <input
              name="name"
              pattern="[a-z0-9_]{1,50}"
              maxLength={50}
              defaultValue={name}
              placeholder="e.g. feature_used"
            />
          </label>
          <label>
            From <input name="from" type="date" defaultValue={from} />
          </label>
          <label>
            To (exclusive) <input name="to" type="date" defaultValue={to} />
          </label>
          <div className="activity-actions">
            <button className="button">Apply filters</button>
            <button
              type="button"
              className="text-button"
              onClick={() => {
                setError('');
                apply({ event_name: '', event_from: '', event_to: '' });
              }}
            >
              Reset
            </button>
          </div>
        </form>
      </details>
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
      {eventId && (
        <section className="ruled-section" aria-label="Selected event">
          <button
            type="button"
            className="text-button"
            onClick={() => apply({})}
          >
            Close event details
          </button>
          {selected.isPending ? (
            <Loading label="Loading event…" />
          ) : selected.error ? (
            <ErrorMessage error={selected.error} />
          ) : (
            selected.data && (
              <>
                <h3>{selected.data.data.event_label}</h3>
                <EventTimes event={selected.data.data} zone={zone} />
                <Properties event={selected.data.data} />
              </>
            )
          )}
        </section>
      )}
      {query.isPending ? (
        <Loading label="Loading activity…" />
      ) : query.isError && !rows.length ? (
        <>
          <p role="alert">Activity couldn’t be loaded.</p>
          <button
            className="button secondary"
            onClick={() => void query.refetch()}
          >
            Retry activity
          </button>
        </>
      ) : rows.length ? (
        <ul className="activity-rows">
          {rows.map((event) => (
            <li key={event.id}>
              <details>
                <summary>
                  <strong>{event.event_label}</strong>{' '}
                  <code>{event.event_name}</code>
                </summary>
                <Properties event={event} />
              </details>
              <EventTimes event={event} zone={zone} />
            </li>
          ))}
        </ul>
      ) : (
        <>
          <p>
            {analytics || name || from || to
              ? 'No events in this period.'
              : 'No activity has been recorded for this customer.'}
          </p>
          {customer.activity_expected && (
            <p className="small-reading">
              Check the tracking setup before drawing conclusions about
              activity.
            </p>
          )}
        </>
      )}
      {query.isFetchNextPageError && <ErrorMessage error={query.error} />}
      {query.hasNextPage && (
        <More
          label="Load more events"
          pending={query.isFetchingNextPage}
          load={() => void query.fetchNextPage()}
        />
      )}
    </section>
  );
}

const kinds = {
  message: 'Messages',
  transition: 'State changes',
  event: 'Recorded events',
  task: 'Follow-ups',
  feedback: 'Feedback',
};
const kindLabels = {
  message: 'Message',
  transition: 'State change',
  event: 'Recorded event',
  task: 'Follow-up',
  feedback: 'Feedback',
};

export function Timeline({ customerId }: { customerId: string }) {
  const { identity } = useSession();
  const { state } = useLocation();
  const [params, setParams] = useSearchParams();
  const selected = params.get('kinds') ?? '';
  const query = useRows<TimelineEntry>(
    '/customers/' +
      customerId +
      '/timeline?' +
      queryString({ kinds: selected }),
  );
  const rows = query.data?.pages.flatMap((page) => page.data) ?? [];
  return (
    <section className="activity-panel" aria-labelledby="timeline-title">
      <h2 id="timeline-title">Timeline</h2>
      <form
        className="timeline-filters"
        key={selected}
        onSubmit={(event) => {
          event.preventDefault();
          const values = new FormData(event.currentTarget).getAll('kind');
          const next = new URLSearchParams(params);
          if (
            values.length === 0 ||
            values.length === Object.keys(kinds).length
          )
            next.delete('kinds');
          else next.set('kinds', values.join(','));
          setParams(next, { state });
        }}
      >
        <fieldset>
          <legend>Include in timeline</legend>
          <div className="timeline-kinds">
            {Object.entries(kinds).map(([key, label]) => (
              <label key={key} className="checkbox-label">
                <input
                  type="checkbox"
                  name="kind"
                  value={key}
                  defaultChecked={
                    !selected || selected.split(',').includes(key)
                  }
                />
                {label}
              </label>
            ))}
          </div>
        </fieldset>
        <button className="button secondary">Apply timeline filters</button>
      </form>
      {query.isPending ? (
        <Loading label="Loading timeline…" />
      ) : query.isError && !rows.length ? (
        <>
          <ErrorMessage error={query.error} />
          <button
            className="button secondary"
            onClick={() => void query.refetch()}
          >
            Retry timeline
          </button>
        </>
      ) : rows.length ? (
        <ol className="activity-rows">
          {rows.map((row) => {
            const target =
              row.kind === 'event'
                ? '?view=activity&event=' + row.reference_id
                : row.kind === 'task'
                  ? '/app/follow-ups/tasks/' + row.reference_id
                  : '/app/support/cases/' + row.reference_id;
            return (
              <li key={row.kind + row.id + row.occurred_at}>
                <p className="small-reading">
                  {kindLabels[row.kind]} · {row.actor} ·{' '}
                  <time dateTime={row.occurred_at}>
                    {dateTime(row.occurred_at, identity?.timezone ?? 'UTC')}
                  </time>
                </p>
                <Link
                  to={target}
                  state={row.kind === 'event' ? state : undefined}
                >
                  {row.title}
                </Link>
                {row.preview && <p className="small-reading">{row.preview}</p>}
              </li>
            );
          })}
        </ol>
      ) : (
        <p>No timeline entries match these filters.</p>
      )}
      {query.isFetchNextPageError && <ErrorMessage error={query.error} />}
      {query.hasNextPage && (
        <More
          label="Load more timeline entries"
          pending={query.isFetchingNextPage}
          load={() => void query.fetchNextPage()}
        />
      )}
    </section>
  );
}
