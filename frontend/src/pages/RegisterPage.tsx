import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { RegistrationStatusRead } from "../api/types";
import { computeAgeGroup, ageGroupHint, ageGroupLabel, isAdultAgeGroup } from "../lib/ageGroup";
import type { AgeGroup } from "../api/types";
import {
  BIRTH_DATE_HINT,
  BIRTH_DATE_PLACEHOLDER,
  birthDateError,
  birthDateToIso,
  formatBirthDateInput,
} from "../lib/birthDate";
import {
  BIRTH_NUMBER_HINT,
  BIRTH_NUMBER_PLACEHOLDER,
  birthNumberError,
  formatBirthNumberInput,
  normalizeBirthNumber,
} from "../lib/birthNumber";
import { HEALTH_INSURERS } from "../lib/healthInsurers";
import { formatPhoneInput, phoneError, PHONE_HINT, PHONE_PLACEHOLDER } from "../lib/phone";
import { ClubLogo } from "../components/ClubLogo";
import { useParent } from "../context/ParentContext";

type ChildForm = {
  key: string;
  first_name: string;
  last_name: string;
  birth_date: string;
  birth_number: string;
  health_insurance: string;
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
    birth_number: "",
    health_insurance: "",
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
  emailHint,
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
  emailHint?: string | null;
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
          disabled={disableIdentity}
          required
        />
      </label>
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
  isAdult,
}: {
  child: ChildForm;
  index: number;
  branches: { id: number; name: string }[];
  canRemove: boolean;
  onChange: (next: ChildForm) => void;
  onRemove: () => void;
  referenceYear: number;
  isAdult: boolean;
}) {
  const dateErr = child.birth_date ? birthDateError(child.birth_date) : null;
  const birthNumberErr = child.birth_number ? birthNumberError(child.birth_number) : null;

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
        {isAdult ? `Sportovec ${index + 1}` : `Dítě ${index + 1}`}
        {canRemove && (
          <button type="button" className="btn btn--ghost register-child__remove" onClick={onRemove}>
            Odebrat
          </button>
        )}
      </legend>

      {isAdult && (
        <p className="register-hint register-hint--info">
          Plnoletý sportovec: zákonný zástupce jsi ty sám/sama — jméno můžeš mít stejné jako u účtu výše.
        </p>
      )}

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

      <label className="notification-field">
        Rodné číslo
        <input
          type="text"
          inputMode="numeric"
          value={child.birth_number}
          onChange={(e) => onChange({ ...child, birth_number: formatBirthNumberInput(e.target.value) })}
          placeholder={BIRTH_NUMBER_PLACEHOLDER}
          required
        />
      </label>
      <p className="register-hint">{BIRTH_NUMBER_HINT}</p>
      {birthNumberErr && <p className="error-box register-age-error">{birthNumberErr}</p>}

      <label className="notification-field">
        Zdravotní pojišťovna
        <select
          value={child.health_insurance}
          onChange={(e) => onChange({ ...child, health_insurance: e.target.value })}
          required
        >
          <option value="">Vyber pojišťovnu</option>
          {HEALTH_INSURERS.map((insurer) => (
            <option key={insurer} value={insurer}>
              {insurer}
            </option>
          ))}
        </select>
      </label>

      {agePreview && (
        <p className="register-age-preview">
          Věková kategorie: <strong>{ageGroupLabel(agePreview)}</strong>
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

function childAgeGroup(child: ChildForm, referenceYear: number): AgeGroup | null {
  if (!child.birth_date || birthDateError(child.birth_date)) return null;
  try {
    return computeAgeGroup(birthDateToIso(child.birth_date), referenceYear);
  } catch {
    return null;
  }
}

export function RegisterPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { parent: loggedInParent } = useParent();

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
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [statusEmail, setStatusEmail] = useState("");
  const [statusResult, setStatusResult] = useState<RegistrationStatusRead | null>(null);
  const [statusPending, setStatusPending] = useState(false);
  const [pending, setPending] = useState(false);
  const [privacyAccepted, setPrivacyAccepted] = useState(false);

  const referenceYear = new Date().getFullYear();

  useEffect(() => {
    if (loggedInParent) {
      setParentFirst(loggedInParent.first_name);
      setParentLast(loggedInParent.last_name);
      setEmail(loggedInParent.email);
      setPhone(loggedInParent.phone || "+");
    }
  }, [loggedInParent]);

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
    setChildren((list) =>
      list.map((c) => {
        if (c.key !== key) return c;
        const group = childAgeGroup(next, referenceYear);
        if (group && isAdultAgeGroup(group) && !next.first_name.trim() && !next.last_name.trim()) {
          return {
            ...next,
            first_name: parentFirst.trim(),
            last_name: parentLast.trim(),
          };
        }
        return next;
      }),
    );
  };

  const childGroups = useMemo(
    () => children.map((c) => childAgeGroup(c, referenceYear)),
    [children, referenceYear],
  );
  const hasAdultAthlete = childGroups.some((g) => g != null && isAdultAgeGroup(g));
  const allAdultAthletes =
    childGroups.length > 0 && childGroups.every((g) => g != null && isAdultAgeGroup(g));

  useEffect(() => {
    if (!allAdultAthletes) return;
    setShowSecondGuardian(false);
    setSecondGuardian(emptyGuardian());
  }, [allAdultAthletes]);

  const athletesSectionTitle = hasAdultAthlete ? "Sportovci" : "Děti";
  const pageTitle = allAdultAthletes
    ? children.length > 1
      ? "Registrace sportovců"
      : "Registrace sportovce"
    : children.length > 1
      ? "Registrace dětí"
      : "Registrace dítěte";
  const guardianTitle = allAdultAthletes ? "Účet (zákonný zástupce = ty)" : "1. zákonný zástupce";
  const consentText = allAdultAthletes
    ? "Potvrzuji, že jsem plnoletý/á a registruji sebe (zákonný zástupce = já), že údaje jsou pravdivé, a že jsem se seznámil(a) se"
    : hasAdultAthlete
      ? "Potvrzuji, že jsem zákonný zástupce uvedených sportovců (u plnoletých i sebe), že údaje jsou pravdivé, a že jsem se seznámil(a) se"
      : "Potvrzuji, že jsem zákonný zástupce uvedeného dítěte / dětí, že údaje jsou pravdivé, a že jsem se seznámil(a) se";
  const submitLabel = allAdultAthletes
    ? children.length > 1
      ? "Registrovat sportovce"
      : "Registrovat sebe"
    : children.length > 1
      ? "Registrovat děti"
      : "Registrovat dítě";

  const addChild = () => {
    if (children.length >= 5) return;
    setChildren((list) => [...list, emptyChild()]);
  };

  const removeChild = (key: string) => {
    setChildren((list) => list.filter((c) => c.key !== key));
  };

  const validChildren = useMemo(() => {
    const birthNumbers = children.map((c) => normalizeBirthNumber(c.birth_number)).filter(Boolean);
    if (birthNumbers.length !== new Set(birthNumbers).size) return false;

    return children.every((c) => {
      if (
        !c.first_name.trim() ||
        !c.last_name.trim() ||
        !c.birth_date ||
        !c.birth_number ||
        !c.health_insurance ||
        !c.branch_id
      ) {
        return false;
      }
      if (birthDateError(c.birth_date)) return false;
      if (birthNumberError(c.birth_number)) return false;
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
    secondGuardianValid &&
    privacyAccepted;

  const primaryEmailHint = loggedInParent
    ? "Po schválení klubem přidáme další dítě k vašemu účtu."
    : "Po schválení registrace klubem vám e-mailem pošleme přihlašovací údaje. Pokud u nás už máte účet se stejným e-mailem, nové dítě připojíme k němu.";

  const checkRegistrationStatus = async (value?: string) => {
    const trimmed = (value ?? statusEmail).trim().toLowerCase();
    if (!trimmed.includes("@")) return;
    setStatusPending(true);
    setStatusResult(null);
    try {
      const result = await api.registrationStatus(trimmed);
      setStatusResult(result);
      setStatusEmail(trimmed);
    } catch (e) {
      setError(String(e));
    } finally {
      setStatusPending(false);
    }
  };

  const submit = async () => {
    setPending(true);
    setError(null);
    setSuccess(null);
    setSubmitted(false);
    setStatusResult(null);
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
          birth_number: normalizeBirthNumber(c.birth_number),
          health_insurance: c.health_insurance,
          branch_ids: [Number(c.branch_id)],
        })),
      };

      const result = await api.registerToClub(payload);
      const submittedEmail = email.trim().toLowerCase();
      setSuccess(result.message ?? "Registrace přijata.");
      setSubmitted(true);
      setStatusEmail(submittedEmail);
      void queryClient.invalidateQueries({ queryKey: ["parent-me"] });
      void checkRegistrationStatus(submittedEmail);
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
          <h1 className="trainer-picker__title">{pageTitle}</h1>
          <p className="trainer-picker__sub">{ageGroupHint()}</p>
        </header>

        <form
          className="auth-form register-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (!pending && !submitted && canSubmit) void submit();
          }}
        >
          {submitted ? (
            <section className="register-section">
              <p className="register-success">{success}</p>
              <p className="register-hint">
                Klub registraci zkontroluje. Přihlašovací údaje dostanete e-mailem až po schválení.
              </p>
              <div className="register-status-check">
                <label>
                  Zkontrolovat stav podle e-mailu
                  <input
                    value={statusEmail}
                    onChange={(e) => setStatusEmail(e.target.value)}
                    placeholder="vas@email.cz"
                    type="email"
                  />
                </label>
                <button
                  type="button"
                  className="btn btn--ghost"
                  disabled={statusPending || !statusEmail.trim().includes("@")}
                  onClick={() => void checkRegistrationStatus()}
                >
                  {statusPending ? "Kontroluji…" : "Zkontrolovat stav"}
                </button>
                {statusResult && (
                  <div className="register-status-result">
                    <p>{statusResult.message}</p>
                    {statusResult.status === "rejected" && statusResult.rejection_reason && (
                      <p className="error-box">{statusResult.rejection_reason}</p>
                    )}
                  </div>
                )}
              </div>
              <div className="confirm-card__actions">
                <button type="button" className="btn btn--ghost" onClick={() => navigate("/")}>
                  Zpět na úvod
                </button>
                <button
                  type="button"
                  className="btn btn--primary"
                  onClick={() => {
                    setSubmitted(false);
                    setSuccess(null);
                    setStatusResult(null);
                    setPrivacyAccepted(false);
                  }}
                >
                  Nová registrace
                </button>
              </div>
            </section>
          ) : (
            <>
          <section className="register-section">
            <GuardianFields
              title={guardianTitle}
              firstName={parentFirst}
              lastName={parentLast}
              email={email}
              phone={phone}
              onFirstName={setParentFirst}
              onLastName={setParentLast}
              onEmail={setEmail}
              onPhone={setPhone}
              disableIdentity={!!loggedInParent}
              emailHint={primaryEmailHint}
            />

            {!allAdultAthletes && !showSecondGuardian ? (
              <button
                type="button"
                className="btn register-add-action register-add-action--block"
                onClick={() => setShowSecondGuardian(true)}
              >
                + Druhý zákonný zástupce
              </button>
            ) : !allAdultAthletes && showSecondGuardian ? (
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
                  className="btn btn--ghost register-remove-action"
                  onClick={() => {
                    setShowSecondGuardian(false);
                    setSecondGuardian(emptyGuardian());
                  }}
                >
                  Odebrat druhého zástupce
                </button>
              </>
            ) : null}
          </section>

          <section className="register-section">
            <div className="register-section__head">
              <h2 className="register-section__title">{athletesSectionTitle}</h2>
              <button
                type="button"
                className="btn register-add-action"
                onClick={addChild}
                disabled={children.length >= 5}
              >
                {hasAdultAthlete ? "+ Další sportovec" : "+ Další dítě"}
              </button>
            </div>

            {children.map((child, index) => {
              const group = childGroups[index];
              return (
                <ChildFields
                  key={child.key}
                  child={child}
                  index={index}
                  branches={branches}
                  canRemove={children.length > 1}
                  referenceYear={referenceYear}
                  isAdult={group != null && isAdultAgeGroup(group)}
                  onChange={(next) => updateChild(child.key, next)}
                  onRemove={() => removeChild(child.key)}
                />
              );
            })}
          </section>

          {error && <p className="error-box trainer-pin-gate__error">{error}</p>}

          <label className="register-consent">
            <input
              type="checkbox"
              checked={privacyAccepted}
              onChange={(e) => setPrivacyAccepted(e.target.checked)}
              required
            />
            <span>
              {consentText}{" "}
              <Link to="/privacy" className="register-inline-link" target="_blank" rel="noreferrer">
                Zásadami ochrany osobních údajů
              </Link>{" "}
              a souhlasím se zpracováním osobních údajů v rozsahu tam uvedeném.
            </span>
          </label>

          <div className="confirm-card__actions">
            <button type="button" className="btn btn--ghost" disabled={pending} onClick={() => navigate("/")}>
              Zpět
            </button>
            <button type="submit" className="btn btn--primary" disabled={pending || !canSubmit}>
              {pending ? "Odesílám…" : submitLabel}
            </button>
          </div>
            </>
          )}

          {!submitted && (
            <section className="register-section register-status-panel">
              <h2 className="register-section__title">Stav registrace</h2>
              <p className="register-hint">Už jsi odeslal/a žádost? Zkontroluj stav podle e-mailu.</p>
              <div className="register-status-check">
                <input
                  value={statusEmail}
                  onChange={(e) => setStatusEmail(e.target.value)}
                  placeholder="vas@email.cz"
                  type="email"
                />
                <button
                  type="button"
                  className="btn btn--ghost"
                  disabled={statusPending || !statusEmail.trim().includes("@")}
                  onClick={() => void checkRegistrationStatus()}
                >
                  {statusPending ? "Kontroluji…" : "Zkontrolovat stav"}
                </button>
              </div>
              {statusResult && (
                <div className="register-status-result">
                  <p>{statusResult.message}</p>
                  {statusResult.status === "rejected" && statusResult.rejection_reason && (
                    <p className="error-box">{statusResult.rejection_reason}</p>
                  )}
                </div>
              )}
            </section>
          )}
        </form>
      </div>
    </div>
  );
}
