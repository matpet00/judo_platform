const TOKEN_KEY = "judo-trainer-token";
const TRAINER_ID_KEY = "judo-trainer-id";
const PIN_CHANGE_REQUIRED_KEY = "judo-trainer-pin-change-required";

export function getTrainerToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function getStoredTrainerId(): number | null {
  const raw = sessionStorage.getItem(TRAINER_ID_KEY);
  if (!raw) return null;
  const id = Number(raw);
  return Number.isFinite(id) && id > 0 ? id : null;
}

export function getTrainerPinChangeRequired(): boolean {
  return sessionStorage.getItem(PIN_CHANGE_REQUIRED_KEY) === "1";
}

export function setTrainerAuth(trainerId: number, token: string, pinChangeRequired = false): void {
  sessionStorage.setItem(TRAINER_ID_KEY, String(trainerId));
  sessionStorage.setItem(TOKEN_KEY, token);
  if (pinChangeRequired) {
    sessionStorage.setItem(PIN_CHANGE_REQUIRED_KEY, "1");
  } else {
    sessionStorage.removeItem(PIN_CHANGE_REQUIRED_KEY);
  }
}

export function clearTrainerPinChangeRequired(): void {
  sessionStorage.removeItem(PIN_CHANGE_REQUIRED_KEY);
}

export function clearTrainerAuth(): void {
  sessionStorage.removeItem(TRAINER_ID_KEY);
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(PIN_CHANGE_REQUIRED_KEY);
}

const PARENT_TOKEN_KEY = "judo-parent-token";
const PARENT_ID_KEY = "judo-parent-id";

export function getParentToken(): string | null {
  return sessionStorage.getItem(PARENT_TOKEN_KEY);
}

export function getStoredParentId(): number | null {
  const raw = sessionStorage.getItem(PARENT_ID_KEY);
  if (!raw) return null;
  const id = Number(raw);
  return Number.isFinite(id) && id > 0 ? id : null;
}

export function setParentAuth(parentId: number, token: string): void {
  sessionStorage.setItem(PARENT_ID_KEY, String(parentId));
  sessionStorage.setItem(PARENT_TOKEN_KEY, token);
}

export function clearParentAuth(): void {
  sessionStorage.removeItem(PARENT_ID_KEY);
  sessionStorage.removeItem(PARENT_TOKEN_KEY);
}

const ADMIN_TOKEN_KEY = "judo-admin-token";

export function getAdminToken(): string | null {
  return sessionStorage.getItem(ADMIN_TOKEN_KEY);
}

export function setAdminAuth(token: string): void {
  sessionStorage.setItem(ADMIN_TOKEN_KEY, token);
}

export function clearAdminAuth(): void {
  sessionStorage.removeItem(ADMIN_TOKEN_KEY);
}
