import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useStore } from '../store';
import TimetablePoster from '../components/TimetablePoster';
import PosterFrame from '../components/PosterFrame';
import { aspects } from '../themes/designs';
import type { Instance, Offering, RoomType, Solution, ViewKind } from '../types';
import {
  checkSchedule,
  clearSchedule,
  createTimetable,
  deleteTimetable,
  describeViolations,
  duplicateTimetable,
  getTimetable,
  listTimetables,
  newId,
  publishSaved,
  saveSchedule,
  updateTimetable,
  type SavedSchedule,
  type ScheduleCheck,
  type Template,
  type TimetableDetail,
  type TimetableSummary,
} from '../timetables';

const ALL_DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const TEMPLATES: { id: Template; label: string }[] = [
  { id: 'blank', label: 'Blank (fill in your own data)' },
  { id: 'demo', label: 'Demo department' },
  { id: 'small', label: 'Small synthetic (40 classes)' },
  { id: 'medium', label: 'Medium synthetic (150 classes)' },
  { id: 'large', label: 'Large synthetic (400 classes)' },
  { id: 'published', label: 'Copy of the published timetable' },
  { id: 'import', label: 'Import a JSON file' },
];
const STATUS: Record<TimetableSummary['schedule'], { text: string; cls: string }> = {
  none: { text: 'No schedule yet', cls: '' },
  ok: { text: '✓ Schedule ready', cls: 'sage' },
  'needs attention': { text: 'Schedule needs attention', cls: 'accent' },
};
// Validation-study budgets by size (as on the Overview), used when optimising a saved timetable.
const sizeDefaults = (events: number) => (events <= 250 ? { budget: 360, searchSeconds: 6 } : { budget: 240, searchSeconds: 16 });

const hourLabels = (n: number, first: number) =>
  Array.from({ length: n }, (_, i) => {
    const h = (x: number) => `${((x - 1) % 12) + 1}:00`;
    return `${h(first + i)} - ${h(first + i + 1)}`;
  });

