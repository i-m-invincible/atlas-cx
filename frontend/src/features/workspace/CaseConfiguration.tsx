import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { api, apiPages } from '../../api/client';
import type { Team, Workspace } from '../../api/client';
import type { components } from '../../api/schema';
import { ErrorMessage, Loading } from '../../components/Feedback';
import { UnsavedChanges } from '../../components/FormSafety';
import { useSession } from '../identity/session';
import { ConflictReview, CustomFields } from '../support/components';
import { useHeadingFocus, useReplayKeys } from '../support/data';
import type { CaseConfig } from '../support/data';

type Definition = CaseConfig['definition'];
type Field = components['schemas']['FieldDefinition'];
type Preset = components['schemas']['CasePreset'];
const base = '/app/settings/case-configuration';
const priorities = ['urgent', 'high', 'normal', 'low'] as const;
const states = [
  'new',
  'open',
  'pending_customer',
  'resolved',
  'closed',
] as const;
const fieldTypes = [
  'string',
  'integer',
  'decimal',
  'boolean',
  'date',
  'single_select',
] as const;

export function CaseConfiguration() {
  const { identity } = useSession();
  return identity?.role === 'admin' ? (
    <ConfigurationPage />
  ) : (
    <p>You don’t have permission to manage case configuration.</p>
  );
}

function ConfigurationPage() {
  const { id } = useParams();
  const { identity } = useSession();
  const scope = [identity?.workspace_id, 'staff'];
  const workspace = useQuery({
    queryKey: [...scope, 'workspace'],
    queryFn: ({ signal }) => api<Workspace>('/workspace', { signal }),
  });
  const active = workspace.data?.data.active_case_config_id;
  const index = useQuery({
    queryKey: [...scope, 'case-configs'],
    queryFn: ({ signal }) => apiPages<CaseConfig>('/case-configs', signal),
    enabled: !id,
  });
  const detailId = id === 'new' ? active : id;
  const detail = useQuery({
    queryKey: [...scope, 'case-config', detailId],
    queryFn: ({ signal }) =>
      api<CaseConfig>('/case-configs/' + detailId, { signal }),
    enabled: !!detailId,
  });
  const teams = useQuery({
    queryKey: [...scope, 'teams'],
    queryFn: ({ signal }) => apiPages<Team>('/teams', signal),
    enabled: !!id,
  });
  const presets = useQuery({
    queryKey: [...scope, 'case-presets'],
    queryFn: ({ signal }) => api<Preset[]>('/case-presets', { signal }),
    enabled: id === 'new',
  });
  const loading =
    workspace.isPending ||
    (!id && index.isPending) ||
    (!!detailId && detail.isPending) ||
    (!!id && teams.isPending) ||
    (id === 'new' && presets.isPending);
  useHeadingFocus('page-heading', !loading);
  const error =
    workspace.error ??
    index.error ??
    detail.error ??
    teams.error ??
    presets.error;
  return (
    <>
      <Link to={id ? base : '/app/settings/workspace'}>
        {id ? 'Back to case configuration' : 'Back to settings'}
      </Link>
      <h1 id="page-heading" tabIndex={-1}>
        Case configuration
      </h1>
      <div className="configuration-layout">
        <nav aria-label="Settings sections" className="settings-sections">
          <Link to="/app/settings/workspace">Workspace settings</Link>
          <Link to={base} aria-current="page">
            Case configuration
          </Link>
        </nav>
        <div className="configuration-content">
          {loading ? (
            <Loading label="Loading case configuration…" />
          ) : error ? (
            <ErrorMessage error={error} />
          ) : !id ? (
            <section className="work-surface m3-surface">
              <h2>Configuration versions</h2>
              <Link className="button" to={base + '/new'}>
                Start a draft
              </Link>
              <ul className="message-list">
                {index.data?.data.map((row) => (
                  <li key={row.id}>
                    <Link to={base + '/' + row.id}>Version {row.number}</Link>
                    <p>
                      {row.id === active
                        ? 'Current published version'
                        : row.status === 'draft'
                          ? 'Draft'
                          : 'Published'}
                    </p>
                  </li>
                ))}
              </ul>
            </section>
          ) : detail.data ? (
            <ConfigurationEditor
              key={id}
              source={detail.data.data}
              newDraft={id === 'new'}
              teams={teams.data?.data.filter((team) => !team.archived_at) ?? []}
              presets={presets.data?.data ?? []}
            />
          ) : (
            <p>Initialize this workspace before creating a draft.</p>
          )}
        </div>
      </div>
    </>
  );
}

