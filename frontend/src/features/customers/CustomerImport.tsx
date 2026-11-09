import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../../api/client';
import type { components } from '../../api/schema';
import { ErrorMessage, Loading } from '../../components/Feedback';
import { useSession } from '../identity/session';
import { dateTime, useHeadingFocus, useReplayKeys } from '../support/data';

type ImportView = components['schemas']['ImportView'];
const base = '/app/customers/import';

export function CustomerImport() {
  const { identity } = useSession();
  const { id } = useParams();
  return id || identity?.permissions.includes('customers:import') ? (
    <ImportPage />
  ) : (
    <p>You don’t have permission to import customers.</p>
  );
}

function ImportPage() {
  const { id } = useParams();
  const { identity } = useSession();
  const canImport = identity?.permissions.includes('customers:import');
  const client = useQueryClient();
  const navigate = useNavigate();
  const keys = useReplayKeys();
  const [error, setError] = useState<Error | null>(null);
  const [pending, setPending] = useState(false);
  const [review, setReview] = useState(false);
  const key = [identity?.workspace_id, 'staff', 'customer-import', id];
  const query = useQuery({
    queryKey: key,
    queryFn: ({ signal }) =>
      api<ImportView>('/customer-imports/' + id, { signal }),
    enabled: !!id,
  });
  useHeadingFocus('page-heading', !id || !!query.data);
  const row = query.data?.data;

  return (
    <>
      <Link to="/app/customers">Back to customers</Link>
      <h1 id="page-heading" tabIndex={-1}>
        Import customers
      </h1>
      <ErrorMessage error={error ?? query.error} />
      {!id ? (
        <form
          className="work-surface form-surface"
          onSubmit={async (event) => {
            event.preventDefault();
            const data = new FormData(event.currentTarget);
            setError(null);
            setPending(true);
            try {
              const response = await api<ImportView>(
                '/customer-imports/validate',
                { method: 'POST', body: data },
              );
              client.setQueryData(
                [
                  identity?.workspace_id,
                  'staff',
                  'customer-import',
                  response.data.id,
                ],
                response,
              );
              navigate(base + '/' + response.data.id);
            } catch (failure) {
              setError(failure as Error);
            } finally {
              setPending(false);
            }
          }}
        >
          <label htmlFor="customer-csv">Customer CSV</label>
          <input
            id="customer-csv"
            name="file"
            type="file"
            accept=".csv,text/csv"
            required
            disabled={pending}
            aria-describedby="csv-help"
          />
          <p id="csv-help">
            Use UTF-8 and include external_id, name, and kind. The limit is 1
            MiB and 1,000 rows.
          </p>
          <details>
            <summary>Supported columns</summary>
            <p>
              Optional columns are lifecycle, owner_email, tags separated by
              semicolons, and activity_expected (true or false). Blank optional
              cells leave existing values in place.
            </p>
          </details>
          <button className="button" disabled={pending}>
            {pending ? 'Validating CSV…' : 'Validate CSV'}
          </button>
        </form>
      ) : query.isPending ? (
        <Loading label="Loading import preview…" />
      ) : (
        row && (
          <section
            className="work-surface m3-surface"
            aria-labelledby="import-result"
          >
            <h2 id="import-result">
              {row.status === 'committed'
                ? 'Import complete'
                : row.status === 'expired'
                  ? 'Preview expired'
                  : row.status === 'failed'
                    ? 'Import needs a new preview'
                    : 'Review import preview'}
            </h2>
            <p role="status">
              {row.create_count}{' '}
              {row.status === 'committed' ? 'created' : 'to create'} ·{' '}
              {row.update_count}{' '}
              {row.status === 'committed' ? 'updated' : 'to update'} ·{' '}
              {row.error_count} with errors
            </p>
            {row.status === 'validated' && (
              <p>
                Preview expires {dateTime(row.expires_at, identity!.timezone)}.
              </p>
            )}
            {row.error_count > 0 && (
              <p role="alert">Fix the rows listed below before importing.</p>
            )}
            {row.rows.length > 0 && (
              <div
                className="m3-table-region"
                tabIndex={0}
                role="region"
                aria-label="Customer import rows"
              >
                <table className="case-table">
                  <thead>
                    <tr>
                      <th scope="col">Row</th>
                      <th scope="col">Action</th>
                      <th scope="col">Customer values</th>
                      <th scope="col">Errors</th>
                    </tr>
                  </thead>
                  <tbody>
                    {row.rows.map((item) => (
                      <tr key={item.row}>
                        <th scope="row">{item.row}</th>
                        <td>{item.action}</td>
                        <td>
                          {Object.entries(item.values)
                            .filter(([, value]) => value != null)
                            .map(([name, value]) => (
                              <p key={name}>
                                {name.replaceAll('_', ' ')} ·{' '}
                                {Array.isArray(value)
                                  ? value.join(', ')
                                  : String(value)}
                              </p>
                            ))}
                        </td>
                        <td>
                          {item.errors.map((issue, index) => (
                            <p key={index}>
                              {issue.field} · {issue.message}
                            </p>
                          ))}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {canImport &&
              row.status === 'validated' &&
              row.error_count === 0 && (
                <div className="form-actions">
                  {!review ? (
                    <button className="button" onClick={() => setReview(true)}>
                      Review and confirm
                    </button>
                  ) : (
                    <>
                      <p>
                        Apply these {row.create_count + row.update_count} rows
                        to the current workspace?
                      </p>
                      <button
                        className="button"
                        disabled={pending}
                        onClick={async () => {
                          const path =
                            '/customer-imports/' + row.id + '/commit';
                          setError(null);
                          setPending(true);
                          try {
                            const response = await api<ImportView>(path, {
                              method: 'POST',
                              version: row.version,
                              idempotencyKey: keys.keyFor(path, null),
                            });
                            client.setQueryData(key, response);
                            keys.completed(path, null);
                            await client.invalidateQueries({
                              queryKey: [
                                identity?.workspace_id,
                                'staff',
                                'customers',
                              ],
                            });
                          } catch (failure) {
                            setError(failure as Error);
                            await query.refetch();
                          } finally {
                            setPending(false);
                          }
                        }}
                      >
                        {pending ? 'Importing customers…' : 'Confirm import'}
                      </button>
                      <button
                        className="button secondary"
                        disabled={pending}
                        onClick={() => setReview(false)}
                      >
                        Keep reviewing
                      </button>
                    </>
                  )}
                </div>
              )}
            {canImport && <Link to={base}>Choose another CSV</Link>}
          </section>
        )
      )}
    </>
  );
}
