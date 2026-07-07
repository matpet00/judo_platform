import type { AttendanceStatus, SessionTrainer } from "../api/types";
import { STATUS_LABELS, STATUS_SHORT } from "../lib/attendance";

const STATUSES: AttendanceStatus[] = ["present", "absent", "excused"];

type TrainerAttendanceOverviewProps = {
  trainers: SessionTrainer[];
  onStatus: (trainerId: number, status: AttendanceStatus, attendanceId?: number) => Promise<void>;
  disabled?: boolean;
  isSaving?: (trainerId: number) => boolean;
  onRemove?: (trainerId: number, attendanceId: number) => void;
};

export function TrainerAttendanceOverview({
  trainers,
  onStatus,
  disabled,
  isSaving,
  onRemove,
}: TrainerAttendanceOverviewProps) {
  if (trainers.length === 0) return null;

  const counts = {
    present: 0,
    absent: 0,
    excused: 0,
    unmarked: 0,
    total: trainers.length,
  };
  for (const trainer of trainers) {
    if (!trainer.attendance) {
      counts.unmarked += 1;
    } else {
      counts[trainer.attendance.status] += 1;
    }
  }
  const sorted = [...trainers].sort((a, b) =>
    a.last_name.localeCompare(b.last_name, "cs") || a.first_name.localeCompare(b.first_name, "cs"),
  );

  return (
    <div className="attendance-overview attendance-overview--trainers">
      <div className="admin-section-title">Trenéři na tréninku</div>
      <div className="attendance-summary">
        <div className="attendance-summary__item attendance-summary__item--present">
          <span className="attendance-summary__value">{counts.present}</span>
          <span className="attendance-summary__label">Přítomní</span>
        </div>
        <div className="attendance-summary__item attendance-summary__item--absent">
          <span className="attendance-summary__value">{counts.absent}</span>
          <span className="attendance-summary__label">Nepřítomní</span>
        </div>
        <div className="attendance-summary__item attendance-summary__item--excused">
          <span className="attendance-summary__value">{counts.excused}</span>
          <span className="attendance-summary__label">Omluvení</span>
        </div>
        {counts.unmarked > 0 && (
          <div className="attendance-summary__item attendance-summary__item--pending">
            <span className="attendance-summary__value">{counts.unmarked}</span>
            <span className="attendance-summary__label">Chybí</span>
          </div>
        )}
      </div>

      <div className="attendance-roster">
        {sorted.map((trainer) => {
          const current = trainer.attendance?.status ?? null;
          const saving = isSaving?.(trainer.id) ?? false;
          return (
            <div
              key={trainer.id}
              className={`attendance-row attendance-row--trainer${saving ? " attendance-row--saving" : ""}${trainer.is_guest ? " attendance-row--guest" : ""}`}
            >
              <div className="attendance-row__info">
                <span className="attendance-row__name">
                  {trainer.first_name} {trainer.last_name}
                  {trainer.is_guest ? (
                    <span className="attendance-guest-badge">Host</span>
                  ) : (
                    <span className="attendance-trainer-badge">Trenér</span>
                  )}
                </span>
                {trainer.branches && (
                  <span className="attendance-row__age">{trainer.branches}</span>
                )}
              </div>
              <div className="attendance-row__actions" role="group" aria-label={`Docházka ${trainer.first_name}`}>
                {STATUSES.map((status) => (
                  <button
                    key={status}
                    type="button"
                    className={`attendance-action attendance-action--${status}${
                      current === status ? " attendance-action--active" : ""
                    }`}
                    disabled={disabled || saving}
                    aria-pressed={current === status}
                    aria-label={STATUS_LABELS[status]}
                    onClick={() => {
                      void onStatus(trainer.id, status, trainer.attendance?.id);
                    }}
                  >
                    {STATUS_SHORT[status]}
                  </button>
                ))}
                {onRemove && trainer.is_guest && trainer.attendance?.id != null && (
                  <button
                    type="button"
                    className="attendance-guest-remove"
                    disabled={disabled || saving}
                    aria-label={`Odebrat trenéra ${trainer.first_name}`}
                    title="Odebrat trenéra z tréninku"
                    onClick={() => onRemove(trainer.id, trainer.attendance!.id)}
                  >
                    ×
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