function ConfigurationEditor({
  source,
  newDraft,
  teams,
  presets,
}: {
  source: CaseConfig;
  newDraft: boolean;
  teams: Team[];
  presets: Preset[];
}) {
  const { identity } = useSession();
  const client = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const keys = useReplayKeys();
  const [saved, setSaved] = useState(newDraft ? null : source);
  const [definition, setDefinition] = useState(source.definition);
  const [presetKey, setPresetKey] = useState('');
  const [review, setReview] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [notice, setNotice] = useState(
    (location.state as { notice?: string } | null)?.notice ?? '',
  );
  const dirty =
    JSON.stringify(definition) !==
    JSON.stringify(saved?.definition ?? source.definition);
  const published = saved?.status === 'published';

  async function run(publishing: boolean) {
    setPending(true);
    setError(null);
    setNotice('');
    const path = saved
      ? '/case-configs/' + saved.id + (publishing ? '/publish' : '')
      : '/case-configs';
    try {
      const response = await api<CaseConfig>(path, {
        method: !saved || publishing ? 'POST' : 'PATCH',
        version: saved?.version,
        body: publishing
          ? undefined
          : {
              ...definition,
              fields: (definition.fields ?? []).map((field) => ({
                ...field,
                allowed_values:
                  field.allowed_values
                    ?.map((option) => option.trim())
                    .filter(Boolean) ?? [],
              })),
            },
        idempotencyKey: publishing ? keys.keyFor(path, null) : undefined,
      });
      const { data } = response;
      client.setQueryData(
        [identity?.workspace_id, 'staff', 'case-config', data.id],
        response,
      );
      if (!saved) {
        navigate(base + '/' + data.id, {
          replace: true,
          state: { notice: 'Draft saved.' },
        });
      }
      setSaved(data);
      setDefinition(data.definition);
      setReview(false);
      keys.completed(path, null);
      await client.invalidateQueries({
        queryKey: [identity?.workspace_id, 'staff', 'case-configs'],
      });
      if (publishing) {
        await client.invalidateQueries({
          queryKey: [identity?.workspace_id, 'staff', 'workspace'],
        });
      }
      setNotice(
        publishing ? 'Configuration published for new cases.' : 'Draft saved.',
      );
    } catch (failure) {
      setError(failure as Error);
    } finally {
      setPending(false);
    }
  }
  const editCategory = (
    index: number,
    value: Definition['categories'][number],
  ) =>
    setDefinition({
      ...definition,
      categories: definition.categories.map((item, at) =>
        at === index ? value : item,
      ),
    });
  const editField = (index: number, value: Field) =>
    setDefinition({
      ...definition,
      fields: definition.fields?.map((item, at) =>
        at === index ? value : item,
      ),
    });
  return (
    <section className="work-surface m3-surface">
      <UnsavedChanges dirty={!published && dirty && !pending} />
      <h2>
        {saved ? 'Version ' + saved.number + ' · ' + saved.status : 'New draft'}
      </h2>
      {dirty && <p>Unsaved changes</p>}
      {published && (
        <p>Published versions are read-only. Start a draft to make changes.</p>
      )}
      <ErrorMessage error={error} />
      {saved && (
        <ConflictReview<CaseConfig>
          record="configuration"
          error={error}
          path={'/case-configs/' + saved.id}
          accept={(latest) => {
            setSaved(latest.data);
            setError(null);
          }}
        />
      )}
      <p role="status">{notice}</p>
      <form
        className="compact-form"
        onSubmit={(event) => {
          event.preventDefault();
          void run(false);
        }}
      >
        <fieldset disabled={published || pending} className="m3-fields">
          {presets.length > 0 && !saved && (
            <>
              <label htmlFor="case-preset">Starter preset</label>
              <select
                id="case-preset"
                value={presetKey}
                onChange={(event) => setPresetKey(event.target.value)}
              >
                <option value="">Current workspace configuration</option>
                {presets.map((preset) => (
                  <option key={preset.key} value={preset.key}>
                    {preset.label}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="button secondary"
                onClick={() => {
                  setDefinition(
                    presets.find((item) => item.key === presetKey)
                      ?.definition ?? source.definition,
                  );
                  setReview(false);
                }}
              >
                Copy preset into draft
              </button>
            </>
          )}
          <h3>Categories and routing</h3>
          {definition.categories.map((category, index) => (
            <fieldset className="m3-fields ruled-section" key={index}>
              <legend>Category {index + 1}</legend>
              <label htmlFor={'category-key-' + index}>Category key</label>
              <input
                id={'category-key-' + index}
                required
                pattern="[a-z0-9_]{1,50}"
                value={category.key}
                onChange={(event) =>
                  editCategory(index, { ...category, key: event.target.value })
                }
              />
              <label htmlFor={'category-label-' + index}>Category label</label>
              <input
                id={'category-label-' + index}
                required
                maxLength={120}
                value={category.label}
                onChange={(event) =>
                  editCategory(index, {
                    ...category,
                    label: event.target.value,
                  })
                }
              />
              <label htmlFor={'routing-' + index}>Default routing team</label>
              <select
                id={'routing-' + index}
                value={category.default_team_id ?? ''}
                onChange={(event) =>
                  editCategory(index, {
                    ...category,
                    default_team_id: event.target.value || null,
                  })
                }
              >
                <option value="">Unrouted</option>
                {teams.map((team) => (
                  <option key={team.id} value={team.id}>
                    {team.name}
                  </option>
                ))}
                {category.default_team_id &&
                  !teams.some(
                    (team) => team.id === category.default_team_id,
                  ) && (
                    <option value={category.default_team_id}>
                      Unavailable team
                    </option>
                  )}
              </select>
              <button
                type="button"
                className="text-button"
                disabled={definition.categories.length === 1}
                onClick={() =>
                  setDefinition({
                    ...definition,
                    categories: definition.categories.filter(
                      (_, at) => at !== index,
                    ),
                  })
                }
              >
                Remove category {index + 1}
              </button>
            </fieldset>
          ))}
          <button
            type="button"
            className="button secondary"
            disabled={definition.categories.length >= 50}
            onClick={() =>
              setDefinition({
                ...definition,
                categories: [...definition.categories, { key: '', label: '' }],
              })
            }
          >
            Add category
          </button>
          <h3>State labels</h3>
          {states.map((state) => (
            <div key={state}>
              <label htmlFor={'label-' + state}>
                {state.replaceAll('_', ' ')}
              </label>
              <input
                id={'label-' + state}
                required
                maxLength={120}
                value={definition.state_labels[state] ?? ''}
                onChange={(event) =>
                  setDefinition({
                    ...definition,
                    state_labels: {
                      ...definition.state_labels,
                      [state]: event.target.value,
                    },
                  })
                }
              />
            </div>
          ))}
          <h3>Priority targets in elapsed minutes</h3>
          {priorities.map((priority) => (
            <fieldset className="m3-fields ruled-section" key={priority}>
              <legend>{priority}</legend>
              {(['response_minutes', 'resolution_minutes'] as const).map(
                (key) => (
                  <div key={key}>
                    <label htmlFor={priority + key}>
                      {key === 'response_minutes'
                        ? 'First response'
                        : 'Resolution'}
                    </label>
                    <input
                      id={priority + key}
                      type="number"
                      required
                      min={1}
                      max={35791394}
                      step={1}
                      value={definition.priorities[priority]?.[key] || ''}
                      onChange={(event) => {
                        const current = definition.priorities[priority];
                        if (current)
                          setDefinition({
                            ...definition,
                            priorities: {
                              ...definition.priorities,
                              [priority]: {
                                ...current,
                                [key]: Number(event.target.value),
                              },
                            },
                          });
                      }}
                    />
                  </div>
                ),
              )}
            </fieldset>
          ))}
          <h3>Custom fields</h3>
          {(definition.fields ?? []).map((field, index) => (
            <FieldEditor
              key={index}
              index={index}
              field={field}
              onChange={(value) => editField(index, value)}
              remove={() =>
                setDefinition({
                  ...definition,
                  fields: definition.fields?.filter((_, at) => at !== index),
                })
              }
            />
          ))}
          <button
            type="button"
            className="button secondary"
            disabled={(definition.fields?.length ?? 0) >= 20}
            onClick={() =>
              setDefinition({
                ...definition,
                fields: [
                  ...(definition.fields ?? []),
                  {
                    key: '',
                    label: '',
                    type: 'string',
                    required_on_create: false,
                    required_on_resolve: false,
                    portal_visible: false,
                    portal_editable_on_create: false,
                  },
                ],
              })
            }
          >
            Add custom field
          </button>
        </fieldset>
        {!published && (
          <button className="button" disabled={pending || (!!saved && !dirty)}>
            Save draft
          </button>
        )}
      </form>
      {saved?.status === 'draft' && (
        <section className="ruled-section">
          <button
            className="button secondary"
            disabled={dirty || pending}
            onClick={() => setReview(!review)}
          >
            Review and publish
          </button>
          {review && (
            <div className="m3-fields">
              <h3>Portal request preview</h3>
              <p>
                New cases use this version. Existing cases keep their current
                configuration.
              </p>
              <fieldset disabled className="m3-fields">
                <legend>New request fields</legend>
                <label htmlFor="preview-category">Category</label>
                <select id="preview-category">
                  {definition.categories.map((item) => (
                    <option key={item.key}>{item.label}</option>
                  ))}
                </select>
                <CustomFields
                  fields={(definition.fields ?? [])
                    .filter(
                      (field) =>
                        field.portal_visible && field.portal_editable_on_create,
                    )
                    .map((field) => ({
                      key: field.key,
                      label: field.label,
                      type: field.type,
                      required_on_create: field.required_on_create ?? false,
                      portal_editable_on_create: true,
                      allowed_values: field.allowed_values ?? [],
                      minimum: field.minimum ?? null,
                      maximum: field.maximum ?? null,
                    }))}
                />
              </fieldset>
              <button
                className="button"
                disabled={dirty || pending}
                onClick={() => void run(true)}
              >
                {pending
                  ? 'Publishing configuration…'
                  : 'Publish configuration'}
              </button>
            </div>
          )}
        </section>
      )}
    </section>
  );
}

function FieldEditor({
  field,
  index,
  onChange,
  remove,
}: {
  field: Field;
  index: number;
  onChange: (value: Field) => void;
  remove: () => void;
}) {
  const prefix = 'config-field-' + index + '-';
  const numeric = field.type === 'integer' || field.type === 'decimal';
  const defaultText = field.default == null ? '' : String(field.default);
  return (
    <fieldset className="m3-fields ruled-section">
      <legend>Custom field {index + 1}</legend>
      <label htmlFor={prefix + 'key'}>Field key</label>
      <input
        id={prefix + 'key'}
        required
        pattern="[a-z0-9_]{1,50}"
        value={field.key}
        onChange={(event) => onChange({ ...field, key: event.target.value })}
      />
      <label htmlFor={prefix + 'label'}>Field label</label>
      <input
        id={prefix + 'label'}
        required
        maxLength={120}
        value={field.label}
        onChange={(event) => onChange({ ...field, label: event.target.value })}
      />
      <label htmlFor={prefix + 'type'}>Field type</label>
      <select
        id={prefix + 'type'}
        value={field.type}
        onChange={(event) =>
          onChange({
            ...field,
            type: event.target.value as Field['type'],
            minimum: null,
            maximum: null,
            allowed_values: [],
            default: null,
          })
        }
      >
        {fieldTypes.map((type) => (
          <option key={type} value={type}>
            {type.replaceAll('_', ' ')}
          </option>
        ))}
      </select>
      {field.type === 'single_select' && (
        <>
          <label htmlFor={prefix + 'options'}>Options, one per line</label>
          <textarea
            id={prefix + 'options'}
            value={field.allowed_values?.join('\n') ?? ''}
            onChange={(event) =>
              onChange({
                ...field,
                allowed_values: event.target.value.split('\n'),
              })
            }
          />
        </>
      )}
      {numeric &&
        (['minimum', 'maximum'] as const).map((bound) => (
          <div key={bound}>
            <label htmlFor={prefix + bound}>
              {bound === 'minimum' ? 'Minimum' : 'Maximum'} · Optional
            </label>
            <input
              id={prefix + bound}
              type="number"
              step={field.type === 'integer' ? 1 : 'any'}
              value={field[bound] ?? ''}
              onChange={(event) =>
                onChange({
                  ...field,
                  [bound]:
                    event.target.value === ''
                      ? null
                      : Number(event.target.value),
                })
              }
            />
          </div>
        ))}
      <label htmlFor={prefix + 'default'}>Default value · Optional</label>
      {field.type === 'boolean' || field.type === 'single_select' ? (
        <select
          id={prefix + 'default'}
          value={defaultText}
          onChange={(event) =>
            onChange({
              ...field,
              default:
                event.target.value === ''
                  ? null
                  : field.type === 'boolean'
                    ? event.target.value === 'true'
                    : event.target.value,
            })
          }
        >
          <option value="">No default</option>
          {(field.type === 'boolean'
            ? ['true', 'false']
            : (field.allowed_values ?? [])
          )
            .filter(Boolean)
            .map((option, at) => (
              <option key={at} value={option}>
                {option}
              </option>
            ))}
        </select>
      ) : (
        <input
          id={prefix + 'default'}
          type={numeric ? 'number' : field.type === 'date' ? 'date' : 'text'}
          step={field.type === 'integer' ? 1 : 'any'}
          maxLength={4000}
          value={defaultText}
          onChange={(event) =>
            onChange({
              ...field,
              default:
                event.target.value === ''
                  ? null
                  : numeric
                    ? Number(event.target.value)
                    : event.target.value,
            })
          }
        />
      )}
      {(
        [
          ['required_on_create', 'Required on creation'],
          ['required_on_resolve', 'Required to resolve'],
          ['portal_visible', 'Visible in the portal'],
          ['portal_editable_on_create', 'Customer can enter on creation'],
        ] as const
      ).map(([key, label]) => (
        <label className="checkbox-label" key={key}>
          <input
            type="checkbox"
            checked={field[key] ?? false}
            onChange={(event) =>
              onChange({ ...field, [key]: event.target.checked })
            }
          />
          {label}
        </label>
      ))}
      <button type="button" className="text-button" onClick={remove}>
        Remove custom field {index + 1}
      </button>
    </fieldset>
  );
}
