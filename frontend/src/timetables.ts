import { api, del, post, put } from './auth';
import type { Instance, Solution } from './types';

// ---- Saved timetables (api/timetables.py) ----
export interface TimetableSummary {
  id: number;
  name: string;
  source: string;
  updatedAt: string;
  createdBy: string;
  classes: number;
  groups: number;
  teachers: number;
  rooms: number;
  courses: number;
  schedule: 'none' | 'ok' | 'needs attention';
}

export interface ScheduleCheck {
  exists: boolean;
  feasible?: boolean;
  violations?: Record<string, number>;
  objectives?: { f1: number; f2: number; f3: number };
  metrics?: Record<string, number>;
  unplaced?: string[];
  error?: string;
}

/** The part of a solution a saved timetable stores. */
export type SavedSchedule = Pick<Solution, 'assignments' | 'facultyOf'> & { id?: string; objectives?: Solution['objectives'] };

export interface TimetableDetail extends TimetableSummary {
  instance: Instance;
  solution: SavedSchedule | null;
  check: ScheduleCheck;
  warnings: string[];
}

export type Template = 'blank' | 'demo' | 'small' | 'medium' | 'large' | 'published' | 'import' | 'data';

export const listTimetables = () => api<TimetableSummary[]>('/timetables');
export const getTimetable = (id: number) => api<TimetableDetail>(`/timetables/${id}`);
export const createTimetable = (body: { name?: string; template: Template; instance?: unknown; solution?: unknown }) =>
  post<{ id: number }>('/timetables', body);
export const updateTimetable = (id: number, body: { name?: string; instance?: Instance }) =>
  put<{ ok: boolean; warnings: string[]; check: ScheduleCheck; instance: Instance }>(`/timetables/${id}`, body);
export const duplicateTimetable = (id: number) => post<{ id: number }>(`/timetables/${id}/duplicate`);
export const deleteTimetable = (id: number) => del<{ ok: boolean }>(`/timetables/${id}`);
export const checkSchedule = (id: number, solution: SavedSchedule) => post<ScheduleCheck>(`/timetables/${id}/check`, { solution });
export const saveSchedule = (id: number, solution: SavedSchedule) => put<{ ok: boolean; check: ScheduleCheck }>(`/timetables/${id}/schedule`, { solution });
export const clearSchedule = (id: number) => del<{ ok: boolean }>(`/timetables/${id}/schedule`);
export const publishSaved = (id: number) => post<{ ok: boolean }>(`/timetables/${id}/publish`);

/** Plain-language names for the evaluator's violation categories. */
export const VIOLATION_TEXT: Record<string, string> = {
  room_clash: 'two classes in the same room at once',
  faculty_clash: 'a teacher in two places at once',
  student_clash: 'a class with two lectures at once',
  same_day_sessions: 'two sessions of a course on the same day',
  room_capacity: 'a room too small for the class',
  room_type: 'wrong kind of room (e.g. a lab in a classroom)',
  room_unavailable: 'a room used when it is unavailable',
  faculty_unavailable: 'a teacher scheduled when unavailable',
  invalid_teacher: 'a teacher who cannot teach that course',
  daily_overload: 'a teacher over their daily limit',
  weekly_overload: 'a teacher over their weekly limit',
  lunch: 'a class during lunch',
  day_boundary: 'a class running past the end of the day',
  missing_event: 'a class not placed',
  placement_count: 'a class placed the wrong number of times',
  teacher_count: 'a course without exactly one teacher',
  invalid_room: 'an unknown room',
  invalid_start: 'an invalid start time',
  invalid_placement: 'an invalid placement',
  invalid: 'invalid entries',
};

export const describeViolations = (v: Record<string, number> | undefined) =>
  Object.entries(v ?? {})
    .map(([k, n]) => `${VIOLATION_TEXT[k] ?? k.replace(/_/g, ' ')} (${n})`)
    .join('; ');

/** A short id that is not used yet, e.g. newId('t', ['t1', 't2']) -> 't3'. */
export function newId(prefix: string, existing: string[]): string {
  const used = new Set(existing);
  let i = existing.length + 1;
  while (used.has(`${prefix}${i}`)) i++;
  return `${prefix}${i}`;
}
