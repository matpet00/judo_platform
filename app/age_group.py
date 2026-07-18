"""Věkové kategorie juda podle kalendářního roku (ČJF).

Kategorie se určuje podle věku sportovce k 31. 12. daného roku — prakticky
``reference_year - birth_year`` (rok narození vs. aktuální/soutěžní rok).
"""

from datetime import date

from app.models import AgeGroup

AGE_GROUP_ORDER: tuple[AgeGroup, ...] = (
    AgeGroup.U8,
    AgeGroup.U10,
    AgeGroup.U12,
    AgeGroup.U14,
    AgeGroup.U16,
    AgeGroup.U18,
    AgeGroup.U21,
    AgeGroup.Over21,
)

# Horní hranice věku k 31. 12. (věk < limit → daná kategorie). Over21 = 21+.
_AGE_LIMITS: tuple[tuple[int, AgeGroup], ...] = (
    (8, AgeGroup.U8),
    (10, AgeGroup.U10),
    (12, AgeGroup.U12),
    (14, AgeGroup.U14),
    (16, AgeGroup.U16),
    (18, AgeGroup.U18),
    (21, AgeGroup.U21),
)


def age_at_year_end(birth_date: date, reference_year: int | None = None) -> int:
    year = reference_year if reference_year is not None else date.today().year
    if birth_date.year > year:
        raise ValueError("Datum narození nesmí být v budoucnosti.")
    return year - birth_date.year


def compute_age_group(birth_date: date, reference_year: int | None = None) -> AgeGroup:
    """Vrátí věkovou kategorii pro dané datum narození a referenční rok."""
    age = age_at_year_end(birth_date, reference_year)
    if age < 0:
        raise ValueError("Datum narození nesmí být v budoucnosti.")
    for limit, group in _AGE_LIMITS:
        if age < limit:
            return group
    return AgeGroup.Over21
