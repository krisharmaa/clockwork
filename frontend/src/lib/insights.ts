import type { Instance, Solution } from '../types';

/** Practical facts about a timetable, computed from the schedule itself. */
export function analyse(inst: Instance, s: Solution) {
  const P = inst.grid.periods.length;
  const lunch = new Set(inst.grid.lunchPeriods ?? (inst.grid.lunchPeriod >= 0 ? [inst.grid.lunchPeriod] : []));
  const teaching = inst.grid.days.length * (P - lunch.size);
  const ev = Object.fromEntries(inst.events.map((e) => [e.id, e]));
  const off = Object.fromEntries(inst.offerings.map((o) => [o.id, o]));
  const roomUse: Record<string, number> = Object.fromEntries(inst.rooms.map((r) => [r.id, 0]));
  const load: Record<string, number> = Object.fromEntries(inst.faculty.map((f) => [f.id, 0]));
  const busy: Record<string, Set<number>[]> = Object.fromEntries(inst.groups.map((g) => [g.id, inst.grid.days.map(() => new Set<number>())]));
  for (const a of s.assignments) {
    const e = ev[a.eventId];
    if (!e) continue;
    const o = off[e.offeringId];
    roomUse[a.roomId] = (roomUse[a.roomId] ?? 0) + e.length;
    const t = s.facultyOf[e.offeringId];
    if (t in load) load[t] += e.length;
    for (const g of o?.groupIds ?? []) for (let k = 0; k < e.length; k++) busy[g]?.[a.day]?.add(a.period + k);
  }
  const gaps: { group: string; day: number; gap: number }[] = [];
  const lonely: { group: string; day: number; period: number }[] = [];
  for (const [g, days] of Object.entries(busy))
    days.forEach((set, d) => {
      if (!set.size) return;
      const ps = [...set].sort((a, b) => a - b);
      let gap = 0;
      for (let p = ps[0]; p <= ps[ps.length - 1]; p++) if (!set.has(p) && !lunch.has(p)) gap++;
      if (gap) gaps.push({ group: g, day: d, gap });
      if (ps.length === 1) lonely.push({ group: g, day: d, period: ps[0] });
    });
  return { teaching, roomUse, load, gaps: gaps.sort((a, b) => b.gap - a.gap), lonely };
}

export function suggestions(inst: Instance, s: Solution): string[] {
  const { teaching, roomUse, load, gaps, lonely } = analyse(inst, s);
  const name = (id: string) => [...inst.groups, ...inst.faculty, ...inst.rooms].find((x) => x.id === id)?.name ?? id;
  const out: string[] = [];
  for (const r of inst.rooms) {
    const used = roomUse[r.id] ?? 0;
    if (used === 0) out.push(`${r.name} is not used at all. It could be released for other departments or events.`);
    else if (used / teaching < 0.15) out.push(`${r.name} is used only ${used} of ${teaching} teaching periods a week; it could be shared.`);
  }
  for (const f of inst.faculty) {
    if (load[f.id] >= f.maxWeekly) out.push(`${f.name} teaches ${load[f.id]} of a maximum ${f.maxWeekly} periods: no spare capacity for cover.`);
    else if (load[f.id] === 0) out.push(`${f.name} has no classes in this timetable; a good substitute when someone is absent.`);
  }
  for (const g of gaps.slice(0, 2))
    out.push(`${name(g.group)} has ${g.gap} idle period${g.gap > 1 ? 's' : ''} on ${inst.grid.days[g.day]}; consider a tutorial or library slot there.`);
  for (const l of lonely.slice(0, 2))
    out.push(`${name(l.group)} comes in on ${inst.grid.days[l.day]} for a single class (${inst.grid.periods[l.period]}).`);
  if (!out.length) out.push('No issues found: rooms are well used, no teacher is at their limit and classes have compact days.');
  return out.slice(0, 6);
}

