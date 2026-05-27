import type { SessionWithProgress } from "../api/types";
import { formatTime } from "../lib/sessionRouting";

type TodaySessionSummaryProps = {
  sessions: SessionWithProgress[];
  onOpenOverview: (sessionId: number) => void;
};

export function TodaySessionSummary({ sessions, onOpenOverview }: TodaySessionSummaryProps) {
  const withAttendance = sessions.filter((s) => s.marked > 0);
  if (withAttendance.length === 0) return null;

  return (
    <section className="section-block" style={{ animationDelay: "0.08s" }}>
      <h2 className="section-block__title">Dnešní docházka</h2>
      <div className="section-block__list">
        {withAttendance.map((session) => {
          const ratio = session.marked / Math.max(session.total, 1);
          const unmarked = session.total - session.marked;

          return (
            <button
              key={session.id}
              type="button"
              className="today-summary-card"
              onClick={() => onOpenOverview(session.id)}
            >
              <div className="today-summary-card__head">
                <div>
                  <div className="today-summary-card__title">{session.training_group.name}</div>
                  <div className="today-summary-card__sub">
                    {formatTime(session.training_group.start_time)} · {session.marked}/{session.total} označeno
                  </div>
                </div>
                <span className="today-summary-card__link">Přehled →</span>
              </div>
              <div className="today-summary-card__bar" aria-hidden="true">
                <span
                  className="today-summary-card__bar-fill"
                  style={{ width: `${Math.round(ratio * 100)}%` }}
                />
              </div>
              <div className="today-summary-card__stats">
                <span className="today-summary-card__stat today-summary-card__stat--present">
                  {session.present} přít.
                </span>
                <span className="today-summary-card__stat today-summary-card__stat--absent">
                  {session.absent} nepř.
                </span>
                <span className="today-summary-card__stat today-summary-card__stat--excused">
                  {session.excused} oml.
                </span>
                {unmarked > 0 && (
                  <span className="today-summary-card__stat today-summary-card__stat--pending">
                    {unmarked} chybí
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}
