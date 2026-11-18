import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { post } from '../auth';
import { useStore } from '../store';
import { representativePicks } from '../mock/solutions';
import { createTimetable, saveSchedule } from '../timetables';
import TimetablePoster from './TimetablePoster';
import PosterFrame from './PosterFrame';
import { aspects } from '../themes/designs';
import type { ViewKind } from '../types';
import { suggestions } from '../lib/insights';

const fmtDiff = (n: number, unit: string, better: 'lower' | 'higher') => {
  if (Math.abs(n) < 1e-9) return `same ${unit}`;
  const good = better === 'lower' ? n < 0 : n > 0;
  return `${good ? '▲ ' : '▼ '}${Math.abs(n) % 1 ? Math.abs(n).toFixed(1) : Math.abs(n)} ${unit} ${n < 0 ? 'fewer' : 'more'}`;
};

/** The single recommended timetable (best compromise of the latest run), shown first on the Overview. */
export default function FinalTimetable({ highlight }: { highlight: boolean }) {
  const { instance: inst, solutions, baseline, stats, source, theme, decorations, blockNotes, runParams, select } = useStore();
  const nav = useNavigate();
  const [view, setView] = useState<{ kind: ViewKind; entityId: string }>({ kind: 'group', entityId: inst.groups[0]?.id ?? '' });
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const front = useMemo(() => solutions.filter((s) => s.onFront), [solutions]);
  const final = front.length ? representativePicks(front).knee : solutions[0];
  const tips = useMemo(() => (final ? suggestions(inst, final) : []), [inst, final]);
  if (!final) return null;
  const v = (view.kind === 'group' ? inst.groups : view.kind === 'faculty' ? inst.faculty : inst.rooms).some((x) => x.id === view.entityId)
    ? view
    : { kind: 'group' as ViewKind, entityId: inst.groups[0]?.id ?? '' };
  const size = aspects.find((a) => a.id === theme.aspect) ?? aspects[0];
  const m = final.metrics ?? {};
  const b = baseline?.metrics;
  const live = source === 'backend';
  const savedId = runParams.scenario === 'saved' && runParams.timetableId ? runParams.timetableId : null;

  const act = async (fn: () => Promise<string | void>) => {
    setErr(null);
    setMsg(null);
    setBusy(true);
    try {
      const r = await fn();
      if (r) setMsg(r);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section id="final-timetable" className={`card final-card ${highlight ? 'flash' : ''}`} style={{ marginBottom: 22 }}>
      <div className="row" style={{ justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
        <div>
          <span className="chip accent">★ Final timetable</span>
          <h2 style={{ fontSize: 24, margin: '6px 0 2px' }}>{inst.name}</h2>
          <span className="tiny">
            {live
              ? `The best compromise among ${front.length} optimal timetable${front.length === 1 ? '' : 's'} found by the memetic optimiser (closest to the ideal on all three goals), independently checked: no clashes.`
              : 'Offline demo data: start the Python server and run the optimiser for real results.'}
          </span>
        </div>
      </div>

      <div className="grid split" style={{ gap: 20, marginTop: 14, alignItems: 'start' }}>
        <div>
          <div className="toolbar" style={{ marginBottom: 10 }}>
            <div className="seg">
              {(['group', 'faculty', 'room'] as ViewKind[]).map((k) => (
                <button
                  key={k}
                  className={v.kind === k ? 'on' : ''}
                  onClick={() => setView({ kind: k, entityId: (k === 'group' ? inst.groups : k === 'faculty' ? inst.faculty : inst.rooms)[0]?.id ?? '' })}
                >
                  {k === 'group' ? 'Class' : k === 'faculty' ? 'Teacher' : 'Room'}
                </button>
              ))}
            </div>
            <select className="input" style={{ width: 'auto' }} value={v.entityId} onChange={(e) => setView({ ...v, entityId: e.target.value })}>
              {(v.kind === 'group' ? inst.groups : v.kind === 'faculty' ? inst.faculty : inst.rooms).map((x) => (
                <option key={x.id} value={x.id}>
                  {x.name}
                </option>
              ))}
            </select>
          </div>
          <PosterFrame w={size.w} h={size.h} maxH={560}>
            <TimetablePoster instance={inst} solution={final} view={v} theme={theme} decorations={decorations} blockNotes={blockNotes} />
          </PosterFrame>
        </div>

        <div style={{ display: 'grid', gap: 14 }}>
          <div>
            <div className="section-title">What this timetable gives you</div>
            <div className="mini-stats">
              <div>
                <b>{m.student_gaps ?? final.objectives.f1}</b>
                <span>idle periods for students per week (all classes)</span>
              </div>
              <div>
                <b>{m.room_utilization != null ? `${(m.room_utilization * 100).toFixed(0)}%` : `${((1 - final.objectives.f2) * 100).toFixed(0)}%`}</b>
                <span>of seats filled in the rooms used</span>
              </div>
              <div>
                <b>{m.max_faculty_daily_load ?? '—'}</b>
                <span>most periods any teacher has in one day</span>
              </div>
              <div>
                <b>{final.objectives.f3.toFixed(3)}</b>
                <span>workload imbalance between teachers (0 = equal)</span>
              </div>
            </div>
          </div>
          {live && b && (
            <div>
              <div className="section-title">Compared with a simple greedy schedule</div>
              <ul className="tiny" style={{ margin: 0, paddingLeft: 18, lineHeight: 1.7 }}>
                <li>{fmtDiff((m.student_gaps ?? 0) - (b.student_gaps ?? 0), 'idle periods for students', 'lower')}</li>
                {m.faculty_gaps != null && b.faculty_gaps != null && <li>{fmtDiff(m.faculty_gaps - b.faculty_gaps, 'idle periods for teachers', 'lower')}</li>}
                {m.room_utilization != null && b.room_utilization != null && (
                  <li>
                    {((m.room_utilization - b.room_utilization) * 100).toFixed(1) === '0.0'
                      ? 'same seat use'
                      : `${m.room_utilization > b.room_utilization ? '▲' : '▼'} seat use ${(b.room_utilization * 100).toFixed(0)}% → ${(m.room_utilization * 100).toFixed(0)}%`}
                  </li>
                )}
                <li>
                  workload imbalance {baseline!.objectives.f3.toFixed(3)} → {final.objectives.f3.toFixed(3)}
                  {stats?.baselineMethod ? ' (same number of evaluations)' : ''}
                </li>
              </ul>
            </div>
          )}
          <div>
            <div className="section-title">Suggestions for the department</div>
            <ul className="tiny" style={{ margin: 0, paddingLeft: 18, lineHeight: 1.7 }}>
              {tips.map((t) => (
                <li key={t}>{t}</li>
              ))}
            </ul>
          </div>
          <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
            <button
              className="btn accent"
              disabled={!live || busy}
              onClick={() =>
                confirm('Publish this as the official timetable? Teachers and students will see it.') &&
                act(async () => {
                  await post('/timetable/publish', { instance: inst, solution: final, design: { theme, decorations, blockNotes } });
                  return 'Published. Teachers and students now see this timetable.';
                })
              }
            >
              ★ Publish
            </button>
            {savedId ? (
              <button
                className="btn"
                disabled={!live || busy}
                onClick={() =>
                  act(async () => {
                    await saveSchedule(savedId, final);
                    nav(`/timetables?id=${savedId}&tab=schedule`);
                  })
                }
              >
                Save &amp; edit by hand
              </button>
            ) : (
              <button
                className="btn"
                disabled={!live || busy}
                onClick={() =>
                  act(async () => {
                    const { id } = await createTimetable({ name: inst.name, template: 'data', instance: inst, solution: final });
                    nav(`/timetables?id=${id}&tab=schedule`);
                  })
                }
              >
                Save &amp; edit by hand
              </button>
            )}
            <button
              className="btn ghost"
              onClick={() => {
                select(final.id);
                nav('/designer');
              }}
            >
              Style it in the Designer
            </button>
          </div>
          {msg && <div className="tiny" style={{ color: 'var(--sage-ink, #3d6b4a)' }}>{msg}</div>}
          {err && <div className="error-box">{err}</div>}
        </div>
      </div>
    </section>
  );
}
