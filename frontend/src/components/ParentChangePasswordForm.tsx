import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { api } from "../api/client";

const LOGOUT_COUNTDOWN_SECONDS = 5;
const MIN_PASSWORD_LENGTH = 6;

type ParentChangePasswordFormProps = {
  onClose: () => void;
  onSuccess: () => void;
};

export function ParentChangePasswordForm({ onClose, onSuccess }: ParentChangePasswordFormProps) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [countdown, setCountdown] = useState<number | null>(null);
  const finished = useRef(false);

  const finish = useCallback(() => {
    if (finished.current) return;
    finished.current = true;
    onSuccess();
  }, [onSuccess]);

  const passwordOk = (value: string) => value.length >= MIN_PASSWORD_LENGTH;
  const canSubmit =
    currentPassword.length > 0 &&
    passwordOk(newPassword) &&
    passwordOk(confirmPassword) &&
    newPassword === confirmPassword &&
    newPassword !== currentPassword;

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
      await api.changeParentPassword(currentPassword, newPassword);
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
          <p className="page-header__eyebrow">Heslo</p>
          <h1 className="trainer-picker__title">Heslo změněno</h1>
          <p className="trainer-picker__sub">
            {countdown > 0 ? `Budete odhlášeni za ${countdown}…` : "Odhlašuji…"}
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
        <p className="page-header__eyebrow">Heslo</p>
        <h1 className="trainer-picker__title">Změnit heslo</h1>
        <p className="trainer-picker__sub">Zadej staré a nové heslo (min. {MIN_PASSWORD_LENGTH} znaků).</p>
      </header>

      <label className="trainer-pin-gate__label">
        Staré heslo
        <input
          className="trainer-pin-gate__input"
          type="password"
          autoComplete="current-password"
          value={currentPassword}
          disabled={pending}
          onChange={(e) => setCurrentPassword(e.target.value)}
        />
      </label>

      <label className="trainer-pin-gate__label">
        Nové heslo
        <input
          className="trainer-pin-gate__input"
          type="password"
          autoComplete="new-password"
          value={newPassword}
          disabled={pending}
          onChange={(e) => setNewPassword(e.target.value)}
        />
      </label>

      <label className="trainer-pin-gate__label">
        Potvrzení nového hesla
        <input
          className="trainer-pin-gate__input"
          type="password"
          autoComplete="new-password"
          value={confirmPassword}
          disabled={pending}
          onChange={(e) => setConfirmPassword(e.target.value)}
        />
      </label>

      {confirmPassword && newPassword !== confirmPassword && (
        <p className="page-header__sub" style={{ margin: 0 }}>
          Potvrzení se neshoduje s novým heslem.
        </p>
      )}
      {newPassword && currentPassword && newPassword === currentPassword && (
        <p className="page-header__sub" style={{ margin: 0 }}>
          Nové heslo musí být jiné než staré.
        </p>
      )}

      {error && <p className="error-box trainer-pin-gate__error">{error}</p>}

      <div className="confirm-card__actions">
        <button type="button" className="btn btn--ghost" disabled={pending} onClick={onClose}>
          Zrušit
        </button>
        <button type="submit" className="btn btn--primary" disabled={pending || !canSubmit}>
          {pending ? "Ukládám…" : "Změnit heslo"}
        </button>
      </div>
    </form>
  );
}
