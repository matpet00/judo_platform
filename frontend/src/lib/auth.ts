const TOKEN_KEY = "judo-trainer-token";
const TRAINER_ID_KEY = "judo-trainer-id";

export function getTrainerToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function getStoredTrainerId(): number | null {
  const raw = sessionStorage.getItem(TRAINER_ID_KEY);
  if (!raw) return null;
  const id = Number(raw);
  return Number.isFinite(id) && id > 0 ? id : null;
}

export function setTrainerAuth(trainerId: number, token: string): void {
  sessionStorage.setItem(TRAINER_ID_KEY, String(trainerId));
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearTrainerAuth(): void {
  sessionStorage.removeItem(TRAINER_ID_KEY);
  sessionStorage.removeItem(TOKEN_KEY);
}
