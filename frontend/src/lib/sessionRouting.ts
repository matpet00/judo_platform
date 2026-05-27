import type { TrainingGroup, TrainingSessionSummary } from "../api/types";

export const WINDOW_BEFORE_MIN = 45;

/** Local calendar date YYYY-MM-DD */
export function todayIso(now = new Date()): string {
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function parseTimeOnDate(timeStr: string, base: Date): Date {
  const [h, m, s] = timeStr.split(":").map(Number);
  const d = new Date(base);
  d.setHours(h, m, s || 0, 0);
  return d;
}

export function isGroupActiveNow(group: TrainingGroup, now = new Date()): boolean {
  const start = parseTimeOnDate(group.start_time, now);
  const end = parseTimeOnDate(group.end_time, now);
  const windowStart = new Date(start.getTime() - WINDOW_BEFORE_MIN * 60_000);
  return now >= windowStart && now <= end;
}

export function minutesUntilStart(group: TrainingGroup, now = new Date()): number {
  const start = parseTimeOnDate(group.start_time, now);
  return (start.getTime() - now.getTime()) / 60_000;
}

export function pickNearestActiveGroup(groups: TrainingGroup[], now = new Date()): TrainingGroup | null {
  const active = groups.filter((g) => isGroupActiveNow(g, now));
  if (active.length === 0) return null;
  if (active.length === 1) return active[0];
  return active.sort((a, b) => Math.abs(minutesUntilStart(a, now)) - Math.abs(minutesUntilStart(b, now)))[0];
}

export function sessionForGroup(
  sessions: TrainingSessionSummary[],
  groupId: number,
): TrainingSessionSummary | undefined {
  return sessions.find((s) => s.training_group_id === groupId);
}

export function groupsWithoutSession(
  groups: TrainingGroup[],
  sessions: TrainingSessionSummary[],
): TrainingGroup[] {
  const withSession = new Set(sessions.map((s) => s.training_group_id));
  return groups.filter((g) => !withSession.has(g.id));
}

export type BootDecision =
  | { type: "open-session"; sessionId: number; group: TrainingGroup }
  | { type: "create-session"; group: TrainingGroup }
  | { type: "today" };

export function resolveBootDecision(
  groups: TrainingGroup[],
  sessions: TrainingSessionSummary[],
  now = new Date(),
): BootDecision {
  const nearest = pickNearestActiveGroup(groups, now);
  if (!nearest) {
    return { type: "today" };
  }
  const existing = sessionForGroup(sessions, nearest.id);
  if (existing) {
    return { type: "open-session", sessionId: existing.id, group: nearest };
  }
  return { type: "create-session", group: nearest };
}

export function formatTime(t: string): string {
  return t.slice(0, 5);
}

export function formatTodayLong(now = new Date()): string {
  return now.toLocaleDateString("cs-CZ", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

export function countMarked(students: { attendance: unknown | null }[]): { marked: number; total: number } {
  const total = students.length;
  const marked = students.filter((s) => s.attendance !== null).length;
  return { marked, total };
}
