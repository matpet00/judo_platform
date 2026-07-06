import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { GuardianCredentialsRead } from "../api/types";
import { computeAgeGroup, ageGroupHint } from "../lib/ageGroup";
import {
  BIRTH_DATE_HINT,
  BIRTH_DATE_PLACEHOLDER,
  birthDateError,
  birthDateToIso,
  formatBirthDateInput,
} from "../lib/birthDate";
import { formatPhoneInput, phoneError, PHONE_HINT, PHONE_PLACEHOLDER } from "../lib/phone";
import { ClubLogo } from "../components/ClubLogo";
import { useParent } from "../context/ParentContext";

type ChildForm = {
  key: string;
  first_name: string;
  last_name: string;
  birth_date: string;
  branch_id: string;
};

type GuardianForm = {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
};

function emptyChild(): ChildForm {
  return {
    key: crypto.randomUUID(),
    first_name: "",
    last_name: "",
    birth_date: "",
    branch_id: "",
  };
}

function emptyGuardian(): GuardianForm {
  return { first_name: "", last_name: "", email: "", phone: "+" };
}

function GuardianFields({
  title,
  firstName,
  lastName,
  email,
  phone,
  onFirstName,
  onLastName,
  onEmail,
  onPhone,
  disableIdentity,
  onEmailBlur,
  emailHint,
  checkingEmail,
}: {
  title: string;
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  onFirstName: (v: string) => void;
  onLastName: (v: string) => void;
  onEmail: (v: string) => void;
  onPhone: (v: string) => void;
  disableIdentity?: boolean;
  onEmailBlur?: () => void;
  emailHint?: string | null;
  checkingEmail?: boolean;
}) {
  const phoneErr = phone.trim() && phone !== "+" ? phoneError(phone) : null;

  return (
    <fieldset className="register-guardian">
      <legend className="register-section__title">{title}</legend>

      <div className="register-child__grid">
        <label className="notification-field">
          Jméno
          <input value={firstName} onChange={(e) => onFirstName(e.target.value)} disabled={disableIdentity} required />
        </label>
        <label className="notification-field">
          Příjmení
          <input value={lastName} onChange={(e) => onLastName(e.target.value)} disabled={disableIdentity} required />
        </label>
      </div>

      <label className="notification-field">
        E-mail
        <input
          type="email"
          value={email}
          onChange={(e) => onEmail(e.target.value)}
          onBlur={onEmailBlur}
          disabled={disableIdentity}
          required
        />
      </label>
      {checkingEmail && <p className="register-hint">Kontroluji e-mail…</p>}
      {emailHint && <p className="register-hint register-hint--info">{emailHint}</p>}

      <label className="notification-field">
        Telefon
        <input
          type="tel"
          value={phone}
          onChange={(e) => onPhone(formatPhoneInput(e.target.value))}
          onFocus={() => {
            if (!phone) onPhone("+");
          }}
          placeholder={PHONE_PLACEHOLDER}
          required
        />
      </label>
      <p className="register-hint">{PHONE_HINT}</p>
      {phoneErr && <p className="error-box register-age-error">{phoneErr}</p>}
    </fieldset>
  );
}

