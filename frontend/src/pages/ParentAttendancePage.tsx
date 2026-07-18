import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Navigate, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { AttendanceStatus, ParentChild, ParentChildAttendanceEntry } from "../api/types";
import { AttendancePeriodPicker } from "../components/AttendancePeriodPicker";
import { ClubLogo } from "../components/ClubLogo";
import { ADMIN_CHART_COLORS, AdminDonutChart } from "../components/AdminCharts";
import { useParent } from "../context/ParentContext";
import { STATUS_LABELS } from "../lib/attendance";
import { defaultPeriodState, formatPeriodLabel, resolvePeriodRange } from "../lib/attendancePeriod";
import type { PeriodState } from "../lib/attendancePeriod";
import "../pages/AdminPage.css";

const WEEKDAYS_CS = ["ne", "po", "út", "st", "čt", "pá", "so"] as const;

function formatSessionWhen(iso: string): string {
  const d = new Date(iso);
  const weekday = WEEKDAYS_CS[d.getDay()];
  const day = d.getDate();
  const month = d.getMonth() + 1;
  const time = d.toLocaleTimeString("cs-CZ", { hour: "2-digit", minute: "2-digit" });
  return `${weekday} ${day}. ${month}. ${time}`;
}

function childBranchesLabel(child: ParentChild): string {
  return child.branches.map((b) => b.name).join(", ") || "—";
}

function childHeadline(child: ParentChild): string {
  return `${child.first_name} ${child.last_name}`;
}

function statusChipClass(status: AttendanceStatus | null): string {
  if (status === "present") return "parent-attendance__chip parent-attendance__chip--present";
  if (status === "absent") return "parent-attendance__chip parent-attendance__chip--absent";
  if (status === "excused") return "parent-attendance__chip parent-attendance__chip--excused";
  return "parent-attendance__chip parent-attendance__chip--missing";
}

function statusLabel(status: AttendanceStatus | null): string {
  return status ? STATUS_LABELS[status] : "Neoznačeno";
}

function SessionRow({ entry }: { entry: ParentChildAttendanceEntry }) {
  return (
    <li className="parent-attendance__session">
      <div className="parent-attendance__session-main">
        <span className="parent-attendance__session-when">{formatSessionWhen(entry.starts_at)}</span>
        <span className="parent-attendance__session-group">
          {entry.group_name}
          {entry.is_guest && <span className="attendance-guest-badge">Host</span>}
        </span>
      </div>
      <span className={statusChipClass(entry.status)}>{statusLabel(entry.status)}</span>
    </li>
  );
}

