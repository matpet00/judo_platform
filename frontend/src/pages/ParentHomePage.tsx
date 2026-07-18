import { useCallback, useMemo, useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Navigate, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { countUnreadBoard, countUnreadPlanner } from "../lib/notificationNavigation";
import { parentNotificationsKey } from "../api/queryKeys";
import { ClubLogo } from "../components/ClubLogo";
import { ParentChangePasswordForm } from "../components/ParentChangePasswordForm";
import { useParent } from "../context/ParentContext";
import type { ParentChild, ParentSelf } from "../api/types";
import { computeAgeGroup } from "../lib/ageGroup";
import { birthNumberError, formatBirthNumberInput, normalizeBirthNumber } from "../lib/birthNumber";
import { HEALTH_INSURERS } from "../lib/healthInsurers";
import { formatPhoneInput, phoneError } from "../lib/phone";
import "../pages/AdminPage.css";

function formatDate(value: string | null): string {
  if (!value) return "—";
  const [year, month, day] = value.split("-");
  if (!year || !month || !day) return value;
  return `${day}.${month}.${year}`;
}

function ParentProfileEditModal({
  parent,
  onClose,
  onSaved,
}: {
  parent: ParentSelf;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [firstName, setFirstName] = useState(parent.first_name);
  const [lastName, setLastName] = useState(parent.last_name);
  const [email, setEmail] = useState(parent.email);
  const [phone, setPhone] = useState(parent.phone);

  const validationError = (() => {
    if (!firstName.trim() || !lastName.trim()) return "Vyplň jméno i příjmení.";
    if (!email.trim()) return "Vyplň e-mail.";
    const phoneErr = phoneError(phone);
    if (phoneErr) return phoneErr;
    return null;
  })();

  const save = useMutation({
    mutationFn: () =>
      api.updateParentMe({
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        email: email.trim(),
        phone: phone.trim(),
      }),
    onSuccess: () => {
      onSaved();
      onClose();
    },
  });

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal__head">
          <h2 className="modal__title">Upravit moje údaje</h2>
          <button type="button" className="modal__close" onClick={onClose} aria-label="Zavřít">
            ×
          </button>
        </div>
        <div className="modal__body">
          <form
            className="admin-form"
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              if (!validationError) save.mutate();
            }}
          >
            <div className="admin-field">
              <label>Jméno</label>
              <input value={firstName} onChange={(e) => setFirstName(e.target.value)} />
            </div>
            <div className="admin-field">
              <label>Příjmení</label>
              <input value={lastName} onChange={(e) => setLastName(e.target.value)} />
            </div>
            <div className="admin-field">
              <label>E-mail</label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div className="admin-field">
              <label>Telefon</label>
              <input
                value={phone}
                onChange={(e) => setPhone(formatPhoneInput(e.target.value))}
                placeholder="+420601234567"
              />
            </div>
            <p className="admin-field__hint">
              Přihlašovací jméno: {parent.username || "—"} (jen pro čtení)
            </p>
            {validationError && <p className="error-box">{validationError}</p>}
            {save.isError && <p className="error-box">{String(save.error)}</p>}
            <div className="admin-form__actions">
              <button type="button" className="btn btn--ghost" onClick={onClose}>
                Zrušit
              </button>
              <button type="submit" className="btn btn--primary" disabled={!!validationError || save.isPending}>
                {save.isPending ? "Ukládám…" : "Uložit"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

function ParentChildDetailModal({
  child,
  onClose,
}: {
  child: ParentChild;
  onClose: () => void;
}) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal__head">
          <h2 className="modal__title">
            {child.first_name} {child.last_name}
          </h2>
          <button type="button" className="modal__close" onClick={onClose} aria-label="Zavřít">
            ×
          </button>
        </div>
        <div className="modal__body">
          <dl className="admin-detail">
            <div className="admin-detail__row">
              <dt className="admin-detail__label">Kategorie</dt>
              <dd className="admin-detail__value">{child.age_group}</dd>
            </div>
            <div className="admin-detail__row">
              <dt className="admin-detail__label">Datum narození</dt>
              <dd className="admin-detail__value">{formatDate(child.birth_date)}</dd>
            </div>
            <div className="admin-detail__row">
              <dt className="admin-detail__label">Rodné číslo</dt>
              <dd className="admin-detail__value">{child.birth_number || "—"}</dd>
            </div>
            <div className="admin-detail__row">
              <dt className="admin-detail__label">Zdravotní pojišťovna</dt>
              <dd className="admin-detail__value">{child.health_insurance || "—"}</dd>
            </div>
            <div className="admin-detail__row">
              <dt className="admin-detail__label">Pobočka</dt>
              <dd className="admin-detail__value">
                {child.branches.map((branch) => branch.name).join(", ") || "—"}
              </dd>
            </div>
          </dl>
        </div>
      </div>
    </div>
  );
}

