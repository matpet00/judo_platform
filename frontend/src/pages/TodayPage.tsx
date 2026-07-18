import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { api, todayIso } from "../api/client";
import type { TrainingOccurrence } from "../api/types";
import { TrainerSwitcher } from "../components/TrainerSwitcher";
import { OfflineBanner } from "../components/OfflineBanner";
import { useTrainer } from "../context/TrainerContext";
import { formatTodayLong } from "../lib/sessionRouting";
import { SessionPickerCard } from "../components/SessionPickerCard";
import { MonthlyAttendanceReport } from "../components/MonthlyAttendanceReport";
import "../components/StudentSwipeDeck.css";

const LOOKAHEAD_DAYS = 21;
const LOOKBEHIND_DAYS = 21;
const MAX_UPCOMING_DAYS = 3;
const MAX_PAST_DAYS = 3;

function occTime(occ: TrainingOccurrence): string {
  return `${occ.start_time.slice(0, 5)} – ${occ.end_time.slice(0, 5)}`;
}

function guestPlural(count: number): string {
  if (count === 1) return "host";
  if (count >= 2 && count <= 4) return "hosté";
  return "hostů";
}

function rosterLabel(occ: TrainingOccurrence): string {
  const base = `${occ.roster_count} žáků`;
  if (occ.guest_count > 0) return `${base} + ${occ.guest_count} ${guestPlural(occ.guest_count)}`;
  return base;
}

function isActiveNow(occ: TrainingOccurrence, now = new Date()): boolean {
  const [sh, sm] = occ.start_time.split(":").map(Number);
  const [eh, em] = occ.end_time.split(":").map(Number);
  const start = new Date(now);
  start.setHours(sh, sm - 45, 0, 0);
  const end = new Date(now);
  end.setHours(eh, em, 0, 0);
  return now >= start && now <= end;
}

