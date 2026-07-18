import type { EventType } from "../api/types";

export type PaySourceFilter = {
  includeTrainings: boolean;
  eventTypes: EventType[];
};

export const ALL_EVENT_TYPES: EventType[] = [
  "tournament",
  "meeting",
  "seminar",
  "training",
  "other",
];

export const EVENT_TYPE_PAY_LABELS: Record<EventType, string> = {
  tournament: "Turnaje",
  meeting: "Schůzky",
  seminar: "Školení",
  training: "Tréninky (akce)",
  other: "Jiné akce",
};

/** Default: club trainings + tournaments + meetings. */
export function defaultPaySourceFilter(): PaySourceFilter {
  return {
    includeTrainings: true,
    eventTypes: ["tournament", "meeting"],
  };
}

export function paySourceQueryParams(filter: PaySourceFilter): URLSearchParams {
  const params = new URLSearchParams();
  params.set("include_trainings", filter.includeTrainings ? "true" : "false");
  for (const type of filter.eventTypes) {
    params.append("event_types", type);
  }
  return params;
}

export function toggleEventType(filter: PaySourceFilter, type: EventType): PaySourceFilter {
  const has = filter.eventTypes.includes(type);
  return {
    ...filter,
    eventTypes: has ? filter.eventTypes.filter((t) => t !== type) : [...filter.eventTypes, type],
  };
}

export function setAllEventTypes(filter: PaySourceFilter, on: boolean): PaySourceFilter {
  return {
    ...filter,
    eventTypes: on ? [...ALL_EVENT_TYPES] : [],
  };
}