function ChildFields({
  child,
  index,
  branches,
  canRemove,
  onChange,
  onRemove,
  referenceYear,
}: {
  child: ChildForm;
  index: number;
  branches: { id: number; name: string }[];
  canRemove: boolean;
  onChange: (next: ChildForm) => void;
  onRemove: () => void;
  referenceYear: number;
}) {
  const dateErr = child.birth_date ? birthDateError(child.birth_date) : null;

  const agePreview = useMemo(() => {
    if (dateErr) return null;
    if (!child.birth_date) return null;
    try {
      return computeAgeGroup(birthDateToIso(child.birth_date), referenceYear);
    } catch {
      return null;
    }
  }, [child.birth_date, dateErr, referenceYear]);

  const ageError = useMemo(() => {
    if (!child.birth_date) return null;
    if (dateErr) return dateErr;
    try {
      computeAgeGroup(birthDateToIso(child.birth_date), referenceYear);
      return null;
    } catch (e) {
      return String(e);
    }
  }, [child.birth_date, dateErr, referenceYear]);

  return (
    <fieldset className="register-child">
      <legend className="register-child__legend">
        Dítě {index + 1}
        {canRemove && (
          <button type="button" className="btn btn--ghost register-child__remove" onClick={onRemove}>
            Odebrat
          </button>
        )}
      </legend>

      <div className="register-child__grid">
        <label className="notification-field">
          Jméno
          <input
            value={child.first_name}
            onChange={(e) => onChange({ ...child, first_name: e.target.value })}
            placeholder="Pepa"
            required
          />
        </label>
        <label className="notification-field">
          Příjmení
          <input
            value={child.last_name}
            onChange={(e) => onChange({ ...child, last_name: e.target.value })}
            placeholder="Novák"
            required
          />
        </label>
      </div>

      <label className="notification-field">
        Datum narození
        <input
          type="text"
          inputMode="numeric"
          autoComplete="bday"
          value={child.birth_date}
          onChange={(e) => onChange({ ...child, birth_date: formatBirthDateInput(e.target.value) })}
          placeholder={BIRTH_DATE_PLACEHOLDER}
          required
        />
      </label>
      <p className="register-hint">{BIRTH_DATE_HINT}</p>

      {agePreview && (
        <p className="register-age-preview">
          Věková kategorie: <strong>{agePreview}</strong>
        </p>
      )}
      {ageError && <p className="error-box register-age-error">{ageError}</p>}

      <label className="notification-field">
        Pobočka
        <select
          value={child.branch_id}
          onChange={(e) => onChange({ ...child, branch_id: e.target.value })}
          required
        >
          <option value="">Vyber pobočku</option>
          {branches.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
            </option>
          ))}
        </select>
      </label>
    </fieldset>
  );
}

