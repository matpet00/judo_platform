import { useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { api, todayIso } from "../api/client";
import { TrainerSwitcher } from "../components/TrainerSwitcher";
import { OfflineBanner } from "../components/OfflineBanner";
import { useTrainer } from "../context/TrainerContext";
import { useTodayAttendance } from "../hooks/useTodayAttendance";
import { formatTodayLong } from "../lib/sessionRouting";
import {
  SessionPickerCard,
  existingSessionCardProps,
  groupSlotCardProps,
} from "../components/SessionPickerCard";
import { TodaySessionSummary } from "../components/TodaySessionSummary";
import "../components/StudentSwipeDeck.css";

export function TodayPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { trainer, isAuthenticated, isLoading: trainersLoading } = useTrainer();
  const {
    groups,
    existingSessions,
    activeGroup,
    activeSession,
    slotsWithoutSession,
    isLoading,
    isError,
    error,
  } = useTodayAttendance();

  const openOrCreate = useMutation({
    mutationFn: async (groupId: number) => {
      if (!trainer) throw new Error("Vyber trenéra");
      return api.openGroupSession(groupId, todayIso(), trainer.id);
    },
    onSuccess: (session) => {
      queryClient.invalidateQueries({ queryKey: ["training-sessions"] });
      navigate(`/session/${session.id}`);
    },
  });

  const openSession = (sessionId: number) => navigate(`/session/${sessionId}`);
  const openSessionOverview = (sessionId: number) =>
    navigate(`/session/${sessionId}?view=overview`);

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

      {isLoading && <div className="loading">Načítám…</div>}
      {isError && (
        <div className="error-box">
          API nedostupné.
          <br />
          <small>{String(error)}</small>
        </div>
      )}

      {!isLoading && !isError && (
        <>
          <TodaySessionSummary sessions={existingSessions} onOpenOverview={openSessionOverview} />

          {activeGroup && (
            <section className="section-block" style={{ animationDelay: "0.05s" }}>
              <h2 className="section-block__title">Probíhá teď</h2>
              <div className="section-block__list">
                {activeSession ? (
                  <SessionPickerCard
                    {...existingSessionCardProps(
                      existingSessions.find((s) => s.id === activeSession.id) ?? {
                        ...activeSession,
                        marked: 0,
                        total: activeGroup.students.length,
                        present: 0,
                        absent: 0,
                        excused: 0,
                      },
                    )}
                    highlight
                    onClick={() => openSession(activeSession.id)}
                  />
                ) : (
                  <SessionPickerCard
                    {...groupSlotCardProps(activeGroup)}
                    highlight
                    pending={openOrCreate.isPending}
                    onClick={() => openOrCreate.mutate(activeGroup.id)}
                  />
                )}
              </div>
            </section>
          )}

          {existingSessions.filter((s) => s.id !== activeSession?.id).length > 0 && (
            <section className="section-block" style={{ animationDelay: "0.1s" }}>
              <h2 className="section-block__title">Otevřít docházku</h2>
              <div className="section-block__list">
                {existingSessions
                  .filter((s) => s.id !== activeSession?.id)
                  .map((s) => (
                    <SessionPickerCard
                      key={s.id}
                      {...existingSessionCardProps(s)}
                      onClick={() => openSession(s.id)}
                    />
                  ))}
              </div>
            </section>
          )}

          {slotsWithoutSession.filter((g) => g.id !== activeGroup?.id).length > 0 && (
            <section className="section-block" style={{ animationDelay: "0.15s" }}>
              <h2 className="section-block__title">Zahájit nový trénink</h2>
              <div className="section-block__list">
                {slotsWithoutSession
                  .filter((g) => g.id !== activeGroup?.id)
                  .map((g) => (
                    <SessionPickerCard
                      key={g.id}
                      {...groupSlotCardProps(g)}
                      pending={openOrCreate.isPending}
                      onClick={() => openOrCreate.mutate(g.id)}
                    />
                  ))}
              </div>
            </section>
          )}

          {groups.length === 0 && (
            <div className="loading">Žádné tréninkové skupiny. Vytvoř je v API.</div>
          )}
        </>
      )}

      {openOrCreate.isError && <div className="toast">{String(openOrCreate.error)}</div>}
    </div>
  );
}
