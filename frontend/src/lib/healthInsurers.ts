export const HEALTH_INSURERS = [
  "VZP ČR",
  "VoZP ČR",
  "ČPZP",
  "OZP",
  "ZP MV ČR",
  "RBP",
  "ZP Škoda",
  "ZP MetLife",
  "ZP 211",
] as const;

export type HealthInsurer = (typeof HEALTH_INSURERS)[number];
