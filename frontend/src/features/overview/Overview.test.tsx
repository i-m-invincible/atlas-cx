import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Overview } from './Overview';

afterEach(() => vi.unstubAllGlobals());

describe('foundation overview', () => {
  it('reports a real successful health response without inventing metrics', async () => {
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        data: { status: 'ok' },
        meta: { request_id: 'test-request' },
      }),
    });
    vi.stubGlobal('fetch', fetch);
    render(<Overview />);
    expect(await screen.findByText('API reachable')).toBeVisible();
    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/health/live',
      expect.objectContaining({ credentials: 'same-origin' }),
    );
    expect(
      screen.getByText(/No customer data or operational metrics/),
    ).toBeVisible();
  });

  it('shows failure and lets the user retry', async () => {
    const fetch = vi
      .fn()
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          data: { status: 'ok' },
          meta: { request_id: 'retry' },
        }),
      });
    vi.stubGlobal('fetch', fetch);
    render(<Overview />);
    expect(
      await screen.findByText('Service unavailable. Try again.'),
    ).toBeVisible();
    await userEvent.click(
      screen.getByRole('button', { name: 'Check connection' }),
    );
    expect(await screen.findByText('API reachable')).toBeVisible();
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it('does not call an HTTP error a healthy service', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: false, status: 503 }),
    );
    render(<Overview />);
    expect(
      await screen.findByText('Service unavailable. Try again.'),
    ).toBeVisible();
  });

  it('rejects an invalid success payload', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ data: { status: 'pretend-success' } }),
      }),
    );
    render(<Overview />);
    expect(
      await screen.findByText('Service unavailable. Try again.'),
    ).toBeVisible();
  });

  it('prevents duplicate checks while a request is pending', async () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
    const view = render(<Overview />);
    expect(screen.getByRole('button', { name: 'Checking…' })).toBeDisabled();
    const signal = vi.mocked(fetch).mock.calls[0]?.[1]?.signal;
    view.unmount();
    await waitFor(() => expect(signal?.aborted).toBe(true));
  });
});
