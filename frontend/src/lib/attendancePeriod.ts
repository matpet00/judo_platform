/** Judo season Sep–Jun period helpers (mirrors app/attendance_report.py). */

export type PeriodMode = "month" | "quarter" | "half" | "season" | "custom";

export type PeriodState = {
  mode: PeriodMode;
  /** Anchor YYYY-MM for month / navigation within season. */
  month: string;
  /** Season start year (Sep of this year). */
  seasonStartYear: number;
  quarter: 1 | 2 | 3 | 4;
  half: 1 | 2;
  customFrom: string;
  customTo: string;
};

export type DateRange = { dateFrom: string; dateTo: string };

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

export function isoDate(y: number, m: number, d: number): string {
  return `${y}-${pad2(m)}-${pad2(d)}`;
}

export function todayMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${pad2(now.getMonth() + 1)}`;
}

export function seasonStartYearForDate(d: Date): number {
  const month = d.getMonth() + 1;
  const year = d.getFullYear();
  if (month >= 9) return year;
  return year - 1;
}

export function defaultPeriodState(now = new Date()): PeriodState {
  const seasonStartYear = seasonStartYearForDate(now);
  const month = todayMonth();
  const [y, m] = month.split("-").map(Number);
  const { quarter, half } = quarterHalfForCalendarMonth(y, m, seasonStartYear);
  return {
    mode: "month",
    month,
    seasonStartYear,
    quarter,
    half,
    customFrom: isoDate(y, m, 1),
    customTo: isoDate(y, m, new Date(y, m, 0).getDate()),
  };
}

/** Map a calendar month into season quarter/half (best effort). */
export function quarterHalfForCalendarMonth(
  _year: number,
  month: number,
  _seasonStartYear: number,
): { quarter: 1 | 2 | 3 | 4; half: 1 | 2 } {
  if (month >= 9 && month <= 11) return { quarter: 1, half: 1 };
  if (month === 12 || month === 1) return { quarter: 2, half: 1 };
  if (month >= 2 && month <= 4) return { quarter: 3, half: 2 };
  if (month >= 5 && month <= 6) return { quarter: 4, half: 2 };
  // Jul–Aug: treat as end of prior season Q4
  return { quarter: 4, half: 2 };
}

export function seasonBounds(startYear: number): DateRange {
  return {
    dateFrom: isoDate(startYear, 9, 1),
    dateTo: isoDate(startYear + 1, 6, 30),
  };
}

export function halfBounds(startYear: number, half: 1 | 2): DateRange {
  if (half === 1) {
    return { dateFrom: isoDate(startYear, 9, 1), dateTo: isoDate(startYear + 1, 1, 31) };
  }
  return { dateFrom: isoDate(startYear + 1, 2, 1), dateTo: isoDate(startYear + 1, 6, 30) };
}

export function quarterBounds(startYear: number, quarter: 1 | 2 | 3 | 4): DateRange {
  if (quarter === 1) return { dateFrom: isoDate(startYear, 9, 1), dateTo: isoDate(startYear, 11, 30) };
  if (quarter === 2) return { dateFrom: isoDate(startYear, 12, 1), dateTo: isoDate(startYear + 1, 1, 31) };
  if (quarter === 3) return { dateFrom: isoDate(startYear + 1, 2, 1), dateTo: isoDate(startYear + 1, 4, 30) };
  return { dateFrom: isoDate(startYear + 1, 5, 1), dateTo: isoDate(startYear + 1, 6, 30) };
}

export function monthBounds(month: string): DateRange | null {
  const match = /^(\d{4})-(\d{2})$/.exec(month);
  if (!match) return null;
  const year = Number(match[1]);
  const mon = Number(match[2]);
  const lastDay = new Date(year, mon, 0).getDate();
  return {
    dateFrom: `${month}-01`,
    dateTo: `${month}-${pad2(lastDay)}`,
  };
}

export function resolvePeriodRange(state: PeriodState): DateRange | null {
  if (state.mode === "month") return monthBounds(state.month);
  if (state.mode === "quarter") return quarterBounds(state.seasonStartYear, state.quarter);
  if (state.mode === "half") return halfBounds(state.seasonStartYear, state.half);
  if (state.mode === "season") return seasonBounds(state.seasonStartYear);
  if (!state.customFrom || !state.customTo) return null;
  if (state.customFrom > state.customTo) return null;
  return { dateFrom: state.customFrom, dateTo: state.customTo };
}

export function seasonLabel(startYear: number): string {
  const yy = String(startYear + 1).slice(-2);
  return `${startYear}/${yy}`;
}

export function formatPeriodLabel(state: PeriodState): string {
  const season = seasonLabel(state.seasonStartYear);
  if (state.mode === "month") {
    const [y, m] = state.month.split("-").map(Number);
    const months = [
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
    ];
    return `${months[m - 1]} ${y}`;
  }
  if (state.mode === "quarter") return `${state.quarter}. čtvrtletí ${season}`;
  if (state.mode === "half") return `${state.half}. pololetí ${season}`;
  if (state.mode === "season") return `Sezóna ${season}`;
  const from = formatCzechShort(state.customFrom);
  const to = formatCzechShort(state.customTo);
  return `${from} – ${to}`;
}

function formatCzechShort(iso: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!match) return iso;
  return `${Number(match[3])}. ${Number(match[2])}. ${match[1]}`;
}

function shiftMonth(month: string, delta: number): string {
  const [y, m] = month.split("-").map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}`;
}

