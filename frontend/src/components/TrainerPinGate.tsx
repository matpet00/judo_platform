import { useState } from "react";
import type { Trainer } from "../api/types";
import { trainerLabel } from "./TrainerPicker";

type TrainerPinGateProps = {
  trainer: Trainer;
  onSubmit: (pin: string) => Promise<void>;
  onCancel: () => void;
  error?: string | null;
  pending?: boolean;
};

export function TrainerPinGate({ trainer, onSubmit, onCancel, error, pending }: TrainerPinGateProps) {
  const [pin, setPin] = useState("");

  return (
    <div className="trainer-pin-gate">
      <header className="trainer-picker__header">
        <p className="page-header__eyebrow">PIN</p>
        <h1 className="trainer-picker__title">{trainerLabel(trainer)}</h1>
        <p className="trainer-picker__sub">Zadej svůj PIN pro docházku</p>
      </header>

      <input
        className="trainer-pin-gate__input"
        type="password"
        inputMode="numeric"
        pattern="[0-9]*"
        maxLength={8}
        autoComplete="one-time-code"
        placeholder="••••"
        value={pin}
        disabled={pending}
        onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))}
      />

      {error && <p className="error-box trainer-pin-gate__error">{error}</p>}

      <div className="confirm-card__actions">
        <button type="button" className="btn btn--ghost" disabled={pending} onClick={onCancel}>
          Zpět
        </button>
        <button
          type="button"
          className="btn btn--primary"
          disabled={pending || pin.length < 4}
          onClick={() => onSubmit(pin)}
        >
          {pending ? "Ověřuji…" : "Přihlásit"}
        </button>
      </div>
    </div>
  );
}
