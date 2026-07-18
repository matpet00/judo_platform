import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Navigate, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { AttendanceStatus, TrainerPayAttendanceEntry } from "../api/types";
import { AttendancePeriodPicker } from "../components/AttendancePeriodPicker";
import { ClubLogo } from "../components/ClubLogo";
import { PaySourceFilterCheckboxes } from "../components/PaySourceFilterCheckboxes";
import { trainerRoleLabel } from "../components/TrainerPicker";
import { useTrainer } from "../context/TrainerContext";
import { STATUS_LABELS } from "../lib/attendance";
import {
  defaultPeriodState,
  formatPeriodLabel,
  resolvePeriodRange,
} from "../lib/attendancePeriod";
import type { PeriodState } from "../lib/attendancePeriod";
import { defaultPaySourceFilter, EVENT_TYPE_PAY_LABELS } from "../lib/paySourceFilter";
import type { PaySourceFilter } from "../lib/paySourceFilter";
import type { EventType } from "../api/types";
import "../pages/AdminPage.css";

const WEEKDAYS_CS = ["ne", "po", "út", "st", "čt", "pá", "so"] as const;

function formatSessionWhen(entry: TrainerPayAttendanceEntry): string {
  if (entry.starts_at) {
    const d = new Date(entry.starts_at);
    const weekday = WEEKDAYS_CS[d.getDay()];
    const day = d.getDate();
    const month = d.getMonth() + 1;
    const time = d.toLocaleTimeString("cs-CZ", { hour: "2-digit", minute: "2-digit" });
    return `${weekday} ${day}. ${month}. ${time}`;
  }
  if (entry.session_date) {
    const time = entry.start_time ? entry.start_time.slice(0, 5) : "";
    return `${entry.session_date}${time ? ` ${time}` : ""}`;
  }
  return "—";
}

function statusChipClass(status: AttendanceStatus): string {
  if (status === "present") return "parent-attendance__chip parent-attendance__chip--present";
  if (status === "absent") return "parent-attendance__chip parent-attendance__chip--absent";
  return "parent-attendance__chip parent-attendance__chip--excused";
}

function entryKindLabel(entry: TrainerPayAttendanceEntry): string {
  if (entry.source === "training") return "Trénink";
  const type = entry.event_type as EventType | null;
  if (type && type in EVENT_TYPE_PAY_LABELS) return EVENT_TYPE_PAY_LABELS[type];
  return "Akce";
}

export function TrainerPayAttendancePage() {
  const navigate = useNavigate();
  const { trainer, isAuthenticated, isLoading } = useTrainer();
  const [period, setPeriod] = useState<PeriodState>(() => defaultPeriodState());
  const [sources, setSources] = useState<PaySourceFilter>(() => defaultPaySourceFilter());
  const range = useMemo(() => resolvePeriodRange(period), [period]);

  const reportQuery = useQuery({
    queryKey: [
      "trainer-pay-attendance",
      trainer?.id,
      range?.dateFrom,
      range?.dateTo,
      sources.includeTrainings,
      sources.eventTypes.join(","),
    ],
    queryFn: () =>
      api.trainerPayAttendance(range!.dateFrom, range!.dateTo, {
        includeTrainings: sources.includeTrainings,
        eventTypes: sources.eventTypes,
      }),
    enabled: isAuthenticated && !!trainer && range != null,
  });

  const download = useMutation({
    mutationFn: () =>
      api.downloadTrainerPayAttendanceCsv(range!.dateFrom, range!.dateTo, {
        includeTrainings: sources.includeTrainings,
        eventTypes: sources.eventTypes,
      }),
  });

  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  if (isLoading || !trainer) {
    return (
      <div className="boot-screen">
        <ClubLogo variant="splash" />
        <p className="page-header__sub">Načítám…</p>
      </div>
    );
  }

  const report = reportQuery.data;

  return (
    <div className="boot-screen app-shell parent-attendance-page">
      <div className="hub-card parent-attendance-card">
        <header className="trainer-picker__header">
          <ClubLogo variant="header" />
          <p className="page-header__eyebrow">Trenér</p>
          <h1 className="trainer-picker__title">Docházka k proplacení</h1>
          <p className="trainer-picker__sub">
            {trainerRoleLabel(trainer)} · {formatPeriodLabel(period)}
          </p>
        </header>

        <AttendancePeriodPicker value={period} onChange={setPeriod} />
        <PaySourceFilterCheckboxes value={sources} onChange={setSources} />

        <div className="admin-form__actions" style={{ marginTop: 12 }}>
          <button
            type="button"
            className="btn btn--primary"
            disabled={!range || download.isPending}
            onClick={() => download.mutate()}
          >
            {download.isPending ? "Stahuji…" : "Stáhnout Excel (CSV)"}
          </button>
        </div>
        {download.isError && <p className="error-box">{String(download.error)}</p>}
        <p className="page-header__sub" style={{ marginTop: 8 }}>
          Export obsahuje záznamy k proplacení (přítomen / RSVP ano).
        </p>

        {reportQuery.isLoading && <p className="page-header__sub">Načítám docházku…</p>}
        {reportQuery.isError && <p className="error-box">{String(reportQuery.error)}</p>}

        {report && (
          <>
            <div className="parent-attendance__kpis">
              <div className="parent-attendance__kpi parent-attendance__kpi--rate">
                <span className="parent-attendance__kpi-value">{report.payable_sessions}</span>
                <span className="parent-attendance__kpi-label">K proplacení</span>
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
                <span className="parent-attendance__kpi-label">Omluven / možná</span>
              </div>
            </div>

            {report.entries.length === 0 ? (
              <p className="parent-attendance__empty-month">
                V tomto období a filtru nemáš žádný záznam.
              </p>
            ) : (
              <section className="parent-attendance__list-section">
                <h2 className="parent-attendance__list-title">Záznamy v období</h2>
                <ul className="parent-attendance__sessions">
                  {report.entries.map((entry) => (
                    <li
                      key={`${entry.source}-${entry.session_id ?? entry.event_id}-${entry.trainer_id}`}
                      className="parent-attendance__session"
                    >
                      <div className="parent-attendance__session-main">
                        <span className="parent-attendance__session-when">{formatSessionWhen(entry)}</span>
                        <span className="parent-attendance__session-group">
                          {entryKindLabel(entry)} · {entry.group_name}
                          {entry.branch_name ? ` · ${entry.branch_name}` : ""}
                        </span>
                      </div>
                      <span className={statusChipClass(entry.status)}>{STATUS_LABELS[entry.status]}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </>
        )}

        <button type="button" className="btn btn--ghost auth-back" onClick={() => navigate("/")}>
          Zpět do menu
        </button>
      </div>
    </div>
  );
}