export function shiftPeriod(state: PeriodState, delta: number): PeriodState {
  if (state.mode === "month") {
    const month = shiftMonth(state.month, delta);
    const [y, m] = month.split("-").map(Number);
    const seasonStartYear = seasonStartYearForDate(new Date(y, m - 1, 1));
    const { quarter, half } = quarterHalfForCalendarMonth(y, m, seasonStartYear);
    const bounds = monthBounds(month)!;
    return { ...state, month, seasonStartYear, quarter, half, customFrom: bounds.dateFrom, customTo: bounds.dateTo };
  }
  if (state.mode === "quarter") {
    let q = state.quarter + delta;
    let year = state.seasonStartYear;
    while (q > 4) {
      q -= 4;
      year += 1;
    }
    while (q < 1) {
      q += 4;
      year -= 1;
    }
    const quarter = q as 1 | 2 | 3 | 4;
    const half: 1 | 2 = quarter <= 2 ? 1 : 2;
    const bounds = quarterBounds(year, quarter);
    return {
      ...state,
      seasonStartYear: year,
      quarter,
      half,
      month: bounds.dateFrom.slice(0, 7),
      customFrom: bounds.dateFrom,
      customTo: bounds.dateTo,
    };
  }
  if (state.mode === "half") {
    let half = state.half + delta;
    let year = state.seasonStartYear;
    while (half > 2) {
      half -= 2;
      year += 1;
    }
    while (half < 1) {
      half += 2;
      year -= 1;
    }
    const h = half as 1 | 2;
    const bounds = halfBounds(year, h);
    return {
      ...state,
      seasonStartYear: year,
      half: h,
      quarter: h === 1 ? 1 : 3,
      month: bounds.dateFrom.slice(0, 7),
      customFrom: bounds.dateFrom,
      customTo: bounds.dateTo,
    };
  }
  if (state.mode === "season") {
    const year = state.seasonStartYear + delta;
    const bounds = seasonBounds(year);
    return {
      ...state,
      seasonStartYear: year,
      month: bounds.dateFrom.slice(0, 7),
      customFrom: bounds.dateFrom,
      customTo: bounds.dateTo,
    };
  }
  return state;
}

export function setPeriodMode(state: PeriodState, mode: PeriodMode): PeriodState {
  if (mode === state.mode) return state;
  const next = { ...state, mode };
  if (mode === "month") {
    const bounds = monthBounds(state.month);
    if (bounds) {
      next.customFrom = bounds.dateFrom;
      next.customTo = bounds.dateTo;
    }
    return next;
  }
  if (mode === "quarter") {
    const bounds = quarterBounds(state.seasonStartYear, state.quarter);
    next.customFrom = bounds.dateFrom;
    next.customTo = bounds.dateTo;
    next.month = bounds.dateFrom.slice(0, 7);
    return next;
  }
  if (mode === "half") {
    const bounds = halfBounds(state.seasonStartYear, state.half);
    next.customFrom = bounds.dateFrom;
    next.customTo = bounds.dateTo;
    next.month = bounds.dateFrom.slice(0, 7);
    return next;
  }
  if (mode === "season") {
    const bounds = seasonBounds(state.seasonStartYear);
    next.customFrom = bounds.dateFrom;
    next.customTo = bounds.dateTo;
    next.month = bounds.dateFrom.slice(0, 7);
    return next;
  }
  // custom: keep current resolved range as starting custom dates
  const current = resolvePeriodRange({ ...state, mode: state.mode === "custom" ? "month" : state.mode });
  if (current) {
    next.customFrom = current.dateFrom;
    next.customTo = current.dateTo;
  }
  return next;
}

export function rangeQueryParams(range: DateRange): string {
  return `date_from=${range.dateFrom}&date_to=${range.dateTo}`;
}
