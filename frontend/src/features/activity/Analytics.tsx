import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { NavLink, useSearchParams } from 'react-router-dom';
import { api } from '../../api/client';
import type { Customer } from '../../api/client';
import { ErrorMessage, Loading } from '../../components/Feedback';
import { useSession } from '../identity/session';
import { CustomerPicker } from '../support/components';
import { CustomerActivity } from './CustomerActivity';
import { ServiceAnalytics } from './ServiceAnalytics';

function ActivityAnalytics() {
  const { identity } = useSession();
  const [params, setParams] = useSearchParams();
  const customerId = params.get('customer') ?? '';
  const customer = useQuery({
    queryKey: [identity?.workspace_id, 'staff', 'customer-option', customerId],
    enabled: !!customerId,
    queryFn: ({ signal }) =>
      api<Customer>('/customers/' + customerId, { signal }),
  });
  const [showPicker, setShowPicker] = useState(!customerId);
  return (
    <>
      <section
        className="work-surface surface-padding activity-panel"
        aria-label="Customer selection"
      >
        {customer.data && (
          <p>
            <strong>{customer.data.data.name}</strong>
          </p>
        )}
        {!showPicker && (
          <button
            type="button"
            className="text-button"
            onClick={() => setShowPicker(true)}
          >
            Change customer
          </button>
        )}
        {showPicker && (
          <CustomerPicker
            value={customerId}
            onChange={(value) => {
              const next = new URLSearchParams(params);
              if (value) next.set('customer', value);
              else next.delete('customer');
              next.delete('event');
              setParams(next);
            }}
          />
        )}
        {!customerId && <p>Choose a customer to inspect recorded activity.</p>}
        {!!customerId &&
          (customer.isPending ? (
            <Loading label="Loading customer…" />
          ) : (
            customer.error && <ErrorMessage error={customer.error} />
          ))}
      </section>
      {customer.data && (
        <CustomerActivity
          key={customerId}
          customer={customer.data.data}
          analytics
        />
      )}
    </>
  );
}

export function Analytics({ service = false }: { service?: boolean }) {
  return (
    <>
      <h1 id="page-heading" tabIndex={-1}>
        Analytics
      </h1>
      <nav className="local-navigation" aria-label="Analytics views">
        <NavLink to="/app/analytics/activity">Activity</NavLink>
        <NavLink to="/app/analytics/service">Service</NavLink>
      </nav>
      {service ? <ServiceAnalytics /> : <ActivityAnalytics />}
    </>
  );
}