function ParentChildEditModal({
  child,
  onClose,
  onSaved,
}: {
  child: ParentChild;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [firstName, setFirstName] = useState(child.first_name);
  const [lastName, setLastName] = useState(child.last_name);
  const [birthDate, setBirthDate] = useState(child.birth_date ?? "");
  const [birthNumber, setBirthNumber] = useState(child.birth_number ?? "");
  const [healthInsurance, setHealthInsurance] = useState(child.health_insurance ?? "");

  const derivedAge = useMemo(() => {
    if (!birthDate) return null;
    try {
      return computeAgeGroup(birthDate);
    } catch {
      return null;
    }
  }, [birthDate]);

  const validationError = (() => {
    if (!firstName.trim() || !lastName.trim()) return "Vyplň jméno i příjmení.";
    if (birthNumber.trim() && birthNumberError(birthNumber)) return birthNumberError(birthNumber);
    return null;
  })();

  const save = useMutation({
    mutationFn: () =>
      api.updateParentChild(child.id, {
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        birth_date: birthDate || null,
        birth_number: birthNumber.trim() ? normalizeBirthNumber(birthNumber) : null,
        health_insurance: healthInsurance || null,
      }),
    onSuccess: () => {
      onSaved();
      onClose();
    },
  });

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal__head">
          <h2 className="modal__title">Upravit dítě</h2>
          <button type="button" className="modal__close" onClick={onClose} aria-label="Zavřít">
            ×
          </button>
        </div>
        <div className="modal__body">
          <form
            className="admin-form"
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              if (!validationError) save.mutate();
            }}
          >
            <div className="admin-field">
              <label>Jméno</label>
              <input value={firstName} onChange={(e) => setFirstName(e.target.value)} />
            </div>
            <div className="admin-field">
              <label>Příjmení</label>
              <input value={lastName} onChange={(e) => setLastName(e.target.value)} />
            </div>
            <div className="admin-field">
              <label>Datum narození</label>
              <input type="date" value={birthDate} onChange={(e) => setBirthDate(e.target.value)} />
              {derivedAge && (
                <p className="admin-field__hint">Kategorie po uložení: {derivedAge}</p>
              )}
            </div>
            <div className="admin-field">
              <label>Rodné číslo</label>
              <input
                value={birthNumber}
                onChange={(e) => setBirthNumber(formatBirthNumberInput(e.target.value))}
                placeholder="RRMMDD/XXXX"
                inputMode="numeric"
              />
            </div>
            <div className="admin-field">
              <label>Zdravotní pojišťovna</label>
              <select value={healthInsurance} onChange={(e) => setHealthInsurance(e.target.value)}>
                <option value="">—</option>
                {HEALTH_INSURERS.map((insurer) => (
                  <option key={insurer} value={insurer}>
                    {insurer}
                  </option>
                ))}
              </select>
            </div>
            <p className="admin-field__hint">
              Pobočka: {child.branches.map((branch) => branch.name).join(", ") || "—"} (jen pro čtení)
            </p>
            {validationError && <p className="error-box">{validationError}</p>}
            {save.isError && <p className="error-box">{String(save.error)}</p>}
            <div className="admin-form__actions">
              <button type="button" className="btn btn--ghost" onClick={onClose}>
                Zrušit
              </button>
              <button
                type="submit"
                className="btn btn--primary"
                disabled={!!validationError || save.isPending}
              >
                {save.isPending ? "Ukládám…" : "Uložit"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

export function ParentHomePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { parent, isAuthenticated, isLoading, clearParent } = useParent();
  const [viewing, setViewing] = useState<ParentChild | null>(null);
  const [editing, setEditing] = useState<ParentChild | null>(null);
  const [editingProfile, setEditingProfile] = useState(false);
  const [changePasswordOpen, setChangePasswordOpen] = useState(false);

  const notificationsQuery = useQuery({
    queryKey: parentNotificationsKey(parent?.id),
    queryFn: () => api.notifications("parent"),
    enabled: isAuthenticated && !!parent,
    refetchInterval: 5_000,
    refetchOnWindowFocus: true,
  });
  const notifs = notificationsQuery.data ?? [];
  const unreadBoard = countUnreadBoard(notifs);
  const unreadEvents = countUnreadPlanner(notifs);

  const refreshParent = () => {
    queryClient.invalidateQueries({ queryKey: ["parent-me"] });
  };

  const handlePasswordChanged = useCallback(() => {
    setChangePasswordOpen(false);
    clearParent();
    navigate("/", { replace: true });
  }, [clearParent, navigate]);

  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  if (isLoading || !parent) {
    return (
      <div className="boot-screen">
        <ClubLogo variant="splash" />
        <p className="page-header__sub">Načítám profil…</p>
      </div>
    );
  }

  const logout = () => {
    clearParent();
    navigate("/", { replace: true });
  };

  return (
    <div className="boot-screen app-shell">
      <div className="hub-card">
        <ClubLogo variant="header" />
        <p className="page-header__eyebrow">Rodič</p>
        <h1 className="trainer-picker__title">
          {parent.first_name} {parent.last_name} (rodič)
        </h1>
        <div className="hub-card__profile-actions">
          <button
            type="button"
            className="hub-card__pin-link"
            onClick={() => setEditingProfile(true)}
          >
            Upravit moje údaje
          </button>
          <button
            type="button"
            className="hub-card__pin-link"
            onClick={() => setChangePasswordOpen(true)}
          >
            Změnit heslo
          </button>
        </div>
        <p className="trainer-picker__sub">Moje děti</p>

        <ul className="parent-children">
          {parent.children.length === 0 && (
            <li className="parent-children__empty">
              Zatím nemáš přiřazené žádné dítě.{" "}
              <button type="button" className="btn btn--ghost register-inline-link" onClick={() => navigate("/register")}>
                Registrovat dítě
              </button>
            </li>
          )}
          {parent.children.map((child) => (
            <li key={child.id} className="parent-child">
              <div className="parent-child__row">
                <div>
                  <span className="parent-child__name">
                    {child.first_name} {child.last_name}
                  </span>
                  <span className="parent-child__meta">
                    <span className="parent-child__age">{child.age_group}</span>
                    {child.branches.map((branch) => (
                      <span key={branch.id} className="parent-child__branch">
                        {branch.name}
                      </span>
                    ))}
                  </span>
                </div>
                <div className="parent-child__actions">
                  <button type="button" className="admin-btn-sm" onClick={() => setViewing(child)}>
                    Zobrazit
                  </button>
                  <button type="button" className="admin-btn-sm" onClick={() => setEditing(child)}>
                    Upravit
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>

        <button type="button" className="btn btn--primary auth-back" onClick={() => navigate("/parent/board")}>
          Nástěnka
          {unreadBoard > 0 && <span className="trainer-card__badge">{unreadBoard}</span>}
        </button>
        <button type="button" className="btn btn--primary auth-back" onClick={() => navigate("/parent/attendance")}>
          Přehled docházky
        </button>
        <button type="button" className="btn btn--primary auth-back" onClick={() => navigate("/parent/chat")}>
          Chat
        </button>
        <button type="button" className="btn btn--primary auth-back" onClick={() => navigate("/parent/events")}>
          Akce
          {unreadEvents > 0 && <span className="trainer-card__badge">{unreadEvents}</span>}
        </button>
        <button type="button" className="btn btn--ghost auth-back" onClick={() => navigate("/register")}>
          Registrovat další dítě
        </button>
        <button type="button" className="btn btn--ghost auth-back" onClick={logout}>
          Odhlásit
        </button>
      </div>

      {editingProfile && (
        <ParentProfileEditModal
          parent={parent}
          onClose={() => setEditingProfile(false)}
          onSaved={refreshParent}
        />
      )}
      {viewing && <ParentChildDetailModal child={viewing} onClose={() => setViewing(null)} />}
      {editing && (
        <ParentChildEditModal
          child={editing}
          onClose={() => setEditing(null)}
          onSaved={refreshParent}
        />
      )}
      {changePasswordOpen && (
        <div className="trainer-overlay" role="dialog" aria-modal="true" aria-label="Změnit heslo">
          <div className="trainer-overlay__panel app-shell">
            <ParentChangePasswordForm
              onClose={() => setChangePasswordOpen(false)}
              onSuccess={handlePasswordChanged}
            />
          </div>
        </div>
      )}
    </div>
  );
}
