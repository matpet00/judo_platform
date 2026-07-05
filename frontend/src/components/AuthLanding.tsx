import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useParent } from "../context/ParentContext";
import { TrainerLoginFlow } from "./TrainerSwitcher";

type Role = "trainer" | "parent";

function ParentLoginForm({ onBack }: { onBack: () => void }) {
  const navigate = useNavigate();
  const { loginParent } = useParent();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const submit = async () => {
    setPending(true);
    setError(null);
    try {
      await loginParent(username.trim(), password);
      navigate("/parent", { replace: true });
    } catch (e) {
      setError(String(e));
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="auth-card">
      <header className="trainer-picker__header">
        <p className="page-header__eyebrow">Rodič</p>
        <h1 className="trainer-picker__title">Přihlášení pro rodiče</h1>
        <p className="trainer-picker__sub">Zadej uživatelské jméno a heslo</p>
      </header>

      <form
        className="auth-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (!pending && username.trim() && password) void submit();
        }}
      >
        <label className="notification-field">
          Uživatelské jméno
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            placeholder="rodic"
            disabled={pending}
          />
        </label>
        <label className="notification-field">
          Heslo
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            placeholder="••••"
            disabled={pending}
          />
        </label>

        {error && <p className="error-box trainer-pin-gate__error">{error}</p>}

        <div className="confirm-card__actions">
          <button type="button" className="btn btn--ghost" disabled={pending} onClick={onBack}>
            Zpět
          </button>
          <button
            type="submit"
            className="btn btn--primary"
            disabled={pending || !username.trim() || !password}
          >
            {pending ? "Přihlašuji…" : "Přihlásit"}
          </button>
        </div>
      </form>
    </div>
  );
}

export function AuthLanding() {
  const [role, setRole] = useState<Role | null>(null);

  if (role === "trainer") {
    return (
      <div className="auth-card">
        <TrainerLoginFlow />
        <button type="button" className="btn btn--ghost auth-back" onClick={() => setRole(null)}>
          Zpět na výběr
        </button>
      </div>
    );
  }

  if (role === "parent") {
    return <ParentLoginForm onBack={() => setRole(null)} />;
  }

  return (
    <div className="hub-card">
      <p className="page-header__eyebrow">Judo klub</p>
      <h1 className="trainer-picker__title">Přihlášení</h1>
      <p className="trainer-picker__sub">Vyber, jak se chceš přihlásit</p>
      <div className="hub-card__actions">
        <button type="button" className="trainer-card" onClick={() => setRole("trainer")}>
          <span className="trainer-card__name">Trenér</span>
          <span className="trainer-card__branch">Přihlášení pro trenéry</span>
        </button>
        <button type="button" className="trainer-card" onClick={() => setRole("parent")}>
          <span className="trainer-card__name">Rodič</span>
          <span className="trainer-card__branch">Přihlášení pro rodiče</span>
        </button>
      </div>
    </div>
  );
}
