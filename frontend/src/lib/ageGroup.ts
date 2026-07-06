import type { AgeGroup } from "../api/types";

const AGE_LIMITS: { limit: number; group: AgeGroup }[] = [
  { limit: 8, group: "U8" },
  { limit: 10, group: "U10" },
  { limit: 12, group: "U12" },
  { limit: 14, group: "U14" },
  { limit: 16, group: "U16" },
  { limit: 18, group: "U18" },
];

export function ageAtYearEnd(birthDateIso: string, referenceYear?: number): number {
  const birth = new Date(`${birthDateIso}T12:00:00`);
  if (Number.isNaN(birth.getTime())) {
    throw new Error("Neplatné datum narození.");
  }
  const year = referenceYear ?? new Date().getFullYear();
  if (birth.getFullYear() > year) {
    throw new Error("Datum narození nesmí být v budoucnosti.");
  }
  return year - birth.getFullYear();
}

export function computeAgeGroup(birthDateIso: string, referenceYear?: number): AgeGroup {
  const year = referenceYear ?? new Date().getFullYear();
  const age = ageAtYearEnd(birthDateIso, year);
  for (const { limit, group } of AGE_LIMITS) {
    if (age < limit) return group;
  }
  throw new Error(`Dítě je starší než U18 (věk k 31. 12. ${year}: ${age} let).`);
}

export function currentReferenceYear(): number {
  return new Date().getFullYear();
}

export function ageGroupHint(): string {
  return "Kategorie podle věku k 31. 12. aktuálního kalendářního roku (přepočítává se automaticky).";
}
