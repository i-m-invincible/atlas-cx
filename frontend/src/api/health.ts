import type { components } from './schema';

type HealthResponse = components['schemas']['HealthResponse'];

export async function checkApi(signal: AbortSignal): Promise<HealthResponse> {
  const response = await fetch('/api/v1/health/live', {
    signal: AbortSignal.any([signal, AbortSignal.timeout(5000)]),
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) throw new Error('Service unavailable');
  const body: HealthResponse = await response.json();
  if (body.data?.status !== 'ok' || typeof body.meta?.request_id !== 'string') {
    throw new Error('Unexpected health response');
  }
  return body;
}