/** Admin page: create, edit, duplicate and delete timetables, optimise them, edit schedules by hand, publish. */
export default function Timetables() {
  const [params, setParams] = useSearchParams();
  const openId = params.get('id') ? Number(params.get('id')) : null;
  const [rows, setRows] = useState<TimetableSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(() => {
    listTimetables()
      .then(setRows)
      .catch((e: Error) => setError(e.message));
  }, []);
  useEffect(load, [load]);

  const open = (id: number | null, tab?: string) => {
    const next = new URLSearchParams();
    if (id != null) next.set('id', String(id));
    if (tab) next.set('tab', tab);
    setParams(next);
    setMsg(null);
    setError(null);
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Timetables</h1>
          <p>
            Create timetables for any department, edit their classes, teachers, rooms and courses, let the optimiser build the schedule, adjust it by
            hand (every change is checked against all hard constraints), and publish it. The Demo department is only a starting template.
          </p>
        </div>
      </div>
      {error && (
        <div className="error-box" style={{ marginBottom: 14 }}>
          {error}
        </div>
      )}
      {msg && (
        <div className="card" style={{ marginBottom: 14, background: 'var(--sage-soft)' }}>
          {msg}
        </div>
      )}
      {openId == null ? (
        <TimetableList
          rows={rows}
          onOpen={(id) => open(id)}
          onChanged={(m) => {
            setMsg(m);
            load();
          }}
          onError={setError}
        />
      ) : (
        <Editor
          key={openId}
          id={openId}
          tab={params.get('tab') ?? 'data'}
          onTab={(t) => open(openId, t)}
          onBack={() => {
            open(null);
            load();
          }}
          onMsg={setMsg}
          onError={setError}
        />
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// list + create
// ---------------------------------------------------------------------------
function TimetableList({
  rows,
  onOpen,
  onChanged,
  onError,
}: {
  rows: TimetableSummary[] | null;
  onOpen: (id: number) => void;
  onChanged: (m: string) => void;
  onError: (m: string) => void;
}) {
  const [name, setName] = useState('');
  const [template, setTemplate] = useState<Template>('blank');
  const file = useRef<HTMLInputElement>(null);

  const create = async () => {
    try {
      let instance: unknown;
      if (template === 'import') {
        const f = file.current?.files?.[0];
        if (!f) return onError('Choose a JSON file to import.');
        instance = JSON.parse(await f.text());
      }
      const { id } = await createTimetable({ name: name.trim() || undefined, template, instance });
      onOpen(id);
    } catch (e) {
      onError((e as Error).message);
    }
  };

  return (
    <>
      <section className="card" style={{ marginBottom: 18 }}>
        <h2>New timetable</h2>
        <div className="row" style={{ gap: 12, flexWrap: 'wrap', alignItems: 'flex-end', marginTop: 8 }}>
          <label className="field" style={{ minWidth: 220 }}>
            Name
            <input className="input" value={name} placeholder="e.g. TY Computer – Sem V" onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="field">
            Start from
            <select className="input" value={template} onChange={(e) => setTemplate(e.target.value as Template)}>
              {TEMPLATES.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
          {template === 'import' && <input ref={file} type="file" accept=".json,application/json" />}
          <button className="btn accent" onClick={create}>
            + Create
          </button>
        </div>
      </section>

      <section className="card table-wrap">
        <h2 style={{ marginBottom: 10 }}>Saved timetables</h2>
        {rows === null ? (
          <p className="muted">Loading…</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Size</th>
                <th>Schedule</th>
                <th>Updated</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} onClick={() => onOpen(r.id)}>
                  <td>
                    <b>{r.name}</b>
                  </td>
                  <td className="tiny">
                    {r.classes} classes · {r.groups} class groups · {r.teachers} teachers · {r.rooms} rooms
                  </td>
                  <td>
                    <span className={`chip ${STATUS[r.schedule].cls}`}>{STATUS[r.schedule].text}</span>
                  </td>
                  <td className="tiny">{new Date(r.updatedAt).toLocaleString()}</td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <div className="row" style={{ gap: 6, justifyContent: 'flex-end' }}>
                      <button className="btn sm" onClick={() => onOpen(r.id)}>
                        Open
                      </button>
                      <button
                        className="btn sm ghost"
                        onClick={() =>
                          duplicateTimetable(r.id)
                            .then(() => onChanged(`Duplicated "${r.name}".`))
                            .catch((e: Error) => onError(e.message))
                        }
                      >
                        Duplicate
                      </button>
                      <button
                        className="btn sm ghost"
                        onClick={() => {
                          if (!confirm(`Delete "${r.name}"? This cannot be undone. The published timetable is not affected.`)) return;
                          deleteTimetable(r.id)
                            .then(() => onChanged(`Deleted "${r.name}".`))
                            .catch((e: Error) => onError(e.message));
                        }}
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  );
}

// ---------------------------------------------------------------------------
// editor
// ---------------------------------------------------------------------------
function Editor({
  id,
  tab,
  onTab,
  onBack,
  onMsg,
  onError,
}: {
  id: number;
  tab: string;
  onTab: (t: string) => void;
  onBack: () => void;
  onMsg: (m: string | null) => void;
  onError: (m: string | null) => void;
}) {
  const nav = useNavigate();
  const [detail, setDetail] = useState<TimetableDetail | null>(null);
  const [name, setName] = useState('');

  const reload = useCallback(() => {
    getTimetable(id)
      .then((d) => {
        setDetail(d);
        setName(d.name);
      })
      .catch((e: Error) => onError(e.message));
  }, [id, onError]);
  useEffect(reload, [reload]);

  if (!detail) return <p className="muted">Loading…</p>;

  const optimise = () => {
    if (!detail.instance.offerings.length) return onError('Add classes, teachers, rooms and courses before optimising.');
    const store = useStore.getState();
    store.setRunParams({ scenario: 'saved', timetableId: id, ...sizeDefaults(detail.instance.events.length) });
    nav('/');
    store.runOptimizer();
  };

  return (
    <>
      <div className="toolbar" style={{ marginBottom: 14 }}>
        <button className="btn ghost sm" onClick={onBack}>
          ← All timetables
        </button>
        <input className="input" style={{ minWidth: 260, fontWeight: 700 }} value={name} onChange={(e) => setName(e.target.value)} />
        {name.trim() && name !== detail.name && (
          <button
            className="btn sm"
            onClick={() =>
              updateTimetable(id, { name })
                .then(() => (onMsg('Renamed.'), reload()))
                .catch((e: Error) => onError(e.message))
            }
          >
            Rename
          </button>
        )}
        <div style={{ flex: 1 }} />
        <button className="btn accent" onClick={optimise}>
          ▶ Optimise this timetable
        </button>
        <button
          className="btn"
          disabled={detail.schedule !== 'ok'}
          title={detail.schedule === 'ok' ? '' : 'Needs a complete, clash-free schedule'}
          onClick={() => {
            if (!confirm(`Publish "${detail.name}"? Teachers and students will see it.`)) return;
            publishSaved(id)
              .then(() => onMsg(`Published "${detail.name}". Teachers and students now see it.`))
              .catch((e: Error) => onError(e.message));
          }}
        >
          ★ Publish
        </button>
      </div>
      <div className="seg" style={{ marginBottom: 14 }}>
        <button className={tab === 'data' ? 'on' : ''} onClick={() => onTab('data')}>
          Data: classes, teachers, rooms, courses
        </button>
        <button className={tab === 'schedule' ? 'on' : ''} onClick={() => onTab('schedule')}>
          Schedule {detail.schedule === 'ok' ? '✓' : detail.schedule === 'none' ? '' : '⚠'}
        </button>
      </div>
      {tab === 'schedule' ? (
        <ScheduleEditor detail={detail} onSaved={(m) => (onMsg(m), reload())} onError={onError} onOptimise={optimise} />
      ) : (
        <DataEditor detail={detail} onSaved={(m) => (onMsg(m), reload())} onError={onError} />
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// data editor
// ---------------------------------------------------------------------------
type Row = Record<string, unknown>;

function DataEditor({ detail, onSaved, onError }: { detail: TimetableDetail; onSaved: (m: string) => void; onError: (m: string | null) => void }) {
  const [inst, setInst] = useState<Instance>(() => structuredClone(detail.instance));
  const [warnings, setWarnings] = useState<string[]>(detail.warnings);
  // keep the editor in step when the saved copy is reloaded
  useEffect(() => setInst(structuredClone(detail.instance)), [detail.instance]);
  const dirty = JSON.stringify(inst) !== JSON.stringify(detail.instance);
  const grid = inst.grid;

  const patch = (p: Partial<Instance>) => setInst((x) => ({ ...x, ...p }));
  const setGrid = (g: Partial<Instance['grid']>, reshape = false) =>
    setInst((x) => ({
      ...x,
      grid: { ...x.grid, ...g, lunchPeriods: g.lunchPeriod != null ? (g.lunchPeriod >= 0 ? [g.lunchPeriod] : []) : x.grid.lunchPeriods },
      // blocked slots are day*periods+period: they no longer mean the same thing when the grid changes shape
      faculty: reshape ? x.faculty.map((f) => ({ ...f, unavailable: [] })) : x.faculty,
      rooms: reshape ? x.rooms.map((r) => ({ ...r, unavailable: [] })) : x.rooms,
    }));

  const save = async () => {
    onError(null);
    try {
      const r = await updateTimetable(detail.id, { instance: inst });
      setInst(structuredClone(r.instance)); // the server's normalised copy is now the saved state
      setWarnings(r.warnings);
      onSaved(r.warnings.length ? 'Saved. Check the warnings below before optimising.' : 'Saved.');
    } catch (e) {
      onError((e as Error).message);
    }
  };

  const remove = (key: 'groups' | 'faculty' | 'rooms', rid: string) =>
    setInst((x) => ({
      ...x,
      [key]: (x[key] as { id: string }[]).filter((r) => r.id !== rid),
      offerings: x.offerings.map((o) => ({
        ...o,
        groupIds: key === 'groups' ? o.groupIds.filter((g) => g !== rid) : o.groupIds,
        eligibleFaculty: key === 'faculty' ? o.eligibleFaculty.filter((f) => f !== rid) : o.eligibleFaculty,
      })),
    }));

  const edit = <K extends 'groups' | 'faculty' | 'rooms' | 'offerings'>(key: K, rid: string, p: Row) =>
    setInst((x) => ({ ...x, [key]: (x[key] as unknown as Row[]).map((r) => (r.id === rid ? { ...r, ...p } : r)) }));

  const num = (v: string, min = 1) => Math.max(min, Math.floor(Number(v) || min));

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      <section className="card">
        <h2>Week and periods</h2>
        <div className="row" style={{ gap: 16, flexWrap: 'wrap', alignItems: 'flex-end', marginTop: 8 }}>
          <div className="field">
            Teaching days
            <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
              {ALL_DAYS.map((d) => (
                <label key={d} className="check">
                  <input
                    type="checkbox"
                    checked={grid.days.includes(d)}
                    onChange={(e) => setGrid({ days: ALL_DAYS.filter((x) => (x === d ? e.target.checked : grid.days.includes(x))) }, true)}
                  />
                  {d}
                </label>
              ))}
            </div>
          </div>
          <label className="field" style={{ width: 130 }}>
            Periods per day
            <input
              className="input"
              type="number"
              min={1}
              max={14}
              value={grid.periods.length}
              onChange={(e) => {
                const n = Math.min(14, num(e.target.value));
                setGrid({ periods: hourLabels(n, 9), lunchPeriod: grid.lunchPeriod < n ? grid.lunchPeriod : -1 }, true);
              }}
            />
          </label>
          <label className="field">
            Lunch break
            <select className="input" value={grid.lunchPeriod} onChange={(e) => setGrid({ lunchPeriod: Number(e.target.value) })}>
              <option value={-1}>No lunch break</option>
              {grid.periods.map((p, i) => (
                <option key={i} value={i}>
                  {p}
                </option>
              ))}
            </select>
          </label>
        </div>
        <p className="tiny" style={{ marginBottom: 0 }}>
          Period labels: {grid.periods.join(' · ')}. Changing the days or periods clears blocked periods stored in this timetable.
        </p>
      </section>

      <EditableTable
        title="Classes (student groups)"
        rows={inst.groups as unknown as Row[]}
        columns={[
          { key: 'name', label: 'Name', type: 'text' },
          { key: 'strength', label: 'Students', type: 'number' },
        ]}
        onAdd={() => patch({ groups: [...inst.groups, { id: newId('g', inst.groups.map((g) => g.id)), name: 'New class', strength: 40 }] })}
        onEdit={(rid, p) => edit('groups', rid, p.strength != null ? { ...p, strength: num(String(p.strength)) } : p)}
        onDelete={(rid) => remove('groups', rid)}
      />
      <EditableTable
        title="Teachers"
        rows={inst.faculty as unknown as Row[]}
        columns={[
          { key: 'name', label: 'Name', type: 'text' },
          { key: 'maxWeekly', label: 'Max periods / week', type: 'number' },
          { key: 'maxDaily', label: 'Max periods / day', type: 'number' },
        ]}
        onAdd={() =>
          patch({ faculty: [...inst.faculty, { id: newId('t', inst.faculty.map((f) => f.id)), name: 'New teacher', maxWeekly: 12, maxDaily: 4 }] })
        }
        onEdit={(rid, p) => edit('faculty', rid, Object.fromEntries(Object.entries(p).map(([k, v]) => [k, k === 'name' ? v : num(String(v))])))}
        onDelete={(rid) => remove('faculty', rid)}
      />
      <EditableTable
        title="Rooms and labs"
        rows={inst.rooms as unknown as Row[]}
        columns={[
          { key: 'name', label: 'Name', type: 'text' },
          { key: 'capacity', label: 'Seats', type: 'number' },
          { key: 'type', label: 'Type', type: 'select', options: ['classroom', 'lab', 'hall'] },
        ]}
        onAdd={() =>
          patch({ rooms: [...inst.rooms, { id: newId('r', inst.rooms.map((r) => r.id)), name: 'New room', capacity: 60, type: 'classroom' as RoomType }] })
        }
        onEdit={(rid, p) =>
          edit('rooms', rid, p.capacity != null ? { ...p, capacity: num(String(p.capacity)) } : p.type != null ? { ...p, kind: p.type === 'lab' ? 'lab' : 'classroom' } : p)
        }
        onDelete={(rid) => remove('rooms', rid)}
      />

      <section className="card table-wrap">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <h2>Courses</h2>
          <button
            className="btn sm"
            onClick={() =>
              patch({
                offerings: [
                  ...inst.offerings,
                  {
                    id: newId('c', inst.offerings.map((o) => o.id)),
                    code: 'NEW',
                    subject: 'New course',
                    type: 'theory',
                    sessionsPerWeek: 3,
                    duration: 1,
                    groupIds: inst.groups[0] ? [inst.groups[0].id] : [],
                    eligibleFaculty: inst.faculty[0] ? [inst.faculty[0].id] : [],
                  } as Offering,
                ],
              })
            }
          >
            + Add course
          </button>
        </div>
        <p className="tiny" style={{ marginTop: 0 }}>
          Each course is taught by one of its eligible teachers (the optimiser chooses). Labs need a lab room; a session of length 2 takes two
          consecutive periods.
        </p>
        <table className="table">
          <thead>
            <tr>
              <th>Code</th>
              <th>Course</th>
              <th>Type</th>
              <th>Sessions / week</th>
              <th>Length (periods)</th>
              <th>Classes</th>
              <th>Teachers who can teach it</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {inst.offerings.map((o) => (
              <tr key={o.id} style={{ cursor: 'default' }}>
                <td>
                  <input className="input" style={{ width: 90 }} value={o.code} onChange={(e) => edit('offerings', o.id, { code: e.target.value })} />
                </td>
                <td>
                  <input className="input" value={o.subject} onChange={(e) => edit('offerings', o.id, { subject: e.target.value })} />
                </td>
                <td>
                  <select
                    className="input"
                    value={o.type}
                    onChange={(e) =>
                      edit('offerings', o.id, {
                        type: e.target.value,
                        roomKind: e.target.value === 'lab' ? 'lab' : 'classroom',
                        distinctDays: e.target.value !== 'lab',
                        duration: e.target.value === 'lab' ? Math.max(2, o.duration ?? 2) : o.duration ?? 1,
                      })
                    }
                  >
                    <option value="theory">theory</option>
                    <option value="tutorial">tutorial</option>
                    <option value="lab">lab</option>
                  </select>
                </td>
                <td>
                  <input
                    className="input"
                    type="number"
                    min={1}
                    style={{ width: 70 }}
                    value={o.sessionsPerWeek}
                    onChange={(e) => edit('offerings', o.id, { sessionsPerWeek: num(e.target.value) })}
                  />
                </td>
                <td>
                  <input
                    className="input"
                    type="number"
                    min={1}
                    style={{ width: 70 }}
                    value={o.duration ?? 1}
                    onChange={(e) => edit('offerings', o.id, { duration: num(e.target.value) })}
                  />
                </td>
                <td>
                  <MultiPick options={inst.groups} value={o.groupIds} onChange={(v) => edit('offerings', o.id, { groupIds: v })} />
                </td>
                <td>
                  <MultiPick options={inst.faculty} value={o.eligibleFaculty} onChange={(v) => edit('offerings', o.id, { eligibleFaculty: v })} />
                </td>
                <td>
                  <button className="btn sm ghost" onClick={() => patch({ offerings: inst.offerings.filter((x) => x.id !== o.id) })}>
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {warnings.length > 0 && (
        <div className="error-box">
          <b>Before optimising:</b>
          <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
            {warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </div>
      )}
      <div className="row" style={{ gap: 10, position: 'sticky', bottom: 10 }}>
        <button className="btn accent" disabled={!dirty} onClick={save}>
          {dirty ? 'Save data' : '✓ Saved'}
        </button>
        {dirty && (
          <button className="btn ghost" onClick={() => setInst(structuredClone(detail.instance))}>
            Discard changes
          </button>
        )}
        <span className="tiny">
          {inst.groups.length} classes · {inst.faculty.length} teachers · {inst.rooms.length} rooms · {inst.offerings.length} courses ·{' '}
          {inst.offerings.reduce((n, o) => n + o.sessionsPerWeek, 0)} sessions a week. A saved schedule stays attached to the sessions that still
          exist.
        </span>
      </div>
    </div>
  );
}

function EditableTable({
  title,
  rows,
  columns,
  onAdd,
  onEdit,
  onDelete,
}: {
  title: string;
  rows: Row[];
  columns: { key: string; label: string; type: 'text' | 'number' | 'select'; options?: string[] }[];
  onAdd: () => void;
  onEdit: (id: string, p: Row) => void;
  onDelete: (id: string) => void;
}) {
  return (
    <section className="card table-wrap">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h2>{title}</h2>
        <button className="btn sm" onClick={onAdd}>
          + Add
        </button>
      </div>
      <table className="table">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key}>{c.label}</th>
            ))}
            <th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={String(r.id)} style={{ cursor: 'default' }}>
              {columns.map((c) => (
                <td key={c.key}>
                  {c.type === 'select' ? (
                    <select className="input" value={String(r[c.key])} onChange={(e) => onEdit(String(r.id), { [c.key]: e.target.value })}>
                      {c.options!.map((o) => (
                        <option key={o}>{o}</option>
                      ))}
                    </select>
                  ) : (
                    <input
                      className="input"
                      type={c.type}
                      min={c.type === 'number' ? 1 : undefined}
                      style={c.type === 'number' ? { width: 90 } : undefined}
                      value={String(r[c.key] ?? '')}
                      onChange={(e) => onEdit(String(r.id), { [c.key]: e.target.value })}
                    />
                  )}
                </td>
              ))}
              <td>
                <button className="btn sm ghost" onClick={() => onDelete(String(r.id))}>
                  ✕
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length && <p className="muted">None yet.</p>}
    </section>
  );
}

function MultiPick({ options, value, onChange }: { options: { id: string; name: string }[]; value: string[]; onChange: (v: string[]) => void }) {
  return (
    <details className="multipick">
      <summary className="input" style={{ cursor: 'pointer', minWidth: 150 }}>
        {value.length ? value.map((v) => options.find((o) => o.id === v)?.name ?? v).join(', ') : <span className="muted">none</span>}
      </summary>
      <div className="card" style={{ position: 'absolute', zIndex: 5, padding: 10, display: 'grid', gap: 4, maxHeight: 240, overflowY: 'auto' }}>
        {options.map((o) => (
          <label key={o.id} className="check">
            <input
              type="checkbox"
              checked={value.includes(o.id)}
              onChange={(e) => onChange(e.target.checked ? [...value, o.id] : value.filter((v) => v !== o.id))}
            />
            {o.name}
          </label>
        ))}
      </div>
    </details>
  );
}

// ---------------------------------------------------------------------------
// schedule editor (edit by hand, checked live)
// ---------------------------------------------------------------------------
function ScheduleEditor({
  detail,
  onSaved,
  onError,
  onOptimise,
}: {
  detail: TimetableDetail;
  onSaved: (m: string) => void;
  onError: (m: string | null) => void;
  onOptimise: () => void;
}) {
  const theme = useStore((s) => s.theme);
  const inst = detail.instance;
  const [draft, setDraft] = useState<SavedSchedule | null>(() => (detail.solution ? structuredClone(detail.solution) : null));
  const [status, setStatus] = useState<ScheduleCheck>(detail.check);
  const [selected, setSelected] = useState<string | null>(null);
  const [view, setView] = useState<{ kind: ViewKind; entityId: string }>({ kind: 'group', entityId: inst.groups[0]?.id ?? '' });
  const dirty = JSON.stringify(draft) !== JSON.stringify(detail.solution);
  const size = aspects.find((a) => a.id === theme.aspect) ?? aspects[0];

  // live independent check of every change
  useEffect(() => {
    if (!draft || !dirty) return;
    const t = setTimeout(() => {
      checkSchedule(detail.id, draft)
        .then(setStatus)
        .catch((e: Error) => onError(e.message));
    }, 250);
    return () => clearTimeout(t);
  }, [draft, dirty, detail.id, onError]);

  const events = useMemo(() => Object.fromEntries(inst.events.map((e) => [e.id, e])), [inst]);
  const offerings = useMemo(() => Object.fromEntries(inst.offerings.map((o) => [o.id, o])), [inst]);
  const name = useMemo(() => {
    const m: Record<string, string> = {};
    [...inst.groups, ...inst.faculty, ...inst.rooms].forEach((x) => (m[x.id] = x.name));
    return m;
  }, [inst]);

  if (!inst.events.length)
    return <p className="muted">This timetable has no courses yet. Add them on the Data tab, then optimise.</p>;
  if (!draft)
    return (
      <section className="card">
        <h2>No schedule yet</h2>
        <p className="muted">Let the optimiser build the best timetable for this data, or start with an empty grid and place every class by hand.</p>
        <div className="row" style={{ gap: 10 }}>
          <button className="btn accent" onClick={onOptimise}>
            ▶ Optimise this timetable
          </button>
          <button
            className="btn"
            onClick={() => {
              const empty = { assignments: [], facultyOf: Object.fromEntries(inst.offerings.map((o) => [o.id, o.eligibleFaculty[0] ?? ''])) };
              setDraft(empty);
              setStatus({ exists: true, feasible: false, unplaced: inst.events.map((e) => e.id) });
            }}
          >
            Place classes by hand
          </button>
        </div>
      </section>
    );

  const assignment = selected ? draft.assignments.find((a) => a.eventId === selected) : undefined;
  const ev = selected ? events[selected] : undefined;
  const off = ev ? offerings[ev.offeringId] : undefined;
  const unplaced = status.unplaced ?? [];
  const solution = { id: draft.id ?? 'EDIT', objectives: status.objectives ?? { f1: 0, f2: 0, f3: 0 }, onFront: true, ...draft } as Solution;

  const place = (p: Partial<{ day: number; period: number; roomId: string }>) => {
    if (!selected) return;
    setDraft((d) => {
      if (!d) return d;
      const exists = d.assignments.some((a) => a.eventId === selected);
      const base = exists
        ? d.assignments.map((a) => (a.eventId === selected ? { ...a, ...p } : a))
        : [...d.assignments, { eventId: selected, day: 0, period: inst.grid.lunchPeriod === 0 ? 1 : 0, roomId: inst.rooms[0]?.id ?? '', ...p }];
      return { ...d, assignments: base };
    });
  };
  const setTeacher = (fid: string) => off && setDraft((d) => (d ? { ...d, facultyOf: { ...d.facultyOf, [off.id]: fid } } : d));

  return (
    <div className="grid split" style={{ gap: 18, alignItems: 'start' }}>
      <section className="card">
        <div className="toolbar" style={{ marginBottom: 10 }}>
          <div className="seg">
            {(['group', 'faculty', 'room'] as ViewKind[]).map((k) => (
              <button
                key={k}
                className={view.kind === k ? 'on' : ''}
                onClick={() => setView({ kind: k, entityId: (k === 'group' ? inst.groups : k === 'faculty' ? inst.faculty : inst.rooms)[0]?.id ?? '' })}
              >
                {k === 'group' ? 'Class' : k === 'faculty' ? 'Teacher' : 'Room'}
              </button>
            ))}
          </div>
          <select className="input" style={{ width: 'auto' }} value={view.entityId} onChange={(e) => setView({ ...view, entityId: e.target.value })}>
            {(view.kind === 'group' ? inst.groups : view.kind === 'faculty' ? inst.faculty : inst.rooms).map((x) => (
              <option key={x.id} value={x.id}>
                {x.name}
              </option>
            ))}
          </select>
          <span className="tiny">Click a class in the timetable to move it.</span>
        </div>
        <PosterFrame w={size.w} h={size.h} maxH={620}>
          <TimetablePoster
            instance={inst}
            solution={solution}
            view={view}
            theme={theme}
            decorations={[]}
            blockNotes={{}}
            activeBlockId={selected}
            onBlockClick={(eid) => setSelected(eid)}
          />
        </PosterFrame>
      </section>

      <div style={{ display: 'grid', gap: 14, position: 'sticky', top: 10 }}>
        <section className="card" style={{ borderLeft: `6px solid ${status.feasible && !unplaced.length ? 'var(--sage)' : 'var(--accent)'}` }}>
          <h3>{status.feasible && !unplaced.length ? '✓ No clashes: every hard constraint holds' : '⚠ Not valid yet'}</h3>
          {!!unplaced.length && <p className="tiny">{unplaced.length} class(es) not placed yet.</p>}
          {status.violations && Object.keys(status.violations).length > 0 && <p className="tiny">Problems: {describeViolations(status.violations)}.</p>}
          {status.objectives && (
            <p className="tiny" style={{ marginBottom: 0 }}>
              Idle gaps {status.objectives.f1.toFixed(1)} · room waste {(status.objectives.f2 * 100).toFixed(1)}% · workload imbalance{' '}
              {status.objectives.f3.toFixed(3)}
            </p>
          )}
          <div className="row" style={{ gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
            <button
              className="btn accent sm"
              disabled={!dirty || !status.feasible || !!unplaced.length}
              onClick={() =>
                saveSchedule(detail.id, draft)
                  .then(() => onSaved('Schedule saved.'))
                  .catch((e: Error) => onError(e.message))
              }
            >
              Save schedule
            </button>
            {dirty && (
              <button className="btn ghost sm" onClick={() => (setDraft(detail.solution ? structuredClone(detail.solution) : null), setStatus(detail.check))}>
                Undo all changes
              </button>
            )}
            {detail.solution && (
              <button
                className="btn ghost sm"
                onClick={() => {
                  if (!confirm('Remove the saved schedule? The data stays.')) return;
                  clearSchedule(detail.id)
                    .then(() => onSaved('Schedule removed.'))
                    .catch((e: Error) => onError(e.message));
                }}
              >
                Remove schedule
              </button>
            )}
          </div>
        </section>

        {!!unplaced.length && (
          <section className="card">
            <h3>Not placed</h3>
            <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
              {unplaced.map((eid) => (
                <button key={eid} className={`btn sm ${selected === eid ? '' : 'ghost'}`} onClick={() => setSelected(eid)}>
                  {offerings[events[eid]?.offeringId]?.code ?? eid} · {offerings[events[eid]?.offeringId]?.groupIds.map((g) => name[g]).join(', ')}
                </button>
              ))}
            </div>
          </section>
        )}

        <section className="card">
          {!selected || !ev || !off ? (
            <p className="muted" style={{ margin: 0 }}>
              Select a class to change its day, time, room or teacher.
            </p>
          ) : (
            <>
              <h3>
                {off.code} · {off.subject}
              </h3>
              <p className="tiny">
                {off.groupIds.map((g) => name[g]).join(', ')} · {ev.length} period{ev.length > 1 ? 's' : ''}
              </p>
              <div style={{ display: 'grid', gap: 10 }}>
                <label className="field">
                  Day
                  <select className="input" value={assignment?.day ?? ''} onChange={(e) => place({ day: Number(e.target.value) })}>
                    {!assignment && <option value="">choose…</option>}
                    {inst.grid.days.map((d, i) => (
                      <option key={d} value={i}>
                        {d}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  Starts at
                  <select className="input" value={assignment?.period ?? ''} onChange={(e) => place({ period: Number(e.target.value) })}>
                    {!assignment && <option value="">choose…</option>}
                    {inst.grid.periods.map((p, i) =>
                      i === inst.grid.lunchPeriod ? null : (
                        <option key={i} value={i}>
                          {p}
                        </option>
                      ),
                    )}
                  </select>
                </label>
                <label className="field">
                  Room
                  <select className="input" value={assignment?.roomId ?? ''} onChange={(e) => place({ roomId: e.target.value })}>
                    {!assignment && <option value="">choose…</option>}
                    {inst.rooms.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.name} ({r.type}, {r.capacity} seats)
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  Teacher (for every session of this course)
                  <select className="input" value={draft.facultyOf[off.id] ?? ''} onChange={(e) => setTeacher(e.target.value)}>
                    {off.eligibleFaculty.map((f) => (
                      <option key={f} value={f}>
                        {name[f] ?? f}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
