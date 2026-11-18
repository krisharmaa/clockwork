import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../auth';
import { useStore } from '../store';
import { suggestions } from '../lib/insights';
import { scrollToId } from '../lib/scroll';
import type { ScheduleCheck } from '../timetables';
import TimetablePoster from './TimetablePoster';
import PosterFrame from './PosterFrame';
import { aspects } from '../themes/designs';
import type { Instance, Solution, ViewKind } from '../types';

interface Starter {
  kind: 'published' | 'saved' | 'starting' | 'empty';
  name: string | null;
  timetableId: number | null;
  instance: Instance | null;
  solution: (Pick<Solution, 'assignments' | 'facultyOf'> & { id?: string }) | null;
  check: ScheduleCheck;
}

const LABEL: Record<Starter['kind'], string> = {
  published: 'Published timetable',
  saved: 'Saved timetable',
  starting: 'Starting timetable · not optimised yet',
  empty: '',
};

// Validation-study budgets by size (as on the Overview).
const sizeDefaults = (events: number) => (events <= 250 ? { budget: 360, searchSeconds: 6 } : { budget: 240, searchSeconds: 16 });

/** Shown on the Overview before any optimiser run: the current timetable and a prompt to optimise it. */
export default function StartTimetable() {
  const { theme, setRunParams, running, resultsReady, instance: mockInst, solutions: mockSolutions } = useStore();
  const [data, setData] = useState<Starter | null>(null);
  const [offline, setOffline] = useState(false);
  const [view, setView] = useState<{ kind: ViewKind; entityId: string } | null>(null);

  useEffect(() => {
    api<Starter>('/starter')
      .then((s) => {
        setData(s);
        // On a first visit, "Run optimiser" works on exactly the timetable shown here.
        if (useStore.getState().resultsReady) return;
        if (s.kind === 'published') setRunParams({ scenario: 'published', ...sizeDefaults(s.instance!.events.length) });
        else if (s.timetableId) setRunParams({ scenario: 'saved', timetableId: s.timetableId, ...sizeDefaults(s.instance!.events.length) });
      })
      .catch(() => setOffline(true));
  }, [setRunParams]);

  const inst: Instance | null = offline ? mockInst : data?.instance ?? null;
  const sol: Solution | null = useMemo(() => {
    if (offline) return mockSolutions[0] ?? null;
    if (!data?.solution) return null;
    const o = data.check.objectives ?? { f1: 0, f2: 0, f3: 0 };
    return { id: data.solution.id ?? 'CURRENT', objectives: o, onFront: false, metrics: data.check.metrics, ...data.solution } as Solution;
  }, [offline, data, mockSolutions]);
  const tips = useMemo(() => (inst && sol ? suggestions(inst, sol) : []), [inst, sol]);

  // Take the user to the optimiser and point at the Run button; the user starts the run.
  const goToOptimiser = () => {
    scrollToId('optimiser');
    const btn = document.getElementById('run-optimiser-btn');
    btn?.classList.remove('pulse');
    void btn?.offsetWidth; // restart the animation
    btn?.classList.add('pulse');
    setTimeout(() => btn?.classList.remove('pulse'), 3200);
  };

  if (!offline && data === null) return <section className="card" style={{ marginBottom: 22 }}>Loading the current timetable…</section>;
  if (!inst || !sol || data?.kind === 'empty')
    return (
      <section className="card" style={{ marginBottom: 22 }}>
        <h2>No timetable yet</h2>
        <p className="muted">
          Add your department&apos;s classes, teachers, rooms and courses in <Link to="/timetables">Edit timetables</Link>, then optimise it.
        </p>
      </section>
    );

  const v =
    view && (view.kind === 'group' ? inst.groups : view.kind === 'faculty' ? inst.faculty : inst.rooms).some((x) => x.id === view.entityId)
      ? view
      : { kind: 'group' as ViewKind, entityId: inst.groups[0]?.id ?? '' };
  const size = aspects.find((a) => a.id === theme.aspect) ?? aspects[0];
  const m = sol.metrics ?? {};

  return (
    <section id="current-timetable" className="card" style={{ marginBottom: 22 }}>
      <span className="chip">{offline ? 'Offline demo data' : `${resultsReady ? 'Before optimising · ' : ''}${LABEL[data!.kind]}`}</span>
      <h2 style={{ fontSize: 24, margin: '6px 0 2px' }}>{offline ? inst.name : data!.name ?? inst.name}</h2>
      <span className="tiny">
        {inst.events.length} classes a week · {inst.groups.length} class groups · {inst.faculty.length} teachers · {inst.rooms.length} rooms
      </span>

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
            <TimetablePoster instance={inst} solution={sol} view={v} theme={theme} decorations={[]} blockNotes={{}} />
          </PosterFrame>
        </div>

        <div style={{ display: 'grid', gap: 14 }}>
          {resultsReady ? (
            <div className="optimise-hint done">
              <b>✓ Optimised</b>
              <p className="tiny" style={{ margin: '4px 0 10px' }}>
                The final timetable and the other recommended options are below the optimiser.
              </p>
              <button className="btn sm" onClick={() => scrollToId('final-timetable')}>
                See the results ↓
              </button>
            </div>
          ) : (
            <div className="optimise-hint">
              <b>✨ This timetable can be optimised</b>
              <p className="tiny" style={{ margin: '4px 0 10px' }}>
                The optimiser searches for clash-free timetables with fewer idle periods, rooms that fit each class and a fairer teaching load,
                then recommends the best compromise.
              </p>
              <button className="btn accent sm" onClick={goToOptimiser} disabled={running}>
                Go to the optimiser ↓
              </button>
            </div>
          )}
          <div>
            <div className="section-title">This timetable today</div>
            <div className="mini-stats">
              <div>
                <b>{m.student_gaps ?? sol.objectives.f1}</b>
                <span>idle periods for students per week</span>
              </div>
              <div>
                <b>{m.room_utilization != null ? `${(m.room_utilization * 100).toFixed(0)}%` : `${((1 - sol.objectives.f2) * 100).toFixed(0)}%`}</b>
                <span>of seats filled in the rooms used</span>
              </div>
              <div>
                <b>{m.max_faculty_daily_load ?? '—'}</b>
                <span>most periods any teacher has in one day</span>
              </div>
              <div>
                <b>{sol.objectives.f3.toFixed(3)}</b>
                <span>workload imbalance between teachers (0 = equal)</span>
              </div>
            </div>
          </div>
          <div>
            <div className="section-title">Suggestions for the department</div>
            <ul className="tiny" style={{ margin: 0, paddingLeft: 18, lineHeight: 1.7 }}>
              {tips.map((t) => (
                <li key={t}>{t}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
