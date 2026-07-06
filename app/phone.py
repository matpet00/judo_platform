"""Validace telefonních čísel ve formátu E.164 (ITU-T)."""

import re

E164_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")


def normalize_phone_for_storage(value: str) -> str:
    return re.sub(r"[\s\-().]", "", value.strip())


def validate_e164_phone(value: str) -> str:
    compact = normalize_phone_for_storage(value)
    if not E164_PATTERN.fullmatch(compact):
        raise ValueError(
            "Telefon musí začínat znakem + a být ve formátu E.164 (např. +420601234567).",
        )
    return compact
