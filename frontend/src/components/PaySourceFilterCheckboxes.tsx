import type { EventType } from "../api/types";
import {
  ALL_EVENT_TYPES,
  EVENT_TYPE_PAY_LABELS,
  setAllEventTypes,
  toggleEventType,
  type PaySourceFilter,
} from "../lib/paySourceFilter";

type Props = {
  value: PaySourceFilter;
  onChange: (next: PaySourceFilter) => void;
};

export function PaySourceFilterCheckboxes({ value, onChange }: Props) {
  const allEventsOn = ALL_EVENT_TYPES.every((t) => value.eventTypes.includes(t));

  return (
    <div className="pay-source-filter">
      <p className="pay-source-filter__title">Zahrnout do přehledu</p>
      <div className="admin-checks">
        <label className="admin-check">
          <input
            type="checkbox"
            checked={value.includeTrainings}
            onChange={(e) => onChange({ ...value, includeTrainings: e.target.checked })}
          />
          Tréninky (docházka)
        </label>
        <label className="admin-check">
          <input
            type="checkbox"
            checked={allEventsOn}
            onChange={(e) => onChange(setAllEventTypes(value, e.target.checked))}
          />
          Všechny typy akcí
        </label>
      </div>
      <div className="admin-checks pay-source-filter__types">
        {ALL_EVENT_TYPES.map((type: EventType) => (
          <label key={type} className="admin-check">
            <input
              type="checkbox"
              checked={value.eventTypes.includes(type)}
              onChange={() => onChange(toggleEventType(value, type))}
            />
            {EVENT_TYPE_PAY_LABELS[type]}
          </label>
        ))}
      </div>
    </div>
  );
}
