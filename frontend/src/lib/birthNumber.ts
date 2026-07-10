export const BIRTH_NUMBER_PLACEHOLDER = "RRMMDD/XXXX";
export const BIRTH_NUMBER_HINT = "Rodné číslo ve formátu RRMMDD/XXXX (s lomítkem).";

/** Formátuje psaní: jen číslice, automaticky lomítko po 6. číslici. */
export function formatBirthNumberInput(raw: string): string {
  const digits = raw.replace(/\D/g, "").slice(0, 10);
  if (digits.length <= 6) return digits;
  return `${digits.slice(0, 6)}/${digits.slice(6)}`;
}

export function birthNumberError(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) return "Zadej rodné číslo.";
  if (!trimmed.includes("/")) return "Rodné číslo musí obsahovat lomítko.";
  if (!/^\d{6}\/\d{3,4}$/.test(trimmed)) {
    return `Použij formát ${BIRTH_NUMBER_PLACEHOLDER}.`;
  }
  return null;
}

export function normalizeBirthNumber(value: string): string {
  return value.trim().replace(/\s/g, "");
}
