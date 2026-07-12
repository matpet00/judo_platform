import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { api } from "../api/client";

const LOGOUT_COUNTDOWN_SECONDS = 5;
const MIN_NEW_PIN_LENGTH = 6;
const MAX_PIN_LENGTH = 8;

type TrainerChangePinFormProps = {
  onClose: () => void;
  onSuccess: () => void;
  required?: boolean;
};

export function TrainerChangePinForm({ onClose, onSuccess, required = false }: TrainerChangePinFormProps) {
  const [currentPin, setCurrentPin] = useState("");
  const [newPin, setNewPin] = useState("");
  const [confirmPin, setConfirmPin] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [countdown, setCountdown] = useState<number | null>(null);
  const finished = useRef(false);

  const finish = useCallback(() => {
    if (finished.current) return;
    finished.current = true;
    onSuccess();
  }, [onSuccess]);

  const currentPinOk = (value: string) => value.length >= 4 && value.length <= MAX_PIN_LENGTH;
  const newPinOk = (value: string) => value.length >= MIN_NEW_PIN_LENGTH && value.length <= MAX_PIN_LENGTH;
  const canSubmit =
    currentPinOk(currentPin) &&
    newPinOk(newPin) &&
    newPinOk(confirmPin) &&
    newPin === confirmPin &&
    newPin !== currentPin;

  useEffect(() => {
    if (countdown === null) return;
    if (countdown <= 0) {
      finish();
      return;
    }
    const timer = window.setTimeout(() => setCountdown((prev) => (prev === null ? null : prev - 1)), 1000);
    return () => window.clearTimeout(timer);
  }, [countdown, finish]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setPending(true);
    setError(null);
    try {
      await api.changeTrainerPin(currentPin, newPin);
      setCountdown(LOGOUT_COUNTDOWN_SECONDS);
    } catch (err) {
      setError(String(err));
    } finally {
      setPending(false);
    }
  };

  if (countdown !== null) {
    return (
      <div className="trainer-pin-gate">
        <header className="trainer-picker__header">
          <p className="page-header__eyebrow">PIN</p>
          <h1 className="trainer-picker__title">PIN změněn</h1>
          <p className="trainer-picker__sub">
            {countdown > 0
              ? `Budete odhlášeni za ${countdown}…`
              : "Odhlašuji…"}
          </p>
        </header>
        <div className="confirm-card__actions">
          <button type="button" className="btn btn--primary" onClick={finish}>
            Odhlásit
          </button>
        </div>
      </div>
    );
  }

  return (
    <form className="trainer-pin-gate" onSubmit={handleSubmit}>
      <header className="trainer-picker__header">
        <p className="page-header__eyebrow">PIN</p>
        <h1 className="trainer-picker__title">{required ? "Nastav nový PIN" : "Změnit PIN"}</h1>
        <p className="trainer-picker__sub">
          {required
            ? "Výchozí nebo slabý PIN už nejde používat. Zadej starý a nový PIN (6–8 číslic)."
            : "Zadej starý a nový PIN (nový musí mít 6–8 číslic)."}
        </p>
      </header>

      <label className="trainer-pin-gate__label">
        Starý PIN
        <input
          className="trainer-pin-gate__input"
          type="password"
          inputMode="numeric"
          pattern="[0-9]*"
          maxLength={8}
          autoComplete="off"
          placeholder="••••"
          value={currentPin}
          disabled={pending}
          onChange={(e) => setCurrentPin(e.target.value.replace(/\D/g, ""))}
        />
      </label>

      <label className="trainer-pin-gate__label">
        Nový PIN
        <input
          className="trainer-pin-gate__input"
          type="password"
          inputMode="numeric"
          pattern="[0-9]*"
          maxLength={8}
          autoComplete="new-password"
          placeholder="••••"
          value={newPin}
          disabled={pending}
          onChange={(e) => setNewPin(e.target.value.replace(/\D/g, ""))}
        />
      </label>

      <label className="trainer-pin-gate__label">
        Potvrzení nového PIN
        <input
          className="trainer-pin-gate__input"
          type="password"
          inputMode="numeric"
          pattern="[0-9]*"
          maxLength={8}
          autoComplete="new-password"
          placeholder="••••"
          value={confirmPin}
          disabled={pending}
          onChange={(e) => setConfirmPin(e.target.value.replace(/\D/g, ""))}
        />
      </label>

      {confirmPin && newPin !== confirmPin && (
        <p className="page-header__sub" style={{ margin: 0 }}>
          Potvrzení se neshoduje s novým PIN.
        </p>
      )}
      {newPin && currentPin && newPin === currentPin && (
        <p className="page-header__sub" style={{ margin: 0 }}>
          Nový PIN musí být jiný než starý.
        </p>
      )}

      {error && <p className="error-box trainer-pin-gate__error">{error}</p>}

      <div className="confirm-card__actions">
        {!required && (
          <button type="button" className="btn btn--ghost" disabled={pending} onClick={onClose}>
            Zrušit
          </button>
        )}
        {required && (
          <button type="button" className="btn btn--ghost" disabled={pending} onClick={onClose}>
            Odhlásit
          </button>
        )}
        <button type="submit" className="btn btn--primary" disabled={pending || !canSubmit}>
          {pending ? "Ukládám…" : "Změnit PIN"}
        </button>
      </div>
    </form>
  );
}
