import { UnsavedChanges, ValidationSummary } from '../../components/FormSafety';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../../api/client';
import type { Contact } from '../../api/client';
import { ErrorMessage, Loading } from '../../components/Feedback';
import { useSession } from '../identity/session';

const schema = z.object({
  name: z.string().trim().min(1, 'Enter the contact name.').max(120),
  email: z.email('Enter a valid email address.').max(254),
  phone: z.string().max(32),
});
type Values = z.infer<typeof schema>;

export function ContactForm() {
  const { id, contactId } = useParams();
  const { identity } = useSession();
  const query = useQuery({
    queryKey: [identity?.workspace_id, 'staff', 'contact', contactId],
    queryFn: ({ signal }) => api<Contact>(`/contacts/${contactId}`, { signal }),
    enabled: !!contactId,
  });
  if (contactId && query.isPending) return <Loading label="Loading contact…" />;
  if (query.error) return <ErrorMessage error={query.error} />;
  if (!identity?.permissions.includes('customers:write'))
    return <p>You don’t have permission to edit contacts.</p>;
  if (!id || (query.data && query.data.data.customer_id !== id))
    return <p>This contact isn’t available.</p>;
  return (
    <ContactEditor
      key={contactId ?? 'new'}
      customerId={id}
      contact={query.data?.data}
    />
  );
}

function ContactEditor({
  customerId,
  contact,
}: {
  customerId: string;
  contact?: Contact;
}) {
  const { identity } = useSession();
  const navigate = useNavigate();
  const client = useQueryClient();
  const [error, setError] = useState<Error | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting, isDirty, submitCount },
  } = useForm<Values>({
    shouldFocusError: false,
    resolver: zodResolver(schema),
    defaultValues: {
      name: contact?.name ?? '',
      email: contact?.email ?? '',
      phone: contact?.phone ?? '',
    },
  });
  const back = `/app/customers/${customerId}`;
  return (
    <>
      <UnsavedChanges dirty={isDirty && !isSubmitting} />
      <Link to={back}>Back to customer</Link>
      <h1 id="page-heading" tabIndex={-1}>
        {contact ? 'Edit contact' : 'Add contact'}
      </h1>
      <form
        className="work-surface form-surface"
        onSubmit={handleSubmit(async (values) => {
          setError(null);
          try {
            await api<Contact>(
              contact ? `/contacts/${contact.id}` : '/contacts',
              {
                method: contact ? 'PATCH' : 'POST',
                version: contact?.version,
                body: {
                  ...values,
                  phone: values.phone || null,
                  ...(!contact ? { customer_id: customerId } : {}),
                },
              },
            );
            await client.invalidateQueries({
              queryKey: [
                identity?.workspace_id,
                'staff',
                'contacts',
                customerId,
              ],
            });
            navigate(back, {
              state: {
                notice: contact ? 'Contact updated.' : 'Contact added.',
              },
            });
          } catch (failure) {
            setError(failure as Error);
          }
        })}
        noValidate
      >
        <ErrorMessage error={error} />
        <ValidationSummary
          submitCount={submitCount}
          messages={Object.entries(errors).map(([field, value]) => ({
            field,
            message: value.message ?? 'Check this field.',
          }))}
        />
        <label htmlFor="name">Contact name</label>
        <input
          id="name"
          {...register('name')}
          aria-invalid={!!errors.name}
          aria-describedby="name-error"
        />
        <p id="name-error" className="field-error">
          {errors.name?.message}
        </p>
        <label htmlFor="email">Email</label>
        <input
          id="email"
          type="email"
          {...register('email')}
          aria-invalid={!!errors.email}
          aria-describedby="email-error"
        />
        <p id="email-error" className="field-error">
          {errors.email?.message}
        </p>
        <p className="small-reading">
          Adding a contact does not grant portal access. After portal access is
          provisioned, this email cannot change here.
        </p>
        <label htmlFor="phone">Phone · Optional</label>
        <input
          id="phone"
          type="tel"
          {...register('phone')}
          aria-invalid={!!errors.phone}
          aria-describedby="phone-error"
        />
        <p id="phone-error" className="field-error">
          {errors.phone?.message}
        </p>
        <div className="form-actions">
          <button
            className="button"
            disabled={isSubmitting || !!contact?.archived_at}
          >
            {isSubmitting
              ? 'Saving…'
              : contact
                ? 'Save contact'
                : 'Add contact'}
          </button>
          <Link to={back}>Cancel</Link>
        </div>
      </form>
    </>
  );
}
