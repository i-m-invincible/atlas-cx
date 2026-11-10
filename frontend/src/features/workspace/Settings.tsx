import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api, apiPages } from '../../api/client';
import type { Member, Team, Workspace } from '../../api/client';
import { ErrorMessage, Loading } from '../../components/Feedback';
import { useSession } from '../identity/session';

export function Settings() {
  const { identity, refreshIdentity } = useSession();
  const client = useQueryClient();
  const [error, setError] = useState<Error | null>(null);
  const [notice, setNotice] = useState('');
  const [link, setLink] = useState('');
  const [pending, setPending] = useState(false);
  const workspace = useQuery({
    queryKey: [identity?.workspace_id, 'staff', 'workspace'],
    queryFn: ({ signal }) => api<Workspace>('/workspace', { signal }),
  });
  const members = useQuery({
    queryKey: [identity?.workspace_id, 'staff', 'settings-members'],
    queryFn: ({ signal }) => apiPages<Member>('/members', signal),
  });
  const teams = useQuery({
    queryKey: [identity?.workspace_id, 'staff', 'teams'],
    queryFn: ({ signal }) => apiPages<Team>('/teams', signal),
  });
  if (identity?.role !== 'admin')
    return <p>You don’t have permission to manage this workspace.</p>;
  if (workspace.isPending || members.isPending || teams.isPending)
    return <Loading label="Loading workspace settings…" />;
  if (workspace.error || members.error || teams.error)
    return (
      <ErrorMessage error={workspace.error ?? members.error ?? teams.error} />
    );
  async function run(action: () => Promise<unknown>, message: string) {
    setPending(true);
    setError(null);
    setNotice('');
    try {
      await action();
      await refreshIdentity();
      await client.invalidateQueries({
        queryKey: [identity?.workspace_id, 'staff'],
      });
      setNotice(message);
    } catch (failure) {
      setError(failure as Error);
    } finally {
      setPending(false);
    }
  }
  const row = workspace.data?.data;
  if (!row) return null;
  return (
    <>
      <h1 id="page-heading" tabIndex={-1}>
        Workspace settings
      </h1>
      <p className="small-reading">Changes apply only to {row.name}.</p>
      <nav className="local-navigation" aria-label="Settings sections">
        <Link to="/app/settings/case-configuration">Case configuration</Link>
        <Link to="/app/settings/event-tracking">Event tracking</Link>
      </nav>
      <p role="status">{notice}</p>
      <ErrorMessage error={error} />
      {link && (
        <div className="work-surface secret-surface">
          <h2>Setup link created</h2>
          <p>
            Share through a verified channel. This link expires in 24 hours.
          </p>
          <button
            className="button secondary"
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(link);
                setNotice('Copied.');
              } catch {
                setError(new Error('Clipboard unavailable'));
              }
            }}
          >
            Copy setup link
          </button>
          <button className="text-button" onClick={() => setLink('')}>
            Close setup link
          </button>
          <details>
            <summary>Reveal setup link</summary>
            <code className="secret-value">{link}</code>
          </details>
        </div>
      )}
      <section className="work-surface form-surface">
        <h2>Workspace</h2>
        <form
          className="compact-form"
          onSubmit={(event) => {
            event.preventDefault();
            const data = new FormData(event.currentTarget);
            void run(
              () =>
                api('/workspace', {
                  method: 'PATCH',
                  version: row.version,
                  body: {
                    name: data.get('name'),
                    timezone: data.get('timezone'),
                    feedback_manager_member_id: data.get('manager'),
                  },
                }),
              'Workspace updated.',
            );
          }}
        >
          <label htmlFor="workspace-name">Name</label>
          <input
            id="workspace-name"
            name="name"
            required
            maxLength={160}
            defaultValue={row.name}
          />
          <label htmlFor="workspace-timezone">Time zone</label>
          <input
            id="workspace-timezone"
            name="timezone"
            required
            defaultValue={row.timezone}
            aria-describedby="timezone-help"
          />
          <p id="timezone-help" className="small-reading">
            Use an IANA time zone, such as Asia/Kolkata. Stored timestamps
            remain in UTC.
          </p>
          <label htmlFor="feedback-manager">Fallback feedback manager</label>
          <select
            id="feedback-manager"
            name="manager"
            defaultValue={row.feedback_manager_member_id ?? ''}
          >
            {members.data?.data
              .filter(
                (member) =>
                  member.active && ['admin', 'manager'].includes(member.role),
              )
              .map((member) => (
                <option value={member.id} key={member.id}>
                  {member.display_name}
                </option>
              ))}
          </select>
          <button className="button" disabled={pending}>
            Save workspace
          </button>
        </form>
      </section>
      <section className="work-surface form-surface">
        <h2>Members</h2>
        <p className="small-reading">
          The last administrator must remain active. Changing access may require
          a replacement owner.
        </p>
        <form
          className="compact-form ruled-section"
          onSubmit={(event) => {
            event.preventDefault();
            const data = new FormData(event.currentTarget);
            setLink('');
            void run(async () => {
              const response = await api<{ member: Member; setup_url: string }>(
                '/members',
                {
                  method: 'POST',
                  body: {
                    email: data.get('email'),
                    display_name: data.get('display_name'),
                    role: data.get('role'),
                  },
                },
              );
              setLink(response.data.setup_url);
            }, 'Member setup link created. No email was sent.');
          }}
        >
          <h3>Add member</h3>
          <label htmlFor="member-name">Display name</label>
          <input
            id="member-name"
            name="display_name"
            required
            maxLength={120}
          />
          <label htmlFor="member-email">Email</label>
          <input
            id="member-email"
            name="email"
            type="email"
            required
            maxLength={254}
          />
          <label htmlFor="member-role">Role</label>
          <select id="member-role" name="role" defaultValue="agent">
            <option value="agent">Agent</option>
            <option value="viewer">Viewer</option>
            <option value="manager">Manager</option>
            <option value="admin">Administrator</option>
          </select>
          <button className="button secondary" disabled={pending}>
            Create member setup link
          </button>
        </form>
        {members.data?.data.map((member) => (
          <form
            className="compact-form ruled-section"
            key={`${member.id}-${member.version}`}
            onSubmit={(event) => {
              event.preventDefault();
              const data = new FormData(event.currentTarget);
              void run(
                () =>
                  api(`/members/${member.id}`, {
                    method: 'PATCH',
                    version: member.version,
                    body: {
                      role: data.get('role'),
                      active: data.has('active'),
                      replacement_member_id: data.get('replacement') || null,
                    },
                  }),
                'Member access updated.',
              );
            }}
          >
            <h3>{member.display_name}</h3>
            <p>
              {member.email} ·{' '}
              {member.active ? 'Active' : 'Inactive or pending setup'}
            </p>
            <label htmlFor={`role-${member.id}`}>
              Role for {member.display_name}
            </label>
            <select
              id={`role-${member.id}`}
              name="role"
              defaultValue={member.role}
            >
              <option value="agent">Agent</option>
              <option value="viewer">Viewer</option>
              <option value="manager">Manager</option>
              <option value="admin">Administrator</option>
            </select>
            <label className="checkbox-label">
              <input
                type="checkbox"
                name="active"
                defaultChecked={member.active}
              />
              Active access for {member.display_name}
            </label>
            <label htmlFor={`replacement-${member.id}`}>
              Replacement owner · When required
            </label>
            <select id={`replacement-${member.id}`} name="replacement">
              <option value="">Choose if needed</option>
              {members.data?.data
                .filter(
                  (other) =>
                    other.active &&
                    other.role !== 'viewer' &&
                    other.id !== member.id,
                )
                .map((other) => (
                  <option key={other.id} value={other.id}>
                    {other.display_name}
                  </option>
                ))}
            </select>
            <div className="form-actions">
              <button className="button secondary" disabled={pending}>
                Save access for {member.display_name}
              </button>
              {!member.active && (
                <button
                  className="text-button"
                  type="button"
                  disabled={pending}
                  onClick={() => {
                    setLink('');
                    void run(async () => {
                      const response = await api<{
                        member: Member;
                        setup_url: string;
                      }>('/members', {
                        method: 'POST',
                        version: member.version,
                        body: {
                          email: member.email,
                          display_name: member.display_name,
                          role: member.role,
                        },
                      });
                      setLink(response.data.setup_url);
                    }, 'New setup link created. Earlier unused links are invalid.');
                  }}
                >
                  Create new setup link
                </button>
              )}
            </div>
          </form>
        ))}
      </section>
      <section className="work-surface form-surface">
        <h2>Teams</h2>
        <p className="small-reading">
          Teams organize routing. They do not make workspace records private.
        </p>
        {[undefined, ...(teams.data?.data ?? [])].map((team) => (
          <form
            key={team ? `${team.id}-${team.version}` : 'new'}
            className="compact-form ruled-section"
            onSubmit={(event) => {
              event.preventDefault();
              const data = new FormData(event.currentTarget);
              void run(
                () =>
                  api(team ? `/teams/${team.id}` : '/teams', {
                    method: team ? 'PATCH' : 'POST',
                    version: team?.version,
                    body: {
                      name: data.get('name'),
                      member_ids: data.getAll('member_ids'),
                      ...(team ? { archived: data.has('archived') } : {}),
                    },
                  }),
                team ? 'Team updated.' : 'Team created.',
              );
            }}
          >
            <h3>{team?.name ?? 'Create team'}</h3>
            <label htmlFor={`team-${team?.id ?? 'new'}`}>Team name</label>
            <input
              id={`team-${team?.id ?? 'new'}`}
              name="name"
              required
              maxLength={120}
              defaultValue={team?.name ?? ''}
            />
            <fieldset>
              <legend>Team members</legend>
              {members.data?.data
                .filter((member) => member.active)
                .map((member) => (
                  <label className="checkbox-label" key={member.id}>
                    <input
                      type="checkbox"
                      name="member_ids"
                      value={member.id}
                      defaultChecked={team?.member_ids.includes(member.id)}
                    />
                    {member.display_name}
                  </label>
                ))}
            </fieldset>
            {team && (
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  name="archived"
                  defaultChecked={!!team.archived_at}
                />
                Archived team
              </label>
            )}
            <button className="button secondary" disabled={pending}>
              {team ? 'Save team' : 'Create team'}
            </button>
          </form>
        ))}
      </section>
    </>
  );
}
