import type { components } from './schema';

export type Identity = components['schemas']['IdentityView'];
export type Customer = components['schemas']['CustomerView'];
export type Contact = components['schemas']['ContactView'];
export type Member = components['schemas']['MemberView'];
export type Team = components['schemas']['TeamView'];
export type Workspace = components['schemas']['WorkspaceView'];
export type ApiEnvelope<T> = { data: T; meta: components['schemas']['Meta'] };

export class ApiError extends Error {
  constructor(
    public status: number,
    public problem: {
      detail?: string;
      code?: string;
      request_id?: string;
      field_errors?: { path: string; message: string }[];
    },
  ) {
    super(problem.detail ?? 'The request could not be completed.');
  }
}

export async function api<T>(
  path: string,
  options: {
    method?: string;
    body?: unknown;
    version?: number;
    signal?: AbortSignal;
  } = {},
): Promise<ApiEnvelope<T>> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  const method = options.method ?? 'GET';
  if (method !== 'GET') {
    const csrf = await fetch('/api/v1/auth/csrf', {
      credentials: 'same-origin',
      signal: options.signal,
    });
    if (!csrf.ok)
      throw new ApiError(csrf.status, {
        detail: 'We couldn’t prepare this request. Try again.',
      });
    const value: ApiEnvelope<components['schemas']['CsrfView']> =
      await csrf.json();
    headers['X-CSRF-Token'] = value.data.csrf_token;
  }
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';
  if (options.version !== undefined)
    headers['If-Match'] = `"${options.version}"`;
  const response = await fetch(`/api/v1${path}`, {
    method,
    headers,
    credentials: 'same-origin',
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: options.signal,
  });
  if (!response.ok) {
    const problem = await response
      .json()
      .catch(() => ({ detail: 'The service is unavailable. Try again.' }));
    if (response.status === 401 && !path.startsWith('/auth/'))
      window.dispatchEvent(new Event('atlas:session-expired'));
    throw new ApiError(response.status, problem);
  }
  if (response.status === 204)
    return {
      data: undefined as T,
      meta: {
        request_id: response.headers.get('X-Request-ID') ?? '',
        has_more: false,
      },
    };
  return response.json();
}

export function queryString(
  values: Record<string, string | number | boolean | undefined | null>,
) {
  const parameters = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '')
      parameters.set(key, String(value));
  });
  return parameters.toString();
}
