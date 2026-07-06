export const BIRTH_DATE_PLACEHOLDER = "DD/MM/YYYY";
export const BIRTH_DATE_HINT = "Datum narození ve formátu DD/MM/YYYY.";

/** Formátuje psaní: jen číslice, automaticky lomítka. */
export function formatBirthDateInput(raw: string): string {
  const digits = raw.replace(/\D/g, "").slice(0, 8);
  if (digits.length <= 2) return digits;
  if (digits.length <= 4) return `${digits.slice(0, 2)}/${digits.slice(2)}`;
  return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
}

/** Převede DD/MM/YYYY na ISO YYYY-MM-DD pro API. */
export function parseBirthDateDdMmYyyy(value: string): string | null {
  const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(value.trim());
  if (!match) return null;

  const day = Number(match[1]);
  const month = Number(match[2]);
  const year = Number(match[3]);
  if (month < 1 || month > 12 || day < 1 || day > 31 || year < 1900 || year > 2100) {
    return null;
  }

  const iso = `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
  const parsed = new Date(`${iso}T12:00:00`);
  if (Number.isNaN(parsed.getTime())) return null;
  if (parsed.getFullYear() !== year || parsed.getMonth() + 1 !== month || parsed.getDate() !== day) {
    return null;
  }
  return iso;
}

export function birthDateError(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) return "Zadej datum narození.";
  if (!/^\d{2}\/\d{2}\/\d{4}$/.test(trimmed)) return `Použij formát ${BIRTH_DATE_PLACEHOLDER}.`;
  if (!parseBirthDateDdMmYyyy(trimmed)) return "Neplatné datum narození.";
  return null;
}

export function birthDateToIso(value: string): string {
  const iso = parseBirthDateDdMmYyyy(value);
  if (!iso) throw new Error(birthDateError(value) ?? "Neplatné datum narození.");
  return iso;
}
