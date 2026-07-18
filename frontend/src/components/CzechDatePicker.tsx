import { useEffect, useMemo, useRef, useState } from "react";

const WEEKDAYS = ["po", "út", "st", "čt", "pá", "so", "ne"] as const;

const MONTHS = [
  "leden",
  "únor",
  "březen",
  "duben",
  "květen",
  "červen",
  "červenec",
  "srpen",
  "září",
  "říjen",
  "listopad",
  "prosinec",
] as const;

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

function parseIso(value: string): { y: number; m: number; d: number } | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return null;
  return { y: Number(match[1]), m: Number(match[2]), d: Number(match[3]) };
}

export function formatCzechDate(iso: string): string {
  const p = parseIso(iso);
  if (!p) return iso || "—";
  return `${p.d}. ${p.m}. ${p.y}`;
}

export function formatCzechMonthYear(year: number, month1to12: number): string {
  return `${MONTHS[month1to12 - 1]} ${year}`;
}

type Props = {
  value: string;
  onChange: (iso: string) => void;
  label?: string;
  id?: string;
  /** Inclusive lower bound (YYYY-MM-DD); days before are disabled. */
  minDate?: string;
  /** Inclusive upper bound (YYYY-MM-DD); days after are disabled. */
  maxDate?: string;
};

function isDisabled(iso: string, minDate?: string, maxDate?: string): boolean {
  if (minDate && iso < minDate) return true;
  if (maxDate && iso > maxDate) return true;
  return false;
}

export function CzechDatePicker({ value, onChange, label, id, minDate, maxDate }: Props) {
  const [open, setOpen] = useState(false);
  const parsed = parseIso(value);
  const [viewYear, setViewYear] = useState(() => parsed?.y ?? new Date().getFullYear());
  const [viewMonth, setViewMonth] = useState(() => parsed?.m ?? new Date().getMonth() + 1);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    if (parsed) {
      setViewYear(parsed.y);
      setViewMonth(parsed.m);
    }
  }, [open, parsed?.y, parsed?.m]);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const cells = useMemo(() => {
    const first = new Date(viewYear, viewMonth - 1, 1);
    // Monday-first: JS Sunday=0 → shift so Monday=0
    const mondayIndex = (first.getDay() + 6) % 7;
    const daysInMonth = new Date(viewYear, viewMonth, 0).getDate();
    const items: Array<{ day: number | null; iso: string | null }> = [];
    for (let i = 0; i < mondayIndex; i++) items.push({ day: null, iso: null });
    for (let day = 1; day <= daysInMonth; day++) {
      items.push({
        day,
        iso: `${viewYear}-${pad2(viewMonth)}-${pad2(day)}`,
      });
    }
    while (items.length % 7 !== 0) items.push({ day: null, iso: null });
    return items;
  }, [viewYear, viewMonth]);

  const shiftView = (delta: number) => {
    const d = new Date(viewYear, viewMonth - 1 + delta, 1);
    setViewYear(d.getFullYear());
    setViewMonth(d.getMonth() + 1);
  };

  return (
    <div className="czech-datepicker notification-field" ref={rootRef}>
      {label && <span className="czech-datepicker__label">{label}</span>}
      <button
        id={id}
        type="button"
        className="czech-datepicker__trigger"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={label ? `${label}: ${formatCzechDate(value)}` : formatCzechDate(value)}
        onClick={() => setOpen((v) => !v)}
      >
        {formatCzechDate(value)}
      </button>
      {open && (
        <div className="czech-datepicker__popover" role="dialog" aria-label="Výběr data">
          <div className="czech-datepicker__nav">
            <button type="button" className="btn btn--ghost" aria-label="Předchozí měsíc" onClick={() => shiftView(-1)}>
              ‹
            </button>
            <p className="czech-datepicker__month">{formatCzechMonthYear(viewYear, viewMonth)}</p>
            <button type="button" className="btn btn--ghost" aria-label="Následující měsíc" onClick={() => shiftView(1)}>
              ›
            </button>
          </div>
          <div className="czech-datepicker__weekdays">
            {WEEKDAYS.map((day) => (
              <span key={day}>{day}</span>
            ))}
          </div>
          <div className="czech-datepicker__grid">
            {cells.map((cell, idx) => {
              if (cell.day == null || cell.iso == null) {
                return <span key={`e-${idx}`} className="czech-datepicker__cell czech-datepicker__cell--empty" />;
              }
              const disabled = isDisabled(cell.iso, minDate, maxDate);
              const selected = cell.iso === value;
              return (
                <button
                  key={cell.iso}
                  type="button"
                  disabled={disabled}
                  className={[
                    "czech-datepicker__cell",
                    selected ? "czech-datepicker__cell--selected" : "",
                    disabled ? "czech-datepicker__cell--disabled" : "",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                  onClick={() => {
                    if (disabled) return;
                    onChange(cell.iso!);
                    setOpen(false);
                  }}
                >
                  {cell.day}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export { MONTHS, WEEKDAYS };
