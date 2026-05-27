import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion, PanInfo, useMotionValue, useTransform } from "framer-motion";
import type { AttendanceStatus, SessionStudent } from "../api/types";
import "./StudentSwipeDeck.css";

const SWIPE_THRESHOLD = 100;

interface Props {
  students: SessionStudent[];
  onStatus: (studentId: number, status: AttendanceStatus, attendanceId?: number) => Promise<void>;
  disabled?: boolean;
  isSaving?: (studentId: number) => boolean;
  onAllDone?: () => void;
}

function sortStudents(students: SessionStudent[]): SessionStudent[] {
  return [...students].sort((a, b) => {
    const aDone = a.attendance !== null ? 1 : 0;
    const bDone = b.attendance !== null ? 1 : 0;
    if (aDone !== bDone) return aDone - bDone;
    return a.last_name.localeCompare(b.last_name, "cs");
  });
}

function DeckCard({
  student,
  onSwipe,
  onExcused,
  disabled,
  saving,
}: {
  student: SessionStudent;
  onSwipe: (status: AttendanceStatus) => void;
  onExcused: () => void;
  disabled?: boolean;
  saving?: boolean;
}) {
  const x = useMotionValue(0);
  const rotate = useTransform(x, [-200, 200], [-8, 8]);
  const presentOpacity = useTransform(x, [0, 60], [0, 1]);
  const absentOpacity = useTransform(x, [0, -60], [0, 1]);
  const presentOverlay = useTransform(x, [0, 60], [0, 0.35]);
  const absentOverlay = useTransform(x, [0, -60], [0, 0.35]);
  const borderColor = useTransform(
    x,
    [-120, -30, 0, 30, 120],
    [
      "rgba(161, 40, 40, 0.55)",
      "rgba(161, 40, 40, 0.25)",
      "rgba(212, 175, 55, 0.45)",
      "rgba(45, 157, 107, 0.25)",
      "rgba(45, 157, 107, 0.55)",
    ],
  );
  const lastTap = useRef(0);
  const busy = disabled || saving;

  const handleDragEnd = (_: unknown, info: PanInfo) => {
    if (busy) return;
    if (info.offset.x > SWIPE_THRESHOLD) onSwipe("present");
    else if (info.offset.x < -SWIPE_THRESHOLD) onSwipe("absent");
  };

  const handleTap = () => {
    if (busy) return;
    const now = Date.now();
    if (now - lastTap.current < 350) {
      onExcused();
      lastTap.current = 0;
      return;
    }
    lastTap.current = now;
  };

  const status = student.attendance?.status;

  return (
    <motion.div
      className="deck-card-wrap"
      style={{ x, rotate }}
      drag={busy ? false : "x"}
      dragConstraints={{ left: 0, right: 0 }}
      dragElastic={0.2}
      onDragEnd={handleDragEnd}
      onTap={handleTap}
      whileTap={{ scale: 0.98 }}
    >
      <motion.div
        className={`deck-card${status ? ` deck-card--${status}` : ""}${saving ? " deck-card--saving" : ""}`}
        style={{ borderColor: busy ? undefined : borderColor }}
      >
        {!busy && (
          <>
            <motion.div
              className="deck-card__drag-overlay deck-card__drag-overlay--present"
              style={{ opacity: presentOverlay }}
            />
            <motion.div
              className="deck-card__drag-overlay deck-card__drag-overlay--absent"
              style={{ opacity: absentOverlay }}
            />
            <motion.div
              className="deck-card__swipe-hint deck-card__swipe-hint--present"
              style={{ opacity: presentOpacity }}
            >
              <span className="deck-card__swipe-hint__lead">Bude změněn na</span>
              <span className="deck-card__swipe-hint__status">Přítomen</span>
            </motion.div>
            <motion.div
              className="deck-card__swipe-hint deck-card__swipe-hint--absent"
              style={{ opacity: absentOpacity }}
            >
              <span className="deck-card__swipe-hint__lead">Bude změněn na</span>
              <span className="deck-card__swipe-hint__status">Nepřítomen</span>
            </motion.div>
          </>
        )}
        <div className="deck-card__belt" />
        <div className="deck-card__age">{student.age_group}</div>
        <h2 className="deck-card__name">
          {student.first_name}
          <br />
          {student.last_name}
        </h2>
        {saving && <div className="deck-card__saving">Ukládám…</div>}
        {!saving && status && (
          <div className={`deck-card__status deck-card__status--${status}`}>{statusLabel(status)}</div>
        )}
        <p className="deck-card__tap-hint">2× tap = omluven</p>
      </motion.div>
    </motion.div>
  );
}

function statusLabel(s: AttendanceStatus): string {
  if (s === "present") return "Přítomen";
  if (s === "absent") return "Nepřítomen";
  return "Omluven";
}

export function StudentSwipeDeck({ students, onStatus, disabled, isSaving, onAllDone }: Props) {
  const sorted = useMemo(() => sortStudents(students), [students]);
  const [index, setIndex] = useState(0);
  const [exitDir, setExitDir] = useState<1 | -1 | 0>(0);
  const [acting, setActing] = useState(false);
  const doneNotified = useRef(false);

  const current = sorted[index];
  const allDone = index >= sorted.length;

  useEffect(() => {
    if (!allDone || doneNotified.current) return;
    doneNotified.current = true;
    onAllDone?.();
  }, [allDone, onAllDone]);

  const advance = useCallback(
    (dir: 1 | -1 | 0) => {
      setExitDir(dir);
      setIndex((i) => Math.min(i + 1, sorted.length));
    },
    [sorted.length],
  );

  const handleAction = useCallback(
    async (status: AttendanceStatus) => {
      if (!current || acting) return;
      setActing(true);
      try {
        const dir = status === "present" ? 1 : status === "absent" ? -1 : 0;
        await onStatus(current.id, status, current.attendance?.id);
        advance(dir);
      } catch {
        // error handled in parent
      } finally {
        setActing(false);
      }
    },
    [current, acting, onStatus, advance],
  );

  if (allDone) {
    return (
      <div className="deck-done">
        <div className="deck-done__icon">✓</div>
        <h2 className="deck-done__title">Hotovo</h2>
        <p className="deck-done__sub">Všichni žáci prošli — v přehledu můžeš hodnoty upravit</p>
        {onAllDone && (
          <button type="button" className="btn btn--primary deck-done__cta" onClick={onAllDone}>
            Přehled docházky
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="deck">
      <AnimatePresence mode="popLayout">
        <motion.div
          key={index}
          className="deck__card-layer"
          initial={{ scale: 0.92, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{
            x: exitDir === 1 ? 400 : exitDir === -1 ? -400 : 0,
            opacity: 0,
            transition: { duration: 0.25 },
          }}
        >
          <DeckCard
            student={current}
            onSwipe={(status) => {
              void handleAction(status);
            }}
            onExcused={() => {
              void handleAction("excused");
            }}
            disabled={disabled || acting}
            saving={current ? isSaving?.(current.id) : false}
          />
        </motion.div>
      </AnimatePresence>

      <div className="deck__footer-hint">
        <span className="deck__hint-left">← nepřítomen</span>
        <span className="deck__hint-mid">2× tap omluven</span>
        <span className="deck__hint-right">přítomen →</span>
      </div>
      <div className="deck__counter">
        {index + 1} / {sorted.length}
      </div>
    </div>
  );
}
