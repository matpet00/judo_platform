import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

export function MonthlyAttendanceReport() {
  const [groupId, setGroupId] = useState<number | null>(null);
  const [month, setMonth] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  });

  const groupsQuery = useQuery({ queryKey: ["training-groups-all"], queryFn: () => api.trainingGroups() });
  const groups = groupsQuery.data ?? [];

  const reportQuery = useQuery({
    queryKey: ["attendance-report", groupId, month],
    queryFn: () => api.attendanceReport(groupId as number, month),
    enabled: groupId != null && /^\d{4}-\d{2}$/.test(month),
  });

  return (
    <section className="notification-compose">
      <h2>Měsíční docházka</h2>
      <div className="events-compose__row">
        <label className="notification-field">
          Trénink
          <select value={groupId ?? ""} onChange={(e) => setGroupId(e.target.value ? Number(e.target.value) : null)}>
            <option value="">Vyber trénink…</option>
            {groups.map((g) => (
              <option key={g.id} value={g.id}>{g.name} · {g.branch.name}</option>
            ))}
          </select>
        </label>
        <label className="notification-field">
          Měsíc
          <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} />
        </label>
      </div>
      {groupId == null && <p className="notification-compose__missing">Vyber trénink pro zobrazení docházky.</p>}
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
