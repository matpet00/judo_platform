export type ChartSegment = {
  label: string;
  value: number;
  color: string;
};

const CHART_COLORS = {
  gold: "var(--gold)",
  accent: "var(--excused)",
  present: "var(--present)",
  absent: "var(--absent)",
  muted: "var(--muted)",
  cream: "var(--cream)",
};

export const ADMIN_CHART_COLORS = CHART_COLORS;

function buildConicGradient(items: ChartSegment[]): string {
  const total = items.reduce((sum, item) => sum + item.value, 0);
  if (total === 0) return "conic-gradient(var(--border) 0deg 360deg)";
  let acc = 0;
  const stops: string[] = [];
  for (const item of items) {
    const pct = (item.value / total) * 100;
    stops.push(`${item.color} ${acc}% ${acc + pct}%`);
    acc += pct;
  }
  return `conic-gradient(${stops.join(", ")})`;
}

export function AdminBarChart({
  title,
  items,
}: {
  title?: string;
  items: ChartSegment[];
}) {
  if (items.length === 0) return null;
  const max = Math.max(...items.map((i) => i.value), 1);

  return (
    <div className="admin-chart">
      {title && <div className="admin-chart__title">{title}</div>}
      <div className="admin-chart__bars">
        {items.map((item) => (
          <div key={item.label} className="admin-chart__row">
            <span className="admin-chart__label">{item.label}</span>
            <div className="admin-chart__track" aria-hidden>
              <div
                className="admin-chart__fill"
                style={{
                  width: `${(item.value / max) * 100}%`,
                  backgroundColor: item.color,
                }}
              />
            </div>
            <span className="admin-chart__value">{item.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function AdminDonutChart({
  title,
  items,
  centerLabel,
}: {
  title?: string;
  items: ChartSegment[];
  centerLabel?: string;
}) {
  const total = items.reduce((sum, item) => sum + item.value, 0);
  if (total === 0) return null;

  return (
    <div className="admin-chart admin-chart--donut-wrap">
      {title && <div className="admin-chart__title">{title}</div>}
      <div className="admin-chart--donut">
        <div
          className="admin-chart__donut-ring"
          style={{ background: buildConicGradient(items) }}
          role="img"
          aria-label={items.map((i) => `${i.label}: ${i.value}`).join(", ")}
        />
        <div className="admin-chart__donut-center">
          <span className="admin-chart__donut-total">{total}</span>
          {centerLabel && <span className="admin-chart__donut-sub">{centerLabel}</span>}
        </div>
      </div>
      <ul className="admin-chart__legend">
        {items.map((item) => (
          <li key={item.label}>
            <span className="admin-chart__legend-swatch" style={{ backgroundColor: item.color }} />
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function AdminStackedBar({
  segments,
  showLegend,
}: {
  segments: ChartSegment[];
  showLegend?: boolean;
}) {
  const total = segments.reduce((sum, s) => sum + s.value, 0);
  const active = segments.filter((s) => s.value > 0);

  if (total === 0) {
    return <div className="admin-chart__stacked admin-chart__stacked--empty">Bez odpovědí</div>;
  }

  return (
    <div className="admin-chart__stacked-wrap">
      <div className="admin-chart__stacked" role="img" aria-label={active.map((s) => `${s.label}: ${s.value}`).join(", ")}>
        {active.map((seg) => (
          <div
            key={seg.label}
            className="admin-chart__stacked-seg"
            style={{ flex: seg.value, backgroundColor: seg.color }}
            title={`${seg.label}: ${seg.value}`}
          />
        ))}
      </div>
      {showLegend && (
        <div className="admin-chart__stacked-legend">
          {active.map((seg) => (
            <span key={seg.label}>
              <span className="admin-chart__legend-swatch" style={{ backgroundColor: seg.color }} />
              {seg.label} {seg.value}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export const RSVP_CHART_SEGMENTS = (yes: number, maybe: number, no: number): ChartSegment[] => [
  { label: "Ano", value: yes, color: CHART_COLORS.present },
  { label: "Možná", value: maybe, color: CHART_COLORS.gold },
  { label: "Ne", value: no, color: CHART_COLORS.absent },
];
