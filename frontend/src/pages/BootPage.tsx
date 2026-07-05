import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Navigate, useNavigate } from "react-router-dom";
import { api, todayIso } from "../api/client";
import { AuthLanding } from "../components/AuthLanding";
import { TrainerLoginFlow } from "../components/TrainerSwitcher";
import { useParent } from "../context/ParentContext";
import { useTrainer } from "../context/TrainerContext";
import { useTodayAttendance } from "../hooks/useTodayAttendance";
import { formatTime, resolveBootDecision } from "../lib/sessionRouting";
import type { TrainingGroup } from "../api/types";
import "../components/StudentSwipeDeck.css";

export function BootPage() {
  const navigate = useNavigate();
  const {
    trainer,
    isAuthenticated,
    isLoading: trainersLoading,
    isError: trainersError,
    error: trainersLoadError,
  } = useTrainer();
  const { isAuthenticated: parentAuthenticated } = useParent();

  if (!isAuthenticated && parentAuthenticated) {
    return <Navigate to="/parent" replace />;
  }

  if (trainersLoading) {
    return (
      <div className="boot-screen">
        <div className="boot-screen__logo">JUDO</div>
        <p className="page-header__sub">Načítám trenéry…</p>
      </div>
    );
  }

  if (trainersError) {
    return (
      <div className="boot-screen app-shell">
        <div className="error-box">
          API nedostupné. Spusť backend na portu 8001.
          <br />
          <small>{String(trainersLoadError)}</small>
        </div>
      </div>
    );
  }

  if (!isAuthenticated || !trainer) {
    return (
      <div className="boot-screen app-shell">
        <AuthLanding />
      </div>
    );
  }

  return (
    <div className="boot-screen app-shell">
      <div className="hub-card">
        <p className="page-header__eyebrow">Menu</p>
        <h1 className="trainer-picker__title">Kam chceš jít?</h1>
        <p className="trainer-picker__sub">
          {trainer.first_name} {trainer.last_name}
        </p>
        <div className="hub-card__actions">
          <button type="button" className="trainer-card" onClick={() => navigate("/board")}>
            <span className="trainer-card__name">Board</span>
            <span className="trainer-card__branch">Notifications</span>
          </button>
          <button type="button" className="trainer-card" onClick={() => navigate("/attendance")}>
            <span className="trainer-card__name">Docházka</span>
            <span className="trainer-card__branch">Dnešní tréninky</span>
          </button>
          <button type="button" className="trainer-card" onClick={() => navigate("/chat")}>
            <span className="trainer-card__name">Chat</span>
            <span className="trainer-card__branch">Zprávy 1-1</span>
          </button>
        </div>
      </div>
    </div>
  );
}

export function AttendanceBootPage() {
  const navigate = useNavigate();
  const {
    trainer,
    isAuthenticated,
    isLoading: trainersLoading,
    isError: trainersError,
    error: trainersLoadError,
  } = useTrainer();
  const { groups, sessions, isLoading, isError, error } = useTodayAttendance();
  const [confirmGroup, setConfirmGroup] = useState<TrainingGroup | null>(null);
  const [decided, setDecided] = useState(false);

  const createSession = useMutation({
    mutationFn: (groupId: number) => {
      if (!trainer) throw new Error("Vyber trenéra");
      return api.openGroupSession(groupId, todayIso(), trainer.id);
    },
    onSuccess: (session) => {
      navigate(`/session/${session.id}`, { replace: true });
    },
  });

  useEffect(() => {
    if (!isAuthenticated || trainersLoading || trainersError) return;
    if (isLoading || isError || decided || confirmGroup || createSession.isPending) return;
    if (groups.length === 0) {
      navigate("/today", { replace: true });
      return;
    }

    const decision = resolveBootDecision(groups, sessions);
    setDecided(true);

    if (decision.type === "open-session") {
      navigate(`/session/${decision.sessionId}`, { replace: true });
      return;
    }
    if (decision.type === "create-session") {
      setConfirmGroup(decision.group);
      return;
    }
    navigate("/today", { replace: true });
  }, [
    isAuthenticated,
    trainersLoading,
    trainersError,
    groups,
    sessions,
    isLoading,
    isError,
    decided,
    confirmGroup,
    createSession.isPending,
    navigate,
  ]);

  if (trainersLoading) {
    return (
      <div className="boot-screen">
        <div className="boot-screen__logo">JUDO</div>
        <p className="page-header__sub">Načítám trenéry…</p>
      </div>
    );
  }

  if (trainersError) {
    return (
      <div className="boot-screen app-shell">
        <div className="error-box">
          API nedostupné. Spusť backend na portu 8001.
          <br />
          <small>{String(trainersLoadError)}</small>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="boot-screen app-shell">
        <TrainerLoginFlow />
      </div>
    );
  }

  if (confirmGroup && trainer) {
    return (
      <div className="boot-screen app-shell">
        <div className="confirm-card">
          <h2 className="confirm-card__title">Zahájit docházku?</h2>
          <p className="confirm-card__sub">
            {confirmGroup.name}
            <br />
            {formatTime(confirmGroup.start_time)} – {formatTime(confirmGroup.end_time)}
            <br />
            <span className="confirm-card__trainer">
              {trainer.first_name} {trainer.last_name}
            </span>
          </p>
          <div className="confirm-card__actions">
            <button type="button" className="btn btn--ghost" onClick={() => navigate("/today")}>
              Zpět
            </button>
            <button
              type="button"
              className="btn btn--primary"
              disabled={createSession.isPending}
              onClick={() => createSession.mutate(confirmGroup.id)}
            >
              {createSession.isPending ? "Vytvářím…" : "Začít"}
            </button>
          </div>
          {createSession.isError && (
            <p className="error-box" style={{ marginTop: 16 }}>
              {String(createSession.error)}
            </p>
          )}
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="boot-screen app-shell">
        <div className="error-box">
          API nedostupné. Spusť backend na portu 8001.
          <br />
          <small>{String(error)}</small>
        </div>
        <button type="button" className="btn btn--ghost" style={{ marginTop: 16 }} onClick={() => navigate("/today")}>
          Pokračovat
        </button>
      </div>
    );
  }

  return (
    <div className="boot-screen">
      <div className="boot-screen__logo">JUDO</div>
      <p className="page-header__sub">Načítám dnešní trénink…</p>
    </div>
  );
}