function formatDayHeading(dateStr: string): string {
  const [y, m, d] = dateStr.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("cs-CZ", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

export function TodayPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { trainer, isAuthenticated, isLoading: trainersLoading } = useTrainer();
  const [tab, setTab] = useState<"trainings" | "monthly">("trainings");

  const today = todayIso();
  const from = useMemo(() => {
    const d = new Date();
    d.setDate(d.getDate() - LOOKBEHIND_DAYS);
    return todayIso(d);
  }, []);
  const to = useMemo(() => {
    const d = new Date();
    d.setDate(d.getDate() + LOOKAHEAD_DAYS);
    return todayIso(d);
  }, []);

  const occurrencesQuery = useQuery({
    queryKey: ["occurrences", "trainer", from, to],
    queryFn: () => api.trainingOccurrences(from, to, "trainer"),
    enabled: isAuthenticated,
    refetchInterval: 60_000,
  });

  const occurrences = occurrencesQuery.data ?? [];
  const todayOccurrences = useMemo(
    () =>
      occurrences
        .filter((o) => o.date === today && !o.canceled)
        .sort((a, b) => a.start_time.localeCompare(b.start_time)),
    [occurrences, today],
  );

  const groupByDate = (predicate: (o: TrainingOccurrence) => boolean, descending: boolean, limit: number) => {
    const map = new Map<string, TrainingOccurrence[]>();
    for (const o of occurrences) {
      if (o.canceled || !predicate(o)) continue;
      const list = map.get(o.date) ?? [];
      list.push(o);
      map.set(o.date, list);
    }
    return [...map.entries()]
      .sort((a, b) => (descending ? b[0].localeCompare(a[0]) : a[0].localeCompare(b[0])))
      .slice(0, limit)
      .map(([date, occs]) => ({
        date,
        occs: occs.sort((a, b) => a.start_time.localeCompare(b.start_time)),
      }));
  };

  const recentByDate = useMemo(
    () => groupByDate((o) => o.date < today, true, MAX_PAST_DAYS),
    [occurrences, today],
  );
  const upcomingByDate = useMemo(
    () => groupByDate((o) => o.date > today, false, MAX_UPCOMING_DAYS),
    [occurrences, today],
  );

  const openOrCreate = useMutation({
    mutationFn: async ({ groupId, date }: { groupId: number; date: string }) => {
      if (!trainer) throw new Error("Vyber trenéra");
      return api.openGroupSession(groupId, date, trainer.id);
    },
    onSuccess: (session) => {
      queryClient.invalidateQueries({ queryKey: ["training-sessions"] });
      queryClient.invalidateQueries({ queryKey: ["occurrences"] });
      navigate(`/session/${session.id}`);
    },
  });

  const openOccurrence = (occ: TrainingOccurrence) => {
    if (occ.session_id != null) {
      navigate(`/session/${occ.session_id}`);
      return;
    }
    openOrCreate.mutate({ groupId: occ.group_id, date: occ.date });
  };

  useEffect(() => {
    if (!trainersLoading && !isAuthenticated) {
      navigate("/", { replace: true });
    }
  }, [isAuthenticated, trainersLoading, navigate]);

  if (!isAuthenticated || !trainer) {
    return <div className="loading app-shell">Načítám…</div>;
  }

  return (
    <div className="app-shell">
      <header className="page-header">
        <div className="page-header__row">
          <div>
            <p className="page-header__eyebrow">Dnes</p>
            <h1 className="page-header__title">{formatTodayLong()}</h1>
            <p className="page-header__sub">Docházka na trénink</p>
          </div>
          <Link className="board-link" to="/">Menu</Link>
        </div>
      </header>

      <TrainerSwitcher variant="bar" />
      <OfflineBanner />

      <div className="events-view-toggle attendance-tabs">
        <button type="button" className={tab === "trainings" ? "is-active" : ""} onClick={() => setTab("trainings")}>
          Dnešní a blízké
        </button>
        <button type="button" className={tab === "monthly" ? "is-active" : ""} onClick={() => setTab("monthly")}>
          Přehled docházky
        </button>
      </div>

      {tab === "monthly" && <MonthlyAttendanceReport />}

      {tab === "trainings" && occurrencesQuery.isLoading && <div className="loading">Načítám…</div>}
      {tab === "trainings" && occurrencesQuery.isError && (
        <div className="error-box">
          API nedostupné.
          <br />
          <small>{String(occurrencesQuery.error)}</small>
        </div>
      )}

      {tab === "trainings" && !occurrencesQuery.isLoading && !occurrencesQuery.isError && (
        <>
          {todayOccurrences.length > 0 ? (
            <section className="section-block" style={{ animationDelay: "0.05s" }}>
              <h2 className="section-block__title">Dnešní tréninky</h2>
              <div className="section-block__list">
                {todayOccurrences.map((occ) => (
                  <SessionPickerCard
                    key={`${occ.group_id}-${occ.date}`}
                    title={occ.name}
                    subtitle={occ.guest_count > 0 ? `${occTime(occ)} · ${rosterLabel(occ)}` : occTime(occ)}
                    marked={occ.marked_count}
                    total={occ.roster_count + occ.guest_count}
                    highlight={isActiveNow(occ)}
                    pending={openOrCreate.isPending}
                    onClick={() => openOccurrence(occ)}
                  />
                ))}
              </div>
            </section>
          ) : (
            <section className="section-block" style={{ animationDelay: "0.05s" }}>
              <div className="today-empty">Dnes není naplánovaný žádný trénink.</div>
            </section>
          )}

          {todayOccurrences.length === 0 && recentByDate.length > 0 && (
            <section className="section-block" style={{ animationDelay: "0.1s" }}>
              <h2 className="section-block__title">Nedávné tréninky</h2>
              <p className="section-block__hint">Můžeš zpětně doplnit docházku.</p>
              {recentByDate.map((group) => (
                <div key={group.date} className="today-upcoming-day">
                  <h3 className="today-upcoming-day__heading">{formatDayHeading(group.date)}</h3>
                  <div className="section-block__list">
                    {group.occs.map((occ) => (
                      <SessionPickerCard
                        key={`${occ.group_id}-${occ.date}`}
                        title={occ.name}
                        subtitle={`${occTime(occ)} · ${rosterLabel(occ)}`}
                        marked={occ.session_id != null ? occ.marked_count : undefined}
                        total={occ.session_id != null ? occ.roster_count + occ.guest_count : undefined}
                        pending={openOrCreate.isPending}
                        onClick={() => openOccurrence(occ)}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </section>
          )}

          {todayOccurrences.length === 0 && upcomingByDate.length > 0 && (
            <section className="section-block" style={{ animationDelay: "0.15s" }}>
              <h2 className="section-block__title">Nejbližší tréninky</h2>
              {upcomingByDate.map((group) => (
                <div key={group.date} className="today-upcoming-day">
                  <h3 className="today-upcoming-day__heading">{formatDayHeading(group.date)}</h3>
                  <div className="section-block__list">
                    {group.occs.map((occ) => (
                      <SessionPickerCard
                        key={`${occ.group_id}-${occ.date}`}
                        title={occ.name}
                        subtitle={`${occTime(occ)} · ${rosterLabel(occ)}`}
                        pending={openOrCreate.isPending}
                        onClick={() => openOccurrence(occ)}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </section>
          )}

          {occurrences.length === 0 && (
            <div className="loading">Žádné naplánované tréninky. Vytvoř je v kalendáři.</div>
          )}
        </>
      )}

      {openOrCreate.isError && <div className="toast">{String(openOrCreate.error)}</div>}
    </div>
  );
}
