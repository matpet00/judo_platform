const E164_RE = /^\+[1-9]\d{7,14}$/;

export const PHONE_PLACEHOLDER = "+420601234567";
export const PHONE_HINT = "Mezinárodní formát E.164 — začíná znakem + (např. +420…).";

export function normalizePhone(value: string): string {
  return value.replace(/[\s\-().]/g, "").trim();
}

export function isValidE164Phone(value: string): boolean {
  return E164_RE.test(normalizePhone(value));
}

/** Udržuje + na začátku a povolí jen číslice za ním. */
export function formatPhoneInput(raw: string): string {
  const trimmed = raw.trim();
  if (!trimmed) return "+";

  let digits = trimmed.replace(/[^\d+]/g, "");
  if (!digits.startsWith("+")) {
    digits = `+${digits.replace(/\+/g, "")}`;
  } else {
    digits = `+${digits.slice(1).replace(/\+/g, "")}`;
  }
  return digits;
}

export function phoneError(value: string): string | null {
  const compact = normalizePhone(value);
  if (!compact || compact === "+") return "Zadej telefonní číslo.";
  if (!compact.startsWith("+")) return "Telefon musí začínat znakem +.";
  if (!isValidE164Phone(compact)) {
    return "Neplatný formát. Použij E.164, např. +420601234567.";
  }
  return null;
}