export function ParentAttendancePage() {
  const navigate = useNavigate();
  const { parent, isAuthenticated, isLoading } = useParent();
  const [period, setPeriod] = useState<PeriodState>(() => defaultPeriodState());
  const [childId, setChildId] = useState<number | null>(null);
  const range = useMemo(() => resolvePeriodRange(period), [period]);

  const children = parent?.children ?? [];

  useEffect(() => {
    if (children.length === 0) {
      setChildId(null);
      return;
    }
    if (childId != null && children.some((c) => c.id === childId)) return;
    setChildId(children[0].id);
  }, [children, childId]);

  const selectedChild = useMemo(
    () => children.find((c) => c.id === childId) ?? null,
    [children, childId],
  );

  const reportQuery = useQuery({
    queryKey: ["parent-child-attendance", childId, range?.dateFrom, range?.dateTo],
    queryFn: () => api.parentChildAttendance(childId as number, range!.dateFrom, range!.dateTo),
    enabled: childId != null && range != null,
  });

  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  if (isLoading || !parent) {
    return (
      <div className="boot-screen">
        <ClubLogo variant="splash" />
        <p className="page-header__sub">Načítám profil…</p>
      </div>
    );
  }

  const report = reportQuery.data;
  const donutItems = report
    ? [
        { label: "Přítomen", value: report.present, color: ADMIN_CHART_COLORS.present },
        { label: "Nepřítomen", value: report.absent, color: ADMIN_CHART_COLORS.absent },
        { label: "Omluven", value: report.excused, color: ADMIN_CHART_COLORS.accent },
        { label: "Neoznačeno", value: report.unmarked, color: ADMIN_CHART_COLORS.muted },
      ].filter((item) => item.value > 0)
    : [];

  return (
    <div className="boot-screen app-shell parent-attendance-page">
      <div className="hub-card parent-attendance-card">
        <header className="trainer-picker__header">
          <ClubLogo variant="header" />
          <p className="page-header__eyebrow">Rodič</p>
          <h1 className="trainer-picker__title">Přehled docházky dítěte</h1>
          {selectedChild ? (
            <div className="parent-attendance__child-head">
              <p className="trainer-picker__sub parent-attendance__child-name">
                {childHeadline(selectedChild)}
              </p>
              <p className="parent-attendance__child-meta">
                <span className="parent-child__age">{selectedChild.age_group}</span>
                <span className="parent-child__branch">{childBranchesLabel(selectedChild)}</span>
              </p>
            </div>
          ) : (
            <p className="trainer-picker__sub">Vyberte dítě a období</p>
          )}
        </header>

        {children.length === 0 ? (
          <div className="parent-attendance__empty">
            <p>Zatím nemáš přiřazené žádné dítě.</p>
            <button type="button" className="btn btn--primary" onClick={() => navigate("/register")}>
              Registrovat dítě
            </button>
          </div>
        ) : (
          <>
            <div className="parent-attendance__controls">
              {children.length > 1 && (
                <label className="notification-field">
                  Dítě
                  <select
                    value={childId ?? ""}
                    onChange={(e) => setChildId(Number(e.target.value))}
                  >
                    {children.map((child) => (
                      <option key={child.id} value={child.id}>
                        {child.first_name} {child.last_name} · {child.age_group} ·{" "}
                        {childBranchesLabel(child)}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <AttendancePeriodPicker value={period} onChange={setPeriod} />
            </div>

            <p className="parent-attendance__month-label">{formatPeriodLabel(period)}</p>

            {reportQuery.isLoading && <p className="page-header__sub">Načítám docházku…</p>}
            {reportQuery.isError && <p className="error-box">{String(reportQuery.error)}</p>}

            {report && (
              <>
                <div className="parent-attendance__kpis">
                  <div className="parent-attendance__kpi">
                    <span className="parent-attendance__kpi-value">{report.sessions}</span>
                    <span className="parent-attendance__kpi-label">Tréninků</span>
                  </div>
                  <div className="parent-attendance__kpi parent-attendance__kpi--present">
                    <span className="parent-attendance__kpi-value">{report.present}</span>
                    <span className="parent-attendance__kpi-label">Přítomen</span>
                  </div>
                  <div className="parent-attendance__kpi parent-attendance__kpi--absent">
                    <span className="parent-attendance__kpi-value">{report.absent}</span>
                    <span className="parent-attendance__kpi-label">Nepřítomen</span>
                  </div>
                  <div className="parent-attendance__kpi parent-attendance__kpi--excused">
                    <span className="parent-attendance__kpi-value">{report.excused}</span>
                    <span className="parent-attendance__kpi-label">Omluven</span>
                  </div>
                  <div className="parent-attendance__kpi">
                    <span className="parent-attendance__kpi-value">{report.unmarked}</span>
                    <span className="parent-attendance__kpi-label">Neoznačeno</span>
                  </div>
                  <div className="parent-attendance__kpi parent-attendance__kpi--rate">
                    <span className="parent-attendance__kpi-value">
                      {report.sessions > 0 ? `${report.attendance_rate}%` : "—"}
                    </span>
                    <span className="parent-attendance__kpi-label">Docházka</span>
                  </div>
                </div>

                {report.sessions === 0 ? (
                  <p className="parent-attendance__empty-month">
                    V tomto období zatím nejsou žádné tréninky s docházkou pro toto dítě.
                  </p>
                ) : (
                  <>
                    {donutItems.length > 0 && (
                      <div className="parent-attendance__charts">
                        <AdminDonutChart
                          title="Poměr docházky"
                          items={donutItems}
                          centerLabel="záznamů"
                        />
                      </div>
                    )}

                    <section className="parent-attendance__list-section">
                      <h2 className="parent-attendance__list-title">Tréninky v období</h2>
                      <ul className="parent-attendance__sessions">
                        {report.entries.map((entry) => (
                          <SessionRow key={entry.session_id} entry={entry} />
                        ))}
                      </ul>
                    </section>
                  </>
                )}
              </>
            )}
          </>
        )}

        <button type="button" className="btn btn--ghost auth-back" onClick={() => navigate("/parent")}>
          Zpět do menu
        </button>
      </div>
    </div>
  );
}
