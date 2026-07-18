import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { AttendanceMonthlyReport, TrainingGroup } from "../api/types";
import { defaultPeriodState, resolvePeriodRange } from "../lib/attendancePeriod";
import type { PeriodState } from "../lib/attendancePeriod";
import { AttendancePeriodPicker } from "./AttendancePeriodPicker";
import { AttendanceReportCharts } from "./AttendanceReportCharts";

type ReportRole = "trainer" | "admin";

const ALL_BRANCH_GROUPS = 0;

/** Skupiny viditelné v kalendáři: mají dny v týdnu a platí ve vybraném intervalu. */
function calendarGroupsForRange(
  groups: TrainingGroup[],
  dateFrom: string,
  dateTo: string,
): TrainingGroup[] {
  return groups.filter((g) => {
    if (!g.weekdays?.length) return false;
    if (g.active_from && g.active_from > dateTo) return false;
    if (g.active_until && g.active_until < dateFrom) return false;
    return true;
  });
}

function AttendanceReportBody({ report, branchMode }: { report: AttendanceMonthlyReport; branchMode?: boolean }) {
  const meta = branchMode
    ? `Tréninků v období: ${report.sessions} · Skupin: ${report.group_count ?? 0}`
    : `Tréninků v období: ${report.sessions}`;

  return (
    <div className="attendance-report">
      <p className="attendance-report__meta">{meta}</p>
      <AttendanceReportCharts report={report} />
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
          {report.rows.map((row) => (
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
  );
}

export function MonthlyAttendanceReport({ role = "trainer" }: { role?: ReportRole }) {
  const isAdmin = role === "admin";
  const [branchId, setBranchId] = useState<number | null>(null);
  const [groupId, setGroupId] = useState<number | null>(null);
  const [period, setPeriod] = useState<PeriodState>(() => defaultPeriodState());
  const range = useMemo(() => resolvePeriodRange(period), [period]);

  const branchesQuery = useQuery({
    queryKey: ["branches"],
    queryFn: () => api.branches(),
    enabled: isAdmin,
  });

  const groupsQuery = useQuery({
    queryKey: ["training-groups-all", role],
    queryFn: () => api.trainingGroups(undefined, role),
  });

  const allGroups = useMemo(() => {
    if (!range) return [];
    return calendarGroupsForRange(groupsQuery.data ?? [], range.dateFrom, range.dateTo);
  }, [groupsQuery.data, range]);

  const groups = useMemo(() => {
    if (!isAdmin || branchId == null) return allGroups;
    return allGroups.filter((g) => g.branch_id === branchId);
  }, [allGroups, branchId, isAdmin]);

  const effectiveBranchId =
    isAdmin && branchId != null && branchesQuery.data?.some((b) => b.id === branchId) ? branchId : null;

  const branchWide =
    isAdmin && effectiveBranchId != null && (groupId == null || groupId === ALL_BRANCH_GROUPS);

  const effectiveGroupId =
    !branchWide && groupId != null && groupId !== ALL_BRANCH_GROUPS && groups.some((g) => g.id === groupId)
      ? groupId
      : null;

  const groupReportQuery = useQuery({
    queryKey: ["attendance-report", "group", effectiveGroupId, range?.dateFrom, range?.dateTo, role],
    queryFn: () =>
      api.attendanceReport(effectiveGroupId as number, range!.dateFrom, range!.dateTo, role),
    enabled: effectiveGroupId != null && range != null,
  });

  const branchReportQuery = useQuery({
    queryKey: ["attendance-report", "branch", effectiveBranchId, range?.dateFrom, range?.dateTo],
    queryFn: () =>
      api.adminBranchAttendanceReport(effectiveBranchId as number, range!.dateFrom, range!.dateTo),
    enabled: branchWide && range != null,
  });

  const reportQuery = branchWide ? branchReportQuery : groupReportQuery;

  const onBranchChange = (value: string) => {
    const next = value ? Number(value) : null;
    setBranchId(next);
    setGroupId(next == null ? null : ALL_BRANCH_GROUPS);
  };

  const onGroupChange = (value: string) => {
    setGroupId(value ? Number(value) : isAdmin && branchId != null ? ALL_BRANCH_GROUPS : null);
  };

  const needsSelection = !branchWide && effectiveGroupId == null;

  return (
    <section className="notification-compose">
      <h2>Docházka</h2>
      <div className="events-compose__row">
        {isAdmin && (
          <label className="notification-field">
            Pobočka
            <select value={effectiveBranchId ?? ""} onChange={(e) => onBranchChange(e.target.value)}>
              <option value="">Vyber pobočku…</option>
              {(branchesQuery.data ?? []).map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <label className="notification-field">
          Trénink
          <select
            value={branchWide ? String(ALL_BRANCH_GROUPS) : (effectiveGroupId ?? "")}
            onChange={(e) => onGroupChange(e.target.value)}
          >
            {isAdmin && effectiveBranchId != null && (
              <option value={ALL_BRANCH_GROUPS}>Všechny skupiny na pobočce</option>
            )}
            {!isAdmin && <option value="">Vyber trénink…</option>}
            {isAdmin && effectiveBranchId == null && <option value="">Vyber trénink…</option>}
            {groups.map((g) => (
              <option key={g.id} value={g.id}>
                {isAdmin
                  ? `${g.name} · ${g.start_time.slice(0, 5)}–${g.end_time.slice(0, 5)}`
                  : `${g.name} · ${g.branch.name} · ${g.start_time.slice(0, 5)}–${g.end_time.slice(0, 5)}`}
              </option>
            ))}
          </select>
        </label>
      </div>
      <AttendancePeriodPicker value={period} onChange={setPeriod} />
      {groupsQuery.isLoading && <p className="notification-compose__missing">Načítám tréninky…</p>}
      {!groupsQuery.isLoading && allGroups.length === 0 && (
        <p className="notification-compose__missing">
          V kalendáři není žádný opakovaný trénink pro toto období. Založ ho v plánovači (+ Trénink).
        </p>
      )}
      {isAdmin && needsSelection && allGroups.length > 0 && (
        <p className="notification-compose__missing">
          Vyber pobočku (všechny skupiny) nebo konkrétní trénink.
        </p>
      )}
      {!isAdmin && needsSelection && allGroups.length > 0 && (
        <p className="notification-compose__missing">Vyber trénink pro zobrazení docházky.</p>
      )}
      {isAdmin && effectiveBranchId != null && groups.length === 0 && !groupsQuery.isLoading && (
        <p className="notification-compose__missing">Na této pobočce není v období žádný kalendářní trénink.</p>
      )}
      {reportQuery.isLoading && !needsSelection && <div className="loading">Načítám…</div>}
      {reportQuery.isError && <div className="error-box">{String(reportQuery.error)}</div>}
      {reportQuery.data && <AttendanceReportBody report={reportQuery.data} branchMode={branchWide} />}
    </section>
  );
}
