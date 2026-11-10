import { ValidationSummary } from '../../components/FormSafety';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Link, useNavigate } from 'react-router-dom';
import { useSession } from './session';
import { api } from '../../api/client';
import type { Identity } from '../../api/client';
import { ErrorMessage } from '../../components/Feedback';

const schema = z.object({
  workspace_slug: z
    .string()
    .min(1, 'Enter the workspace address.')
    .max(80)
    .regex(
      /^[a-z0-9][a-z0-9-]*$/,
      'Use the workspace address supplied by your administrator.',
    ),
  email: z.email('Enter a valid email address.'),
  password: z.string().min(1, 'Enter your password.').max(128),
});
type Values = z.infer<typeof schema>;

export function SignIn({ portal = false }: { portal?: boolean }) {
  const navigate = useNavigate();
  const { setIdentity } = useSession();
  const [error, setError] = useState<Error | null>(null);
  const [show, setShow] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting, submitCount },
  } = useForm<Values>({
    shouldFocusError: false,
    resolver: zodResolver(schema),
  });
  return (
    <main className="auth-page">
      <Link to="/">Atlas CX</Link>
      <h1>{portal ? 'Customer portal sign-in' : 'Staff sign-in'}</h1>
      <p className="small-reading">
        Use the workspace address and account supplied by your administrator.
      </p>
      <form
        className="work-surface form-surface"
        onSubmit={handleSubmit(async (values) => {
          setError(null);
          try {
            const response = await api<Identity>('/auth/login', {
              method: 'POST',
              body: { ...values, audience: portal ? 'portal' : 'staff' },
            });
            setIdentity(response.data);
            navigate(portal ? '/portal' : '/app/customers');
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
        <label htmlFor="workspace_slug">Workspace address</label>
        <input
          id="workspace_slug"
          autoComplete="organization"
          {...register('workspace_slug')}
          aria-invalid={!!errors.workspace_slug}
          aria-describedby="workspace-error"
        />
        <p id="workspace-error" className="field-error">
          {errors.workspace_slug?.message}
        </p>
        <label htmlFor="email">Email</label>
        <input
          id="email"
          type="email"
          autoComplete="username"
          {...register('email')}
          aria-invalid={!!errors.email}
          aria-describedby="email-error"
        />
        <p id="email-error" className="field-error">
          {errors.email?.message}
        </p>
        <label htmlFor="password">Password</label>
        <input
          id="password"
          type={show ? 'text' : 'password'}
          autoComplete="current-password"
          {...register('password')}
          aria-invalid={!!errors.password}
          aria-describedby="password-error"
        />
        <p id="password-error" className="field-error">
          {errors.password?.message}
        </p>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={show}
            onChange={(event) => setShow(event.target.checked)}
          />
          Show password
        </label>
        <button className="button" disabled={isSubmitting}>
          {isSubmitting ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
      <Link to={portal ? '/sign-in' : '/portal/sign-in'}>
        {portal ? 'Staff sign-in' : 'Customer portal sign-in'}
      </Link>
    </main>
  );
}
