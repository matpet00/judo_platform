"""Trainer PIN strength rules."""

from __future__ import annotations

MIN_TRAINER_PIN_LENGTH = 6
MAX_TRAINER_PIN_LENGTH = 8

WEAK_TRAINER_PINS = frozenset(
    {
        "0000",
        "1111",
        "1234",
        "2222",
        "4321",
        "5678",
        "9999",
    },
)


def trainer_pin_change_required(pin: str) -> bool:
    if not pin.isdigit():
        return True
    if len(pin) < MIN_TRAINER_PIN_LENGTH:
        return True
    return pin in WEAK_TRAINER_PINS


def validate_new_trainer_pin(pin: str) -> None:
    if not pin.isdigit():
        raise ValueError("PIN must contain digits only.")
    if len(pin) < MIN_TRAINER_PIN_LENGTH or len(pin) > MAX_TRAINER_PIN_LENGTH:
        raise ValueError(f"PIN must be {MIN_TRAINER_PIN_LENGTH}–{MAX_TRAINER_PIN_LENGTH} digits.")
    if pin in WEAK_TRAINER_PINS:
        raise ValueError("PIN is too weak. Choose a different PIN.")
