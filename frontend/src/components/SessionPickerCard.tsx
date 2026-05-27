import { formatTime } from "../lib/sessionRouting";
import type { SessionWithProgress, TrainingGroup } from "../api/types";
import { ProgressRing } from "./ProgressRing";

interface SessionPickerCardProps {
  title: string;
  subtitle: string;
  marked?: number;
  total?: number;
  highlight?: boolean;
  onClick: () => void;
  pending?: boolean;
}

export function SessionPickerCard({
  title,
  subtitle,
  marked,
  total,
  highlight,
  onClick,
  pending,
}: SessionPickerCardProps) {
  const showProgress = marked !== undefined && total !== undefined;

  return (
    <button
      type="button"
      className={`picker-card${highlight ? " picker-card--live" : ""}`}
      onClick={onClick}
      disabled={pending}
    >
      <div className="picker-card__body">
        <div className="picker-card__title">{title}</div>
        <div className="picker-card__sub">{subtitle}</div>
        {showProgress && (
          <div className="picker-card__progress-text">
            {marked}/{total} označeno
          </div>
        )}
      </div>
      {showProgress && total > 0 && <ProgressRing marked={marked} total={total} size={52} />}
      {pending && <span className="picker-card__pending">…</span>}
    </button>
  );
}

export function existingSessionCardProps(session: SessionWithProgress) {
  return {
    title: session.training_group.name,
    subtitle: `${formatTime(session.training_group.start_time)} – ${formatTime(session.training_group.end_time)} · ${session.branch.name}`,
    marked: session.marked,
    total: session.total,
  };
}

export function groupSlotCardProps(group: TrainingGroup) {
  return {
    title: group.name,
    subtitle: `${formatTime(group.start_time)} – ${formatTime(group.end_time)} · ${group.students.length} žáků`,
  };
}
