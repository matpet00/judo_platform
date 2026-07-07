import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { TrainingGroup } from "../api/types";

function monthBounds(month: string): { start: string; end: string } | null {
  const match = /^(\d{4})-(\d{2})$/.exec(month);
  if (!match) return null;
  const year = Number(match[1]);
  const mon = Number(match[2]);
  const start = `${month}-01`;
  const lastDay = new Date(year, mon, 0).getDate();
  const end = `${month}-${String(lastDay).padStart(2, "0")}`;
  return { start, end };
}

/** Skupiny viditelné v kalendáři: mají dny v týdnu a platí ve vybraném měsíci. */
function calendarGroupsForMonth(groups: TrainingGroup[], month: string): TrainingGroup[] {
  const bounds = monthBounds(month);
  if (!bounds) return [];

  return groups.filter((g) => {
    if (!g.weekdays?.length) return false;
    if (g.active_from && g.active_from > bounds.end) return false;
    if (g.active_until && g.active_until < bounds.start) return false;
    return true;
  });
}

export function MonthlyAttendanceReport() {
  const [groupId, setGroupId] = useState<number | null>(null);
  const [month, setMonth] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  });

  const groupsQuery = useQuery({ queryKey: ["training-groups-all"], queryFn: () => api.trainingGroups() });
  const groups = useMemo(
    () => calendarGroupsForMonth(groupsQuery.data ?? [], month),
    [groupsQuery.data, month],
  );

  // Vybraná skupina už v daném měsíci neplatí (např. změna měsíce).
  const effectiveGroupId = groupId != null && groups.some((g) => g.id === groupId) ? groupId : null;

  const reportQuery = useQuery({
    queryKey: ["attendance-report", effectiveGroupId, month],
    queryFn: () => api.attendanceReport(effectiveGroupId as number, month),
    enabled: effectiveGroupId != null && /^\d{4}-\d{2}$/.test(month),
  });

  return (
    <section className="notification-compose">
      <h2>Měsíční docházka</h2>
      <div className="events-compose__row">
        <label className="notification-field">
          Trénink
          <select value={effectiveGroupId ?? ""} onChange={(e) => setGroupId(e.target.value ? Number(e.target.value) : null)}>
            <option value="">Vyber trénink…</option>
            {groups.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name} · {g.branch.name} · {g.start_time.slice(0, 5)}–{g.end_time.slice(0, 5)}
              </option>
            ))}
          </select>
        </label>
        <label className="notification-field">
          Měsíc
          <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} />
        </label>
      </div>
      {groupsQuery.isLoading && <p className="notification-compose__missing">Načítám tréninky…</p>}
      {!groupsQuery.isLoading && groups.length === 0 && (
        <p className="notification-compose__missing">
          V kalendáři není žádný opakovaný trénink pro tento měsíc. Založ ho v plánovači (+ Trénink).
        </p>
      )}
      {effectiveGroupId == null && groups.length > 0 && (
        <p className="notification-compose__missing">Vyber trénink pro zobrazení docházky.</p>
      )}
      {reportQuery.isLoading && <div className="loading">Načítám…</div>}
      {reportQuery.isError && <div className="error-box">{String(reportQuery.error)}</div>}
      {reportQuery.data && (
        <div className="attendance-report">
          <p className="attendance-report__meta">Tréninků v měsíci: {reportQuery.data.sessions}</p>
          <table className="attendance-report__table">
            <thead>
              <tr>
                <th>Dítě</th>
                <th>Přítomen</th>
                <th>Nepřítomen</th>
                <th>Omluven</th>
              </tr>
            </thead>
            <tbody>
              {reportQuery.data.rows.map((row) => (
                <tr key={`${row.is_guest ? "guest" : "member"}-${row.student_id}`}>
                  <td>
                    {row.name}
                    {row.is_guest && <span className="attendance-guest-badge">Host</span>}
                  </td>
                  <td>{row.present}</td>
                  <td>{row.absent}</td>
                  <td>{row.excused}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