export function RegisterPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { parent: loggedInParent, isAuthenticated, setParentSession } = useParent();

  const branchesQuery = useQuery({
    queryKey: ["branches"],
    queryFn: () => api.branches(),
  });
  const branches = branchesQuery.data ?? [];

  const [parentFirst, setParentFirst] = useState("");
  const [parentLast, setParentLast] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("+");
  const [showSecondGuardian, setShowSecondGuardian] = useState(false);
  const [secondGuardian, setSecondGuardian] = useState<GuardianForm>(emptyGuardian());
  const [children, setChildren] = useState<ChildForm[]>([emptyChild()]);
  const [emailStatus, setEmailStatus] = useState<{ exists: boolean; has_login: boolean } | null>(null);
  const [checkingEmail, setCheckingEmail] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [createdCredentialSets, setCreatedCredentialSets] = useState<
    { label: string; guardian: GuardianCredentialsRead }[]
  >([]);
  const [pending, setPending] = useState(false);

  const referenceYear = new Date().getFullYear();
  const isExistingParent = emailStatus?.exists === true;

  useEffect(() => {
    if (loggedInParent) {
      setParentFirst(loggedInParent.first_name);
      setParentLast(loggedInParent.last_name);
      setEmail(loggedInParent.email);
      setPhone(loggedInParent.phone || "+");
      setEmailStatus({ exists: true, has_login: !!loggedInParent.username });
    }
  }, [loggedInParent]);

  const checkEmail = useCallback(async (value: string) => {
    const trimmed = value.trim().toLowerCase();
    if (!trimmed.includes("@")) {
      setEmailStatus(null);
      return;
    }
    setCheckingEmail(true);
    try {
      const status = await api.parentEmailStatus(trimmed);
      setEmailStatus(status);
    } catch {
      setEmailStatus(null);
    } finally {
      setCheckingEmail(false);
    }
  }, []);

  const primaryPhoneValid = !phoneError(phone);
  const secondPhoneValid = !showSecondGuardian || !phoneError(secondGuardian.phone);
  const secondGuardianValid =
    !showSecondGuardian ||
    (secondGuardian.first_name.trim() &&
      secondGuardian.last_name.trim() &&
      secondGuardian.email.trim().includes("@") &&
      secondPhoneValid &&
      secondGuardian.email.trim().toLowerCase() !== email.trim().toLowerCase());

  const updateChild = (key: string, next: ChildForm) => {
    setChildren((list) => list.map((c) => (c.key === key ? next : c)));
  };

  const addChild = () => {
    if (children.length >= 5) return;
    setChildren((list) => [...list, emptyChild()]);
  };

  const removeChild = (key: string) => {
    setChildren((list) => list.filter((c) => c.key !== key));
  };

  const validChildren = useMemo(() => {
    return children.every((c) => {
      if (!c.first_name.trim() || !c.last_name.trim() || !c.birth_date || !c.branch_id) return false;
      if (birthDateError(c.birth_date)) return false;
      try {
        computeAgeGroup(birthDateToIso(c.birth_date), referenceYear);
        return true;
      } catch {
        return false;
      }
    });
  }, [children, referenceYear]);

  const canSubmit =
    parentFirst.trim() &&
    parentLast.trim() &&
    email.trim().includes("@") &&
    primaryPhoneValid &&
    validChildren &&
    secondGuardianValid;

  const primaryEmailHint = isExistingParent
    ? `Účet s tímto e-mailem už existuje — přidáme další dítě k tvému účtu.${
        emailStatus?.has_login
          ? " Přihlas se stejným uživatelským jménem jako dříve."
          : " Pokud ještě nemáš přihlášení, vygenerujeme ti ho po odeslání."
      }`
    : "Po registraci klub vygeneruje přihlašovací jméno (3 znaky příjmení + 3 znaky jména) a heslo pro každého zástupce.";

  const submit = async () => {
    setPending(true);
    setError(null);
    setSuccess(null);
    setCreatedCredentialSets([]);
    try {
      const payload = {
        parent_first_name: parentFirst.trim(),
        parent_last_name: parentLast.trim(),
        email: email.trim().toLowerCase(),
        phone: phone.trim(),
        second_guardian: showSecondGuardian
          ? {
              first_name: secondGuardian.first_name.trim(),
              last_name: secondGuardian.last_name.trim(),
              email: secondGuardian.email.trim().toLowerCase(),
              phone: secondGuardian.phone.trim(),
            }
          : null,
        children: children.map((c) => ({
          first_name: c.first_name.trim(),
          last_name: c.last_name.trim(),
          birth_date: birthDateToIso(c.birth_date),
          branch_ids: [Number(c.branch_id)],
        })),
      };

      const result = await api.registerToClub(payload);
      setSuccess(result.message ?? "Registrace proběhla úspěšně.");

      const credentialSets: { label: string; guardian: GuardianCredentialsRead }[] = [];
      if (result.credentials_created && result.username) {
        credentialSets.push({
          label: "1. zákonný zástupce",
          guardian: {
            parent_id: result.parent_id,
            first_name: parentFirst.trim(),
            last_name: parentLast.trim(),
            email: email.trim().toLowerCase(),
            username: result.username,
            password: result.password,
            credentials_created: true,
          },
        });
      }
      if (result.second_guardian) {
        credentialSets.push({
          label: "2. zákonný zástupce",
          guardian: result.second_guardian,
        });
      }
      setCreatedCredentialSets(credentialSets);

      void queryClient.invalidateQueries({ queryKey: ["parent-me"] });

      if (result.access_token && result.parent_id_token) {
        setParentSession(result.parent_id_token, result.access_token);
        if (credentialSets.every((c) => !c.guardian.credentials_created)) {
          setTimeout(() => navigate("/parent", { replace: true }), 1200);
        }
      } else if (isAuthenticated) {
        setTimeout(() => navigate("/parent", { replace: true }), 1500);
      } else if (result.existing_parent) {
        setTimeout(() => navigate("/", { replace: true }), 2500);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="boot-screen app-shell">
      <div className="auth-card register-card">
        <header className="trainer-picker__header">
          <ClubLogo variant="header" />
          <h1 className="trainer-picker__title">Registrace dítěte</h1>
          <p className="trainer-picker__sub">{ageGroupHint()}</p>
        </header>

        <form
          className="auth-form register-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (!pending && canSubmit) void submit();
          }}
        >
          <section className="register-section">
            <GuardianFields
              title="1. zákonný zástupce"
              firstName={parentFirst}
              lastName={parentLast}
              email={email}
              phone={phone}
              onFirstName={setParentFirst}
              onLastName={setParentLast}
              onEmail={setEmail}
              onPhone={setPhone}
              disableIdentity={!!loggedInParent}
              onEmailBlur={() => void checkEmail(email)}
              emailHint={primaryEmailHint}
              checkingEmail={checkingEmail}
            />

            {!showSecondGuardian ? (
              <button
                type="button"
                className="btn btn--ghost register-add-child"
                onClick={() => setShowSecondGuardian(true)}
              >
                + Druhý zákonný zástupce
              </button>
            ) : (
              <>
                <GuardianFields
                  title="2. zákonný zástupce"
                  firstName={secondGuardian.first_name}
                  lastName={secondGuardian.last_name}
                  email={secondGuardian.email}
                  phone={secondGuardian.phone}
                  onFirstName={(v) => setSecondGuardian((g) => ({ ...g, first_name: v }))}
                  onLastName={(v) => setSecondGuardian((g) => ({ ...g, last_name: v }))}
                  onEmail={(v) => setSecondGuardian((g) => ({ ...g, email: v }))}
                  onPhone={(v) => setSecondGuardian((g) => ({ ...g, phone: v }))}
                />
                {secondGuardian.email.trim() &&
                  secondGuardian.email.trim().toLowerCase() === email.trim().toLowerCase() && (
                    <p className="error-box register-age-error">E-mail druhého zástupce musí být jiný.</p>
                  )}
                <button
                  type="button"
                  className="btn btn--ghost register-add-child"
                  onClick={() => {
                    setShowSecondGuardian(false);
                    setSecondGuardian(emptyGuardian());
                  }}
                >
                  Odebrat druhého zástupce
                </button>
              </>
            )}
          </section>

          <section className="register-section">
            <div className="register-section__head">
              <h2 className="register-section__title">Děti</h2>
              <button
                type="button"
                className="btn btn--ghost register-add-child"
                onClick={addChild}
                disabled={children.length >= 5}
              >
                + Další dítě
              </button>
            </div>

            {children.map((child, index) => (
              <ChildFields
                key={child.key}
                child={child}
                index={index}
                branches={branches}
                canRemove={children.length > 1}
                referenceYear={referenceYear}
                onChange={(next) => updateChild(child.key, next)}
                onRemove={() => removeChild(child.key)}
              />
            ))}
          </section>

          {error && <p className="error-box trainer-pin-gate__error">{error}</p>}
          {success && <p className="register-success">{success}</p>}
          {createdCredentialSets.length > 0 && (
            <div className="register-credentials-list">
              {createdCredentialSets.map((entry) => (
                <div key={entry.label} className="register-credentials">
                  <p className="register-credentials__title">{entry.label}</p>
                  <p>
                    Uživatel: <strong>{entry.guardian.username}</strong>
                  </p>
                  {entry.guardian.credentials_created && entry.guardian.password ? (
                    <p>
                      Heslo: <strong>{entry.guardian.password}</strong>
                    </p>
                  ) : (
                    <p className="register-hint">Účet už existuje — použij stávající heslo.</p>
                  )}
                </div>
              ))}
              <p className="register-hint">Ulož si údaje — heslo se v aplikaci znovu nezobrazí.</p>
              <button
                type="button"
                className="btn btn--primary auth-back"
                onClick={() => navigate("/parent", { replace: true })}
              >
                Pokračovat do aplikace
              </button>
            </div>
          )}

          <div className="confirm-card__actions">
            <button type="button" className="btn btn--ghost" disabled={pending} onClick={() => navigate("/")}>
              Zpět
            </button>
            <button type="submit" className="btn btn--primary" disabled={pending || !canSubmit}>
              {pending ? "Odesílám…" : children.length > 1 ? "Registrovat děti" : "Registrovat dítě"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
