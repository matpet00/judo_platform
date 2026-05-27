import type { AttendanceStatus, SessionStudent } from "../api/types";
import { STATUS_LABELS, STATUS_SHORT, countByStatus, sortStudentsByName } from "../lib/attendance";

const STATUSES: AttendanceStatus[] = ["present", "absent", "excused"];

type AttendanceOverviewProps = {
  students: SessionStudent[];
  onStatus: (studentId: number, status: AttendanceStatus, attendanceId?: number) => Promise<void>;
  disabled?: boolean;
  isSaving?: (studentId: number) => boolean;
  compact?: boolean;
};

export function AttendanceOverview({ students, onStatus, disabled, isSaving, compact }: AttendanceOverviewProps) {
  const counts = countByStatus(students);
  const sorted = sortStudentsByName(students);

  return (
    <div className={`attendance-overview${compact ? " attendance-overview--compact" : ""}`}>
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

      {!compact && (
        <p className="attendance-overview__hint">Klepnutím na stav u žáka hodnotu změníš.</p>
      )}

      <div className="attendance-roster">
        {sorted.map((student) => {
          const current = student.attendance?.status ?? null;
          const saving = isSaving?.(student.id) ?? false;
          return (
            <div key={student.id} className={`attendance-row${saving ? " attendance-row--saving" : ""}`}>
              <div className="attendance-row__info">
                <span className="attendance-row__name">
                  {student.first_name} {student.last_name}
                </span>
                <span className="attendance-row__age">{student.age_group}</span>
              </div>
              <div className="attendance-row__actions" role="group" aria-label={`Docházka ${student.first_name}`}>
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
                      void onStatus(student.id, status, student.attendance?.id);
                    }}
                  >
                    {STATUS_SHORT[status]}
                  </button>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
