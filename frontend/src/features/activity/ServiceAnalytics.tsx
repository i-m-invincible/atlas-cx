import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router-dom';
import { api, apiPages, queryString } from '../../api/client';
import type { Team } from '../../api/client';
import type { components } from '../../api/schema';
import { ErrorMessage, Loading } from '../../components/Feedback';
import { useSession } from '../identity/session';
import { dateTime } from '../support/data';
import type { CaseConfig } from '../support/data';
import { useRows } from './data';
import type { MetricRecord, Report } from './data';

type Metric = keyof typeof labels;
type Rate = components['schemas']['Rate'];
type Export = 'cases' | 'tasks' | 'feedback';
const labels = {
  backlog: 'Active backlog',
  unassigned: 'Unassigned',
  response_overdue: 'Unanswered overdue',
  resolution_overdue: 'Resolution overdue',
  paused: 'Paused cycles',
  new_cases: 'New cases',
  first_response: 'First response',
  resolution: 'Resolution',
  reopen: 'Reopened within seven days',
  csat: 'Favorable satisfaction',
  coverage: 'Feedback coverage',
  follow_up: 'Follow-ups completed on time',
};

function duration(seconds: number | null) {
  if (seconds === null) return '—';
  const format = (value: number) =>
    new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(
      value,
    );
  if (seconds < 60) return format(seconds) + ' s';
  if (seconds < 3600) return format(seconds / 60) + ' min';
  if (seconds < 86400) return format(seconds / 3600) + ' hr';
  return format(seconds / 86400) + ' days';
}

function share(rate: Rate) {
  const percent =
    rate.share === null
      ? '—'
      : new Intl.NumberFormat(undefined, {
          style: 'percent',
          maximumFractionDigits: 1,
        }).format(rate.share);
  return percent + ' · ' + rate.numerator + ' of ' + rate.denominator;
}

function Records({
  metric,
  scope,
}: {
  metric: Metric;
  scope: Report['scope'];
}) {
  const query = useRows<MetricRecord>(
    '/analytics/records?' +
      queryString({
        metric,
        from: scope.from_at,
        to: scope.to_at,
        timezone: scope.timezone,
        category: scope.category,
        team_id: scope.team_id,
      }),
  );
  const rows = query.data?.pages.flatMap((page) => page.data) ?? [];
  return (
    <section
      className="work-surface surface-padding activity-panel"
      aria-labelledby="report-records"
    >
      <h2 id="report-records">{labels[metric]} records</h2>
      <p className="small-reading">
        Matches this report’s filters. Records are read when you open this view.
      </p>
      {query.isPending ? (
        <Loading label="Loading report records…" />
      ) : query.isError && !rows.length ? (
        <>
          <ErrorMessage error={query.error} />
          <button
            type="button"
            className="button secondary"
            onClick={() => void query.refetch()}
          >
            Retry records
          </button>
        </>
      ) : rows.length ? (
        <ul className="activity-rows">
          {rows.map((row) => (
            <li key={row.id}>
              <Link
                to={
                  row.record_type === 'task'
                    ? '/app/follow-ups/tasks/' + row.reference_id
                    : '/app/support/cases/' + row.reference_id
                }
              >
                {row.title}
              </Link>
              <p className="small-reading">
                {dateTime(row.observed_at, scope.timezone)}
                {row.cycle_number !== null && ' · Cycle ' + row.cycle_number}
                {row.seconds != null && ' · ' + duration(row.seconds)}
                {!row.eligible
                  ? ' · Not yet eligible'
                  : row.meets_measure === null
                    ? ''
                    : row.meets_measure
                      ? ' · Included in numerator'
                      : ' · Denominator only'}
              </p>
            </li>
          ))}
        </ul>
      ) : (
        <p>No records match this measure.</p>
      )}
      {query.isFetchNextPageError && <ErrorMessage error={query.error} />}
      {query.hasNextPage && (
        <button
          type="button"
          className="button secondary"
          disabled={query.isFetchingNextPage}
          onClick={() => void query.fetchNextPage()}
        >
          Load more records
        </button>
      )}
    </section>
  );
}

