import { useEffect } from "react";
import type { PeriodMode, PeriodState } from "../lib/attendancePeriod";
import {
  formatPeriodLabel,
  setPeriodMode,
  shiftPeriod,
} from "../lib/attendancePeriod";
import { CzechDatePicker, formatCzechMonthYear } from "./CzechDatePicker";

type Props = {
  value: PeriodState;
  onChange: (next: PeriodState) => void;
  className?: string;
};

const MODE_OPTIONS: { value: PeriodMode; label: string }[] = [
  { value: "month", label: "Měsíc" },
  { value: "quarter", label: "Čtvrtletí" },
  { value: "half", label: "Pololetí" },
  { value: "season", label: "Sezóna" },
  { value: "custom", label: "Vlastní" },
];

function applyMonth(state: PeriodState, year: number, month1to12: number): PeriodState {
  const month = `${year}-${String(month1to12).padStart(2, "0")}`;
  const lastDay = new Date(year, month1to12, 0).getDate();
  const seasonStartYear = month1to12 >= 9 ? year : year - 1;
  return {
    ...state,
    month,
    seasonStartYear,
    customFrom: `${month}-01`,
    customTo: `${month}-${String(lastDay).padStart(2, "0")}`,
  };
}

export function AttendancePeriodPicker({ value, onChange, className = "" }: Props) {
  const canNavigate = value.mode !== "custom";
  const [y, m] = value.month.split("-").map(Number);

  useEffect(() => {
    if (value.mode !== "custom") return;
    if (!value.customFrom || !value.customTo) return;
    if (value.customFrom <= value.customTo) return;
    onChange({ ...value, customTo: value.customFrom });
  }, [value, onChange]);

  return (
    <div className={`attendance-period ${className}`.trim()}>
      <label className="notification-field">
        Období
        <select
          value={value.mode}
          onChange={(e) => onChange(setPeriodMode(value, e.target.value as PeriodMode))}
        >
          {MODE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </label>

      {value.mode === "custom" ? (
        <div className="attendance-period__custom">
          <CzechDatePicker
            label="Od"
            value={value.customFrom}
            onChange={(customFrom) => {
              const customTo =
                value.customTo && customFrom > value.customTo ? customFrom : value.customTo;
              onChange({ ...value, customFrom, customTo });
            }}
          />
          <CzechDatePicker
            label="Do"
            value={value.customTo}
            minDate={value.customFrom || undefined}
            onChange={(customTo) => {
              onChange({ ...value, customTo });
            }}
          />
        </div>
      ) : (
        <div className="attendance-period__nav">
          <button
            type="button"
            className="btn btn--ghost"
            aria-label="Předchozí období"
            disabled={!canNavigate}
            onClick={() => onChange(shiftPeriod(value, -1))}
          >
            ‹
          </button>
          <p className="attendance-period__label">{formatPeriodLabel(value)}</p>
          <button
            type="button"
            className="btn btn--ghost"
            aria-label="Následující období"
            disabled={!canNavigate}
            onClick={() => onChange(shiftPeriod(value, 1))}
          >
            ›
          </button>
        </div>
      )}

      {value.mode === "month" && (
        <label className="notification-field attendance-period__month-input">
          Měsíc
          <select
            value={value.month}
            aria-label={formatCzechMonthYear(y, m)}
            onChange={(e) => {
              const [yy, mm] = e.target.value.split("-").map(Number);
              onChange(applyMonth(value, yy, mm));
            }}
          >
            {monthOptionsAround(y, m).map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
      )}
    </div>
  );
}

/** ~±18 months around current selection for the Czech month dropdown. */
function monthOptionsAround(centerYear: number, centerMonth: number) {
  const options: { value: string; label: string }[] = [];
  const start = new Date(centerYear, centerMonth - 1 - 18, 1);
  for (let i = 0; i < 37; i++) {
    const d = new Date(start.getFullYear(), start.getMonth() + i, 1);
    const year = d.getFullYear();
    const month = d.getMonth() + 1;
    const value = `${year}-${String(month).padStart(2, "0")}`;
    options.push({ value, label: formatCzechMonthYear(year, month) });
  }
  return options;
}
