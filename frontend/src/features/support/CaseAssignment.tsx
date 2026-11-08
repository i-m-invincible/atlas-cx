import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useForm, useWatch } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { api, apiPages } from '../../api/client';
import type { Member, Team } from '../../api/client';
import { ErrorMessage, Loading } from '../../components/Feedback';
import { UnsavedChanges, ValidationSummary } from '../../components/FormSafety';
import { useSession } from '../identity/session';
import { ConflictReview } from './components';
import type { CaseConfig, CaseDetail } from './data';
import { useHeadingFocus } from './data';

const schema = z.object({
  category_key: z.string().min(1),
  priority: z.enum(['urgent', 'high', 'normal', 'low']),
  team_id: z.string(),
  assignee_member_id: z.string(),
});
type Values = z.infer<typeof schema>;

export function CaseAssignment() {
  const { id } = useParams();
  const { identity } = useSession();
  const query = useQuery({
    queryKey: [identity?.workspace_id, 'staff', 'case', id],
    queryFn: ({ signal }) => api<CaseDetail>(`/cases/${id}`, { signal }),
  });
  if (query.isPending) return <Loading label="Loading case details..." />;
  if (query.error) return <ErrorMessage error={query.error} />;
  if (!identity?.permissions.includes('cases:write'))
    return <p>You don’t have permission to edit this case.</p>;
  if (query.data.data.state === 'closed')
    return <p>This case is closed. Its details cannot be changed.</p>;
  return <AssignmentEditor key={id} row={query.data.data} />;
}

function AssignmentEditor({ row }: { row: CaseDetail }) {
  useHeadingFocus('page-heading', true);
  const { identity } = useSession();
  const client = useQueryClient();
  const navigate = useNavigate();
  const [error, setError] = useState<Error | null>(null);
  const [version, setVersion] = useState(row.version);
  const members = useQuery({
    queryKey: [identity?.workspace_id, 'staff', 'assignment-members'],
    queryFn: ({ signal }) => apiPages<Member>('/members?active=true', signal),
  });
  const teams = useQuery({
    queryKey: [identity?.workspace_id, 'staff', 'teams'],
    queryFn: ({ signal }) => apiPages<Team>('/teams', signal),
  });
  const config = useQuery({
    queryKey: [
      identity?.workspace_id,
      'staff',
      'case-config',
      row.config_version_id,
    ],
    queryFn: ({ signal }) =>
      api<CaseConfig>(`/case-configs/${row.config_version_id}`, { signal }),
  });
  const {
    register,
    handleSubmit,
    control,
    formState: { errors, isDirty, isSubmitting, submitCount },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    shouldFocusError: false,
    defaultValues: {
      category_key: row.category_key,
      priority: row.priority,
      team_id: row.team?.id ?? '',
      assignee_member_id: row.assignee?.id ?? '',
    },
  });
  const teamId = useWatch({ control, name: 'team_id' });
  const team = teams.data?.data.find((item) => item.id === teamId);
  const eligible =
    members.data?.data.filter(
      (item) =>
        item.role !== 'viewer' &&
        (!teamId || team?.member_ids.includes(item.id)),
    ) ?? [];
  const failed = members.error ?? teams.error ?? config.error;
  const loading = members.isPending || teams.isPending || config.isPending;
  return (
    <>
      <UnsavedChanges dirty={isDirty && !isSubmitting} />
      <Link to={`/app/support/cases/${row.id}`}>Back to case</Link>
      <h1 id="page-heading" tabIndex={-1}>
        Edit case details
      </h1>
      <p>{row.subject}</p>
      <form
        className="work-surface form-surface"
        noValidate
        onSubmit={handleSubmit(async (values) => {
          setError(null);
          try {
            const response = await api<CaseDetail>(`/cases/${row.id}`, {
              method: 'PATCH',
              version,
              body: {
                ...values,
                team_id: values.team_id || null,
                assignee_member_id: values.assignee_member_id || null,
              },
            });
            client.setQueryData(
              [identity?.workspace_id, 'staff', 'case', row.id],
              response,
            );
            await client.invalidateQueries({
              queryKey: [identity?.workspace_id, 'staff', 'cases'],
            });
            navigate(`/app/support/cases/${row.id}`, {
              state: { notice: 'Case details updated.' },
            });
          } catch (cause) {
            setError(cause as Error);
          }
        })}
      >
        <ErrorMessage error={error ?? failed} />
        <ConflictReview<CaseDetail>
          error={error}
          path={`/cases/${row.id}`}
          accept={(latest) => {
            setVersion(latest.data.version);
            setError(null);
            client.setQueryData(
              [identity?.workspace_id, 'staff', 'case', row.id],
              latest,
            );
          }}
        />
        <ValidationSummary
          submitCount={submitCount}
          messages={Object.entries(errors).map(([field, value]) => ({
            field,
            message: value.message ?? 'Review this field.',
          }))}
        />
        {loading && <Loading label="Loading assignment options..." />}
        <label htmlFor="category_key">Category</label>
        <select id="category_key" {...register('category_key')}>
          {config.data?.data.definition.categories.map((item) => (
            <option key={item.key} value={item.key}>
              {item.label}
            </option>
          ))}
        </select>
        <label htmlFor="team_id">Team · Optional</label>
        <select id="team_id" {...register('team_id')}>
          <option value="">No team</option>
          {teams.data?.data
            .filter((item) => !item.archived_at || item.id === row.team?.id)
            .map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
                {item.archived_at ? ' · Archived' : ''}
              </option>
            ))}
        </select>
        <label htmlFor="assignee_member_id">Assignee</label>
        <select id="assignee_member_id" {...register('assignee_member_id')}>
          <option value="">
            Unassigned
            {row.state !== 'new' ? ' · Only permitted for new cases' : ''}
          </option>
          {eligible.map((item) => (
            <option key={item.id} value={item.id}>
              {item.display_name}
            </option>
          ))}
        </select>
        <p className="small-reading">
          The assignee must be active and belong to the selected team.
          Assignment sets responsibility; staff still share workspace-wide
          visibility.
        </p>
        <label htmlFor="priority">Priority</label>
        <select id="priority" {...register('priority')}>
          {['urgent', 'high', 'normal', 'low'].map((value) => (
            <option key={value}>{value}</option>
          ))}
        </select>
        <p className="small-reading">
          Priority changes the order of work. The original target stays the
          same.
        </p>
        <button
          className="button"
          disabled={isSubmitting || loading || !!failed}
        >
          {isSubmitting ? 'Saving...' : 'Save case details'}
        </button>
      </form>
    </>
  );
}