function CategoryVolume({ categories }: { categories: Report['categories'] }) {
  if (!categories.length) return <p>No cases were created in this period.</p>;
  const max = Math.max(...categories.map((category) => category.count));
  return (
    <>
      <ul className="category-chart" aria-hidden="true">
        {categories.map(({ key, label, count }) => (
          <li key={key}>
            <span>{label}</span>
            <meter min={0} max={max} value={count} /> <strong>{count}</strong>
          </li>
        ))}
      </ul>
      <table className="report-table">
        <caption>New case counts by category</caption>
        <thead>
          <tr>
            <th scope="col">Current category</th>
            <th scope="col">Cases</th>
          </tr>
        </thead>
        <tbody>
          {categories.map(({ key, label, count }) => (
            <tr key={key}>
              <th scope="row">{label}</th>
              <td>{count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function CaseTrend({ trend }: { trend: Report['trend'] }) {
  const max = Math.max(1, ...trend.points.map((point) => point.count));
  const coords = trend.points.map(
    (point, index) =>
      [
        24 +
          (trend.points.length === 1
            ? 376
            : (index * 752) / (trend.points.length - 1)),
        128 - (point.count * 112) / max,
      ] as const,
  );
  return (
    <>
      <details
        className="report-trend"
        open={window.matchMedia('(min-width: 701px)').matches}
      >
        <summary>View trend chart</summary>
        <figure aria-hidden="true">
          <svg className="trend-chart" viewBox="0 0 800 140">
            <line
              className="chart-baseline"
              x1={24}
              y1={128}
              x2={776}
              y2={128}
            />
            <line className="chart-baseline" x1={24} y1={16} x2={776} y2={16} />
            <polyline
              points={coords.map((point) => point.join(',')).join(' ')}
            />
            {coords.length < 55 &&
              coords.map(([x, y]) => <circle key={x} cx={x} cy={y} r={3} />)}
          </svg>
          <figcaption>
            New cases per {trend.bucket} · Scale 0–{max}
          </figcaption>
        </figure>
      </details>
      <details open={trend.points.length <= 7}>
        <summary>View trend data table</summary>
        <table className="report-table">
          <caption>
            New cases per {trend.bucket} in {trend.scope.timezone}
          </caption>
          <thead>
            <tr>
              <th scope="col">
                {trend.bucket === 'week' ? 'Week beginning' : 'Day'}
              </th>
              <th scope="col">New cases</th>
            </tr>
          </thead>
          <tbody>
            {trend.points.map(({ start, count, partial }) => (
              <tr key={start}>
                <th scope="row">
                  <time dateTime={start}>{start}</time>
                  {partial && ' · Partial'}
                </th>
                <td>{count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </>
  );
}

export function ServiceAnalytics() {
  const { identity } = useSession();
  const [params, setParams] = useSearchParams();
  const [metric, setMetric] = useState<Metric | null>(null);
  const [format, setFormat] = useState<Export>('cases');
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState('');
  const [notice, setNotice] = useState('');
  const timezone = identity?.timezone ?? 'UTC';
  const filters = {
    from: params.get('from') ?? '',
    to: params.get('to') ?? '',
    timezone: params.get('timezone') ?? timezone,
    category: params.get('category') ?? '',
    team_id: params.get('team_id') ?? '',
    bucket: params.get('bucket') === 'week' ? 'week' : 'day',
  };
  const search = queryString(filters);
  const privileged = identity?.role === 'admin' || identity?.role === 'manager';
  const report = useQuery({
    queryKey: [identity?.workspace_id, 'staff', 'analytics-overview', search],
    queryFn: ({ signal }) =>
      api<Report>('/analytics/overview?' + search, { signal }),
  });
  const teams = useQuery({
    queryKey: [identity?.workspace_id, 'staff', 'teams'],
    queryFn: ({ signal }) => apiPages<Team>('/teams', signal),
  });
  const configs = useQuery({
    queryKey: [identity?.workspace_id, 'staff', 'analytics-categories'],
    queryFn: ({ signal }) =>
      apiPages<CaseConfig>('/case-configs?status=published', signal),
  });
  const categories = new Map<string, string>();
  for (const config of [...(configs.data?.data ?? [])].reverse()) {
    for (const category of config.definition.categories)
      categories.set(category.key, category.label);
  }
  if (filters.category && !categories.has(filters.category))
    categories.set(filters.category, filters.category);
  const data = report.data?.data;
  const scope = data?.scope;
  async function download() {
    if (!scope) return;
    setExporting(true);
    setExportError('');
    setNotice('');
    try {
      const response = await fetch(
        '/api/v1/analytics/export?' +
          queryString({
            from: scope.from_at,
            to: scope.to_at,
            timezone: scope.timezone,
            category: scope.category,
            team_id: scope.team_id,
            report: format,
          }),
        { credentials: 'same-origin' },
      );
      if (response.status === 401)
        window.dispatchEvent(new Event('atlas:session-expired'));
      if (!response.ok) {
        const problem = await response.json().catch(() => null);
        setExportError(
          problem?.detail ?? 'The CSV couldn’t be downloaded. Try again.',
        );
        return;
      }
      const url = URL.createObjectURL(await response.blob());
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'atlas-' + format + '.csv';
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setNotice('CSV download started.');
    } catch {
      setExportError('The CSV couldn’t be downloaded. Try again.');
    } finally {
      setExporting(false);
    }
  }
  function selectMeasure(key: Metric) {
    return (
      privileged && (
        <button
          type="button"
          className="text-button"
          aria-label={
            (metric === key ? 'Hide records for ' : 'Inspect records for ') +
            labels[key]
          }
          onClick={() => setMetric(metric === key ? null : key)}
          aria-expanded={metric === key}
        >
          {metric === key ? 'Hide records' : 'Inspect records'}
        </button>
      )
    );
  }

  return (
    <>
      <section
        className="work-surface surface-padding activity-panel"
        aria-label="Report filters"
      >
        <details
          className="report-filter-disclosure"
          open={window.matchMedia('(min-width: 701px)').matches}
        >
          <summary>Report filters</summary>
          <form
            className="activity-filters service-filters"
            key={search}
            onSubmit={(event) => {
              event.preventDefault();
              setMetric(null);
              setExportError('');
              setNotice('');
              setParams(
                queryString(
                  Object.fromEntries(
                    new FormData(event.currentTarget),
                  ) as Record<string, string>,
                ),
              );
            }}
          >
            <label>
              From <input type="date" name="from" defaultValue={filters.from} />
            </label>
            <label>
              To (exclusive){' '}
              <input type="date" name="to" defaultValue={filters.to} />
            </label>
            <label>
              Time zone{' '}
              <input
                name="timezone"
                required
                maxLength={100}
                defaultValue={filters.timezone}
              />
            </label>
            <label>
              Current category{' '}
              <select name="category" defaultValue={filters.category}>
                <option value="">All categories</option>
                {[...categories].map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Current team{' '}
              <select name="team_id" defaultValue={filters.team_id}>
                <option value="">All teams</option>
                {filters.team_id &&
                  !teams.data?.data.some(
                    (team) => team.id === filters.team_id,
                  ) && <option value={filters.team_id}>Selected team</option>}
                {teams.data?.data.map((team) => (
                  <option key={team.id} value={team.id}>
                    {team.name}
                    {team.archived_at ? ' (archived)' : ''}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Trend intervals{' '}
              <select name="bucket" defaultValue={filters.bucket}>
                <option value="day">Day</option>
                <option value="week">Week</option>
              </select>
            </label>
            <div className="activity-actions">
              <button className="button">Apply filters</button>
              <button
                type="button"
                className="text-button"
                onClick={() => {
                  setMetric(null);
                  setParams({});
                }}
              >
                Reset
              </button>
            </div>
          </form>
          {(teams.error || configs.error) && (
            <ErrorMessage error={teams.error ?? configs.error} />
          )}
        </details>
        {privileged && (
          <div className="activity-actions report-export">
            <label>
              CSV report{' '}
              <select
                value={format}
                onChange={(event) => setFormat(event.target.value as Export)}
              >
                <option value="cases">Cases</option>
                <option value="tasks">Follow-ups</option>
                <option value="feedback">Feedback</option>
              </select>
            </label>
            <button
              className="button secondary"
              type="button"
              disabled={!scope || exporting}
              onClick={() => void download()}
            >
              {exporting ? 'Preparing CSV…' : 'Export CSV'}
            </button>
          </div>
        )}
        {exportError && (
          <p role="alert" className="field-error">
            {exportError}
          </p>
        )}
        {notice && <p role="status">{notice}</p>}
      </section>
      {report.isPending ? (
        <Loading label="Loading service report…" />
      ) : report.error ? (
        <>
          <ErrorMessage error={report.error} />
          <button
            type="button"
            className="button secondary"
            onClick={() => void report.refetch()}
          >
            Retry report
          </button>
        </>
      ) : (
        data && (
          <>
            <p className="report-scope">
              Period{' '}
              <time dateTime={data.scope.from_at}>
                {dateTime(data.scope.from_at, data.scope.timezone)}
              </time>
              {' to '}
              <time dateTime={data.scope.to_at}>
                {dateTime(data.scope.to_at, data.scope.timezone)}
              </time>
              {' (exclusive) · '}
              {data.scope.timezone}
              <br />
              Updated{' '}
              <time dateTime={data.scope.generated_at}>
                {dateTime(data.scope.generated_at, data.scope.timezone)}
              </time>
              {data.scope.today_partial && ' · Today is partial'}
              {report.isFetching && ' · Updating…'}
            </p>
            <section
              className="work-surface surface-padding activity-panel"
              aria-labelledby="service-now"
            >
              <h2 id="service-now">Now</h2>
              <p className="small-reading">
                Current case state at the updated time, across all creation
                dates.
              </p>
              <dl className="measure-band">
                {(
                  [
                    ['backlog', data.active_backlog],
                    ['unassigned', data.unassigned],
                    ['response_overdue', data.unanswered_overdue],
                    ['resolution_overdue', data.resolution_overdue],
                    ['paused', data.paused],
                  ] as const
                ).map(([key, value]) => (
                  <div key={key}>
                    <dt>{labels[key]}</dt>
                    <dd>
                      {value}
                      {selectMeasure(key)}
                    </dd>
                  </div>
                ))}
              </dl>
            </section>
            <section
              className="work-surface surface-padding activity-panel"
              aria-labelledby="service-period"
            >
              <h2 id="service-period">Service in this period</h2>
              <dl className="measure-rows">
                <div>
                  <dt>{labels.new_cases}</dt>
                  <dd>
                    {data.new_cases}
                    {selectMeasure('new_cases')}
                  </dd>
                </div>
                {(
                  [
                    ['first_response', data.first_response],
                    ['resolution', data.resolution],
                  ] as const
                ).map(([key, value]) => (
                  <div key={key}>
                    <dt>{labels[key]}</dt>
                    <dd>
                      <p>
                        Median {duration(value.median_seconds)} · p90{' '}
                        {duration(value.p90_seconds)}
                      </p>
                      <p className="small-reading">
                        {value.sample_count} observations · Target met{' '}
                        {share(value.attainment)}
                      </p>
                      {selectMeasure(key)}
                    </dd>
                  </div>
                ))}
                {(
                  [
                    ['reopen', data.reopen],
                    ['csat', data.csat],
                    ['coverage', data.coverage],
                    ['follow_up', data.follow_up],
                  ] as const
                ).map(([key, value]) => (
                  <div key={key}>
                    <dt>{labels[key]}</dt>
                    <dd>
                      <p>{share(value)}</p>
                      {(key === 'coverage' || key === 'reopen') && (
                        <p className="small-reading">
                          {data.immature_cycles} cycles resolved less than seven
                          days ago
                          {key === 'coverage'
                            ? ' included as observed'
                            : ' excluded from eligibility'}
                          .
                        </p>
                      )}
                      {key === 'csat' && value.denominator === 0 && (
                        <p className="small-reading">
                          No ratings submitted in this period.
                        </p>
                      )}
                      {selectMeasure(key)}
                    </dd>
                  </div>
                ))}
              </dl>
              <details className="ruled-section">
                <summary>Metric definitions</summary>
                <p>
                  First response measures elapsed time to the first public staff
                  reply. Resolution measures active time per resolved cycle
                  after subtracting pauses. Median and p90 interpolate between
                  recorded durations.
                </p>
                <p>
                  Seven-day reopen rate counts resolved cycles with a full seven
                  days of observation. Satisfaction counts ratings of 4 or 5.
                  Coverage counts resolved cycles with a rating as of this
                  report.
                </p>
                <p>
                  Follow-ups count non-cancelled tasks due in the period by the
                  updated time. A task is on time when completed by its due
                  date.
                </p>
              </details>
            </section>
            {privileged && metric && (
              <Records metric={metric} scope={data.scope} />
            )}
            <section
              className="work-surface surface-padding activity-panel"
              aria-labelledby="category-volume"
            >
              <h2 id="category-volume">Category volume</h2>
              <CategoryVolume categories={data.categories} />
            </section>
            <section
              className="work-surface surface-padding activity-panel"
              aria-labelledby="case-trend"
            >
              <h2 id="case-trend">New case trend</h2>
              <CaseTrend trend={data.trend} />
            </section>
          </>
        )
      )}
    </>
  );
}
