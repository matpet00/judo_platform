import { useMemo } from "react";
import type { AttendanceMonthlyReport } from "../api/types";
import { ADMIN_CHART_COLORS, AdminBarChart, AdminDonutChart } from "./AdminCharts";

export function AttendanceReportCharts({ report }: { report: AttendanceMonthlyReport }) {
  const statusTotals = useMemo(() => {
    let present = 0;
    let absent = 0;
    let excused = 0;
    for (const row of report.rows) {
      present += row.present;
      absent += row.absent;
      excused += row.excused;
    }
    return { present, absent, excused };
  }, [report.rows]);

  const attendanceRateBars = useMemo(
    () =>
      [...report.rows]
        .sort((a, b) => {
          const rateA = a.sessions > 0 ? a.present / a.sessions : 0;
          const rateB = b.sessions > 0 ? b.present / b.sessions : 0;
          return rateB - rateA;
        })
        .map((row) => {
          const rate = row.sessions > 0 ? Math.round((row.present / row.sessions) * 100) : 0;
          return {
            label: row.is_guest ? `${row.name} (host)` : row.name,
            value: rate,
            color: row.is_guest ? ADMIN_CHART_COLORS.gold : ADMIN_CHART_COLORS.present,
          };
        }),
    [report.rows],
  );

  const presentCountBars = useMemo(
    () =>
      [...report.rows]
        .sort((a, b) => b.present - a.present)
        .map((row) => ({
          label: row.is_guest ? `${row.name} (host)` : row.name,
          value: row.present,
          color: row.is_guest ? ADMIN_CHART_COLORS.gold : ADMIN_CHART_COLORS.accent,
        })),
    [report.rows],
  );

  const statusSegments = [
    { label: "Přítomen", value: statusTotals.present, color: ADMIN_CHART_COLORS.present },
    { label: "Nepřítomen", value: statusTotals.absent, color: ADMIN_CHART_COLORS.absent },
    { label: "Omluven", value: statusTotals.excused, color: ADMIN_CHART_COLORS.accent },
  ].filter((s) => s.value > 0);

  if (report.rows.length === 0) {
    return <p className="admin-empty">Žádná data docházky pro zobrazení grafů.</p>;
  }

  return (
    <div className="admin-charts-grid attendance-report__charts">
      {statusSegments.length > 0 && (
        <AdminDonutChart
          title="Celkový poměr docházky"
          items={statusSegments}
          centerLabel="záznamů"
        />
      )}
      <AdminBarChart title="Přítomnost podle dítěte (%)" items={attendanceRateBars} />
      <AdminBarChart title="Počet přítomností v měsíci" items={presentCountBars} />
    </div>
  );
}
