import { useCallback, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { AttendanceOverview } from "../components/AttendanceOverview";
import { OfflineBanner } from "../components/OfflineBanner";
import { TrainerSwitcher } from "../components/TrainerSwitcher";
import { useTrainer } from "../context/TrainerContext";
import type { AttendanceStatus, SessionStudent } from "../api/types";
import { StudentSwipeDeck } from "../components/StudentSwipeDeck";
import { ProgressRing } from "../components/ProgressRing";
import { useOnlineStatus } from "../hooks/useOnlineStatus";
import { countByStatus } from "../lib/attendance";
import { countMarked, formatTime } from "../lib/sessionRouting";
import "../components/StudentSwipeDeck.css";

type SessionView = "deck" | "overview";

function hapticSuccess() {
  navigator.vibrate?.(10);
}

export function SessionSwipePage({ sessionId }: { sessionId: number }) {
  const queryClient = useQueryClient();
  const { trainer, isAuthenticated } = useTrainer();
  const online = useOnlineStatus();
  const [searchParams] = useSearchParams();
  const [students, setStudents] = useState<SessionStudent[]>([]);
  const [view, setView] = useState<SessionView>(
    searchParams.get("view") === "overview" ? "overview" : "deck",
  );
  const [toast, setToast] = useState<string | null>(null);
  const [pendingStudentIds, setPendingStudentIds] = useState<Set<number>>(new Set());

  const { data: session, isLoading, error } = useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => api.session(sessionId),
  });

  useEffect(() => {
    if (session) setStudents(session.students);
  }, [session]);

  const setStatus = useMutation({
    mutationFn: async ({
      studentId,
      status,
      attendanceId,
    }: {
      studentId: number;
      status: AttendanceStatus;
      attendanceId?: number;
    }) => {
      const summary = await api.setAttendance(sessionId, studentId, status, attendanceId, trainer?.id);
      return { studentId, summary };
    },
    onSuccess: ({ studentId, summary }) => {
      setStudents((prev) =>
        prev.map((s) => (s.id === studentId ? { ...s, attendance: summary } : s)),
      );
      hapticSuccess();
    },
    onError: (err) => {
      if (session) setStudents(session.students);
      setToast(String(err));
      setTimeout(() => setToast(null), 4000);
    },
    onSettled: (_data, _err, vars) => {
      setPendingStudentIds((prev) => {
        const next = new Set(prev);
        next.delete(vars.studentId);
        return next;
      });
      queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
      queryClient.invalidateQueries({ queryKey: ["training-sessions"] });
      queryClient.invalidateQueries({ queryKey: ["today-sessions-progress"] });
    },
  });

  const handleStatus = useCallback(
    async (studentId: number, status: AttendanceStatus, attendanceId?: number) => {
      if (!online) {
        setToast("Jsi offline — nelze uložit");
        setTimeout(() => setToast(null), 3000);
        throw new Error("offline");
      }
      setPendingStudentIds((prev) => new Set(prev).add(studentId));
      await setStatus.mutateAsync({ studentId, status, attendanceId });
    },
    [online, setStatus],
  );

  const showOverview = useCallback(() => setView("overview"), []);
  const isSaving = (studentId: number) => pendingStudentIds.has(studentId);

  if (isLoading) {
    return (
      <div className="boot-screen">
        <p className="page-header__sub">Načítám roster…</p>
      </div>
    );
  }

  if (error || !session) {
    return (
      <div className="app-shell error-box">
        Session nenalezena.
        <br />
        <Link to="/today">← Zpět</Link>
      </div>
    );
  }

  if (!isAuthenticated || !trainer) {
    return (
      <div className="app-shell error-box">
        Nejprve se přihlas jako trenér.
        <br />
        <Link to="/">← Zpět</Link>
      </div>
    );
  }

  const { marked, total } = countMarked(students);
  const counts = countByStatus(students);
  const actionsDisabled = !online || setStatus.isPending;

  return (
    <div className="app-shell app-shell--session">
      <OfflineBanner />

      <div className="session-top">
        <Link to="/today" className="back-link">
          ←
        </Link>
        <div className="session-top__info">
          <h1 className="session-top__title">{session.training_group.name}</h1>
          <p className="session-top__sub">
            {formatTime(session.training_group.start_time)} · {session.branch.name}
          </p>
        </div>
        <div className="session-top__actions">
          <TrainerSwitcher variant="compact" />
          <ProgressRing marked={marked} total={total} size={48} />
        </div>
      </div>

      <div className="session-view-toggle" role="tablist" aria-label="Zobrazení docházky">
        <button
          type="button"
          role="tab"
          aria-selected={view === "deck"}
          className={`session-view-toggle__btn${view === "deck" ? " session-view-toggle__btn--active" : ""}`}
          onClick={() => setView("deck")}
        >
          Karty
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={view === "overview"}
          className={`session-view-toggle__btn${view === "overview" ? " session-view-toggle__btn--active" : ""}`}
          onClick={() => setView("overview")}
        >
          Přehled
          {marked > 0 && <span className="session-view-toggle__badge">{marked}/{total}</span>}
        </button>
      </div>

      {view === "deck" ? (
        <StudentSwipeDeck
          students={students}
          onStatus={handleStatus}
          disabled={actionsDisabled}
          isSaving={isSaving}
          onAllDone={showOverview}
        />
      ) : (
        <>
          <AttendanceOverview
            students={students}
            onStatus={handleStatus}
            disabled={actionsDisabled}
            isSaving={isSaving}
          />
          <div className="session-overview-footer">
            <Link to="/today" className="btn btn--ghost session-overview-footer__back">
              ← Dnešní přehled
            </Link>
            {counts.unmarked === 0 && (
              <p className="session-overview-footer__done">Docházka kompletní</p>
            )}
          </div>
        </>
      )}

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}
