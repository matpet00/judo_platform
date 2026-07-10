import { useMemo, useState, type FormEvent, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { ClubLogo } from "../components/ClubLogo";
import {
  ADMIN_CHART_COLORS,
  AdminBarChart,
  AdminDonutChart,
  AdminStackedBar,
  RSVP_CHART_SEGMENTS,
} from "../components/AdminCharts";
import { MonthlyAttendanceReport } from "../components/MonthlyAttendanceReport";
import { useAdmin } from "../context/AdminContext";
import { computeAgeGroup } from "../lib/ageGroup";
import type {
  AgeGroup,
  AdminEventParticipation,
  BranchBrief,
  BranchDetail,
  ParentRow,
  RegistrationRequestDetail,
  RegistrationRequestListItem,
  ResendCredentialsRead,
  RsvpStatus,
  StudentWithBranches,
  Trainer,
} from "../api/types";
import "./AdminPage.css";

type TabId = "dashboard" | "trainers" | "students" | "parents" | "registrations" | "branches" | "attendance" | "events" | "export";

const TABS: { id: TabId; label: string }[] = [
  { id: "dashboard", label: "Přehled" },
  { id: "trainers", label: "Trenéři" },
  { id: "students", label: "Děti" },
  { id: "parents", label: "Rodiče" },
  { id: "registrations", label: "Registrace" },
  { id: "branches", label: "Pobočky" },
  { id: "attendance", label: "Docházka" },
  { id: "events", label: "Akce" },
  { id: "export", label: "Export" },
];

const EVENT_TYPE_LABELS: Record<string, string> = {
  tournament: "Turnaj",
  training: "Trénink",
  meeting: "Schůzka",
  seminar: "Školení",
  other: "Akce",
};

const RSVP_LABELS: Record<RsvpStatus, string> = {
  yes: "Ano",
  no: "Ne",
  maybe: "Možná",
};

const AGE_GROUPS: AgeGroup[] = ["U8", "U10", "U12", "U14", "U16", "U18"];

export function AdminPage() {
  const navigate = useNavigate();
  const { isAuthenticated, logoutAdmin } = useAdmin();
  const [tab, setTab] = useState<TabId>("dashboard");

  if (!isAuthenticated) {
    return <AdminLogin />;
  }

  return (
    <div className="admin-shell">
      <div className="admin-topbar">
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <ClubLogo variant="header" />
          <h1 className="admin-topbar__title">Administrace</h1>
        </div>
        <div className="admin-topbar__actions">
          <button type="button" className="btn btn--ghost" onClick={() => navigate("/")}>
            Menu
          </button>
          <button
            type="button"
            className="btn btn--ghost"
            onClick={() => {
              logoutAdmin();
              navigate("/", { replace: true });
            }}
          >
            Odhlásit
          </button>
        </div>
      </div>

      <div className="admin-tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`admin-tab ${tab === t.id ? "admin-tab--active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "dashboard" && <DashboardTab />}
      {tab === "trainers" && <TrainersTab />}
      {tab === "students" && <StudentsTab />}
      {tab === "parents" && <ParentsTab />}
      {tab === "registrations" && <RegistrationsTab />}
      {tab === "branches" && <BranchesTab />}
      {tab === "attendance" && <MonthlyAttendanceReport role="admin" />}
      {tab === "events" && <EventsTab />}
      {tab === "export" && <ExportTab />}
    </div>
  );
}

function AdminLogin() {
  const navigate = useNavigate();
  const { loginAdmin } = useAdmin();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const login = useMutation({
    mutationFn: () => loginAdmin(username, password),
  });

  return (
    <div className="app-shell">
      <form
        className="admin-login-card"
        onSubmit={(e) => {
          e.preventDefault();
          login.mutate();
        }}
      >
        <ClubLogo variant="header" />
        <h1 className="admin-topbar__title" style={{ textAlign: "center" }}>
          Administrace
        </h1>
        <p className="page-header__sub" style={{ textAlign: "center", margin: 0 }}>
          Zadej administrátorské přihlašovací údaje.
        </p>
        <input
          type="text"
          placeholder="Uživatelské jméno"
          autoFocus
          autoComplete="username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <input
          type="password"
          placeholder="Heslo"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {login.isError && <p className="error-box">{String(login.error)}</p>}
        <div className="confirm-card__actions">
          <button
            type="button"
            className="btn btn--ghost"
            disabled={login.isPending}
            onClick={() => navigate("/")}
          >
            Zpět
          </button>
          <button
            type="submit"
            className="btn btn--primary"
            disabled={login.isPending || !username || !password}
          >
            {login.isPending ? "Přihlašuji…" : "Přihlásit"}
          </button>
        </div>
      </form>
    </div>
  );
}

// --- Shared bits ---

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal__head">
          <h2 className="modal__title">{title}</h2>
          <button type="button" className="modal__close" onClick={onClose} aria-label="Zavřít">
            ×
          </button>
        </div>
        <div className="modal__body">{children}</div>
      </div>
    </div>
  );
}

function SearchBar({
  value,
  onChange,
  onAdd,
  addLabel,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  onAdd?: () => void;
  addLabel?: string;
  placeholder: string;
}) {
  return (
    <div className="admin-toolbar">
      <input
        type="search"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      {onAdd && (
        <button type="button" className="btn btn--primary" onClick={onAdd}>
          {addLabel ?? "Přidat"}
        </button>
      )}
    </div>
  );
}

function BranchChecks({
  branches,
  selected,
  onToggle,
}: {
  branches: BranchBrief[];
  selected: number[];
  onToggle: (id: number) => void;
}) {
  return (
    <div className="admin-checks">
      {branches.map((b) => {
        const on = selected.includes(b.id);
        return (
          <label key={b.id} className={`admin-check ${on ? "admin-check--on" : ""}`}>
            <input type="checkbox" checked={on} onChange={() => onToggle(b.id)} />
            {b.name}
          </label>
        );
      })}
    </div>
  );
}

function matches(query: string, ...fields: (string | null | undefined)[]): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return fields.some((f) => (f ?? "").toLowerCase().includes(q));
}

function AdminDetailModal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <Modal title={title} onClose={onClose}>
      <dl className="admin-detail">{children}</dl>
      <div className="admin-form__actions">
        <button type="button" className="btn btn--primary" onClick={onClose}>
          Zavřít
        </button>
      </div>
    </Modal>
  );
}

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  if (value == null || value === "") return null;
  return (
    <div className="admin-detail__row">
      <dt className="admin-detail__label">{label}</dt>
      <dd className="admin-detail__value">{value}</dd>
    </div>
  );
}

// --- Dashboard ---

function DashboardTab() {
  const stats = useQuery({ queryKey: ["admin", "stats"], queryFn: () => api.adminStats() });

  if (stats.isLoading) return <p className="admin-empty">Načítám…</p>;
  if (stats.isError) return <p className="error-box">{String(stats.error)}</p>;
  const s = stats.data!;

  const cards = [
    { label: "Trenéři", value: s.trainers },
    { label: "Děti", value: s.students },
    { label: "Rodiče", value: s.parents },
    { label: "Pobočky", value: s.branches },
    { label: "Skupiny", value: s.training_groups },
    { label: "Bez přihlášení", value: s.parents_without_login },
    { label: "Čekající registrace", value: s.pending_registrations },
  ];

  const branchChart = s.students_per_branch.map((r) => ({
    label: r.label,
    value: r.count,
    color: ADMIN_CHART_COLORS.gold,
  }));

  const ageChart = s.students_per_age_group.map((r, i) => ({
    label: r.label,
    value: r.count,
    color: [ADMIN_CHART_COLORS.gold, ADMIN_CHART_COLORS.accent, ADMIN_CHART_COLORS.present, ADMIN_CHART_COLORS.cream, ADMIN_CHART_COLORS.muted, ADMIN_CHART_COLORS.absent][i % 6],
  }));

  const memberDonut = [
    { label: "Děti", value: s.students, color: ADMIN_CHART_COLORS.gold },
    { label: "Rodiče", value: s.parents, color: ADMIN_CHART_COLORS.accent },
    { label: "Trenéři", value: s.trainers, color: ADMIN_CHART_COLORS.present },
  ];

  return (
    <div>
      <div className="admin-stats-grid">
        {cards.map((c) => (
          <div key={c.label} className="admin-stat-card">
            <div className="admin-stat-card__num">{c.value}</div>
            <div className="admin-stat-card__label">{c.label}</div>
          </div>
        ))}
      </div>

      <div className="admin-charts-grid">
        <AdminDonutChart title="Členové klubu" items={memberDonut} centerLabel="celkem" />
        <AdminBarChart title="Děti podle poboček" items={branchChart} />
      </div>

      <AdminBarChart title="Děti podle kategorií" items={ageChart} />
    </div>
  );
}

// --- Trainers ---

function TrainersTab() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<Trainer | "new" | null>(null);
  const [viewing, setViewing] = useState<Trainer | null>(null);

  const trainers = useQuery({ queryKey: ["admin", "trainers"], queryFn: () => api.trainers() });
  const branchesQ = useQuery({ queryKey: ["branches"], queryFn: () => api.branches() });

  const del = useMutation({
    mutationFn: (id: number) => api.deleteTrainer(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "trainers"] }),
  });

  const list = (trainers.data ?? []).filter((t) =>
    matches(search, t.first_name, t.last_name, t.branches.map((b) => b.name).join(" ")),
  );

  return (
    <div>
      <SearchBar
        value={search}
        onChange={setSearch}
        onAdd={() => setEditing("new")}
        addLabel="+ Trenér"
        placeholder="Hledat trenéra…"
      />
      {trainers.isError && <p className="error-box">{String(trainers.error)}</p>}
      {del.isError && <p className="error-box">{String(del.error)}</p>}
      <div className="admin-list">
        {list.map((t) => (
          <div key={t.id} className="admin-row">
            <div className="admin-row__main">
              <div className="admin-row__title">
                {t.first_name} {t.last_name}
              </div>
              <div className="admin-row__sub">
                {t.branches.map((b) => b.name).join(", ") || "Bez pobočky"}
              </div>
            </div>
            <div className="admin-row__actions">
              <button type="button" className="admin-btn-sm" onClick={() => setViewing(t)}>
                Zobrazit
              </button>
              <button type="button" className="admin-btn-sm" onClick={() => setEditing(t)}>
                Upravit
              </button>
              <button
                type="button"
                className="admin-btn-sm admin-btn-sm--danger"
                onClick={() => {
                  if (confirm(`Smazat trenéra ${t.first_name} ${t.last_name}?`)) del.mutate(t.id);
                }}
              >
                Smazat
              </button>
            </div>
          </div>
        ))}
        {list.length === 0 && !trainers.isLoading && <p className="admin-empty">Žádní trenéři.</p>}
      </div>

      {viewing && (
        <AdminDetailModal title={`${viewing.first_name} ${viewing.last_name}`} onClose={() => setViewing(null)}>
          <DetailRow label="Jméno" value={`${viewing.first_name} ${viewing.last_name}`} />
          <DetailRow label="Pobočky" value={viewing.branches.map((b) => b.name).join(", ") || "—"} />
        </AdminDetailModal>
      )}

      {editing && (
        <TrainerForm
          trainer={editing === "new" ? null : editing}
          branches={branchesQ.data ?? []}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            qc.invalidateQueries({ queryKey: ["admin", "trainers"] });
          }}
        />
      )}
    </div>
  );
}

function TrainerForm({
  trainer,
  branches,
  onClose,
  onSaved,
}: {
  trainer: Trainer | null;
  branches: BranchBrief[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [firstName, setFirstName] = useState(trainer?.first_name ?? "");
  const [lastName, setLastName] = useState(trainer?.last_name ?? "");
  const [branchIds, setBranchIds] = useState<number[]>(trainer?.branches.map((b) => b.id) ?? []);
  const [pin, setPin] = useState("");

  const save = useMutation({
    mutationFn: async () => {
      if (trainer) {
        await api.updateTrainer(trainer.id, {
          first_name: firstName,
          last_name: lastName,
          branch_ids: branchIds,
          ...(pin ? { pin } : {}),
        });
      } else {
        const created = await api.createTrainer({
          first_name: firstName,
          last_name: lastName,
          branch_ids: branchIds,
        });
        await api.updateTrainer(created.id, { pin });
      }
    },
    onSuccess: onSaved,
  });

  // New trainer: PIN required. Editing: blank keeps the current PIN.
  const pinRequired = !trainer;
  const pinValid = pin === "" ? !pinRequired : pin.length >= 4 && pin.length <= 8;
  const canSave = firstName.trim() && lastName.trim() && branchIds.length > 0 && pinValid;

  return (
    <Modal title={trainer ? "Upravit trenéra" : "Nový trenér"} onClose={onClose}>
      <form
        className="admin-form"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          save.mutate();
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
          <label>Pobočky</label>
          <BranchChecks
            branches={branches}
            selected={branchIds}
            onToggle={(id) =>
              setBranchIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
            }
          />
        </div>
        <div className="admin-field">
          <label>PIN {trainer ? "(přepíše stávající – prázdné = beze změny)" : "(povinný, 4–8 číslic)"}</label>
          <input
            value={pin}
            onChange={(e) => setPin(e.target.value.replace(/\D/g, "").slice(0, 8))}
            placeholder="4–8 číslic"
            inputMode="numeric"
            autoComplete="off"
            maxLength={8}
          />
        </div>
        {!pinValid && (
          <p className="page-header__sub" style={{ margin: 0 }}>
            {pinRequired ? "Zadej PIN (4–8 číslic)." : "PIN musí mít 4–8 číslic."}
          </p>
        )}
        {save.isError && <p className="error-box">{String(save.error)}</p>}
        <div className="admin-form__actions">
          <button type="button" className="btn btn--ghost" onClick={onClose}>
            Zrušit
          </button>
          <button type="submit" className="btn btn--primary" disabled={!canSave || save.isPending}>
            {save.isPending ? "Ukládám…" : "Uložit"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

// --- Students ---

function StudentsTab() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<StudentWithBranches | "new" | null>(null);
  const [viewing, setViewing] = useState<StudentWithBranches | null>(null);

  const students = useQuery({ queryKey: ["admin", "students"], queryFn: () => api.students() });
  const branchesQ = useQuery({ queryKey: ["branches"], queryFn: () => api.branches() });

  const del = useMutation({
    mutationFn: (id: number) => api.deleteStudent(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "students"] }),
  });

  const list = (students.data ?? []).filter((s) =>
    matches(search, s.first_name, s.last_name, s.age_group, s.branches.map((b) => b.name).join(" ")),
  );

  return (
    <div>
      <SearchBar
        value={search}
        onChange={setSearch}
        onAdd={() => setEditing("new")}
        addLabel="+ Dítě"
        placeholder="Hledat dítě…"
      />
      {students.isError && <p className="error-box">{String(students.error)}</p>}
      {del.isError && <p className="error-box">{String(del.error)}</p>}
      <div className="admin-list">
        {list.map((s) => (
          <div key={s.id} className="admin-row">
            <div className="admin-row__main">
              <div className="admin-row__title">
                {s.first_name} {s.last_name} <span style={{ color: "var(--gold)" }}>· {s.age_group}</span>
              </div>
              <div className="admin-row__sub">
                {s.branches.map((b) => b.name).join(", ") || "Bez pobočky"}
              </div>
            </div>
            <div className="admin-row__actions">
              <button type="button" className="admin-btn-sm" onClick={() => setViewing(s)}>
                Zobrazit
              </button>
              <button type="button" className="admin-btn-sm" onClick={() => setEditing(s)}>
                Upravit
              </button>
              <button
                type="button"
                className="admin-btn-sm admin-btn-sm--danger"
                onClick={() => {
                  if (confirm(`Smazat dítě ${s.first_name} ${s.last_name}?`)) del.mutate(s.id);
                }}
              >
                Smazat
              </button>
            </div>
          </div>
        ))}
        {list.length === 0 && !students.isLoading && <p className="admin-empty">Žádné děti.</p>}
      </div>

      {viewing && (
        <AdminDetailModal title={`${viewing.first_name} ${viewing.last_name}`} onClose={() => setViewing(null)}>
          <DetailRow label="Jméno" value={`${viewing.first_name} ${viewing.last_name}`} />
          <DetailRow label="Věková kategorie" value={viewing.age_group} />
          <DetailRow label="Pobočky" value={viewing.branches.map((b) => b.name).join(", ") || "—"} />
          <DetailRow
            label="Rodiče"
            value={
              viewing.parents?.length
                ? viewing.parents.map((p) => `${p.first_name} ${p.last_name} · ${p.email}`).join("; ")
                : "—"
            }
          />
        </AdminDetailModal>
      )}

      {editing && (
        <StudentForm
          student={editing === "new" ? null : editing}
          branches={branchesQ.data ?? []}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            qc.invalidateQueries({ queryKey: ["admin", "students"] });
          }}
        />
      )}
    </div>
  );
}

type GuardianDraft = { first_name: string; last_name: string; email: string; phone: string };

const EMPTY_GUARDIAN: GuardianDraft = { first_name: "", last_name: "", email: "", phone: "" };

function guardianComplete(g: GuardianDraft): boolean {
  return !!(g.first_name.trim() && g.last_name.trim() && g.email.trim() && g.phone.trim());
}

function guardianEmpty(g: GuardianDraft): boolean {
  return !g.first_name.trim() && !g.last_name.trim() && !g.email.trim() && !g.phone.trim();
}

function StudentForm({
  student,
  branches,
  onClose,
  onSaved,
}: {
  student: StudentWithBranches | null;
  branches: BranchBrief[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [firstName, setFirstName] = useState(student?.first_name ?? "");
  const [lastName, setLastName] = useState(student?.last_name ?? "");
  const [ageGroup, setAgeGroup] = useState<AgeGroup>(student?.age_group ?? "U10");
  const [birthDate, setBirthDate] = useState("");
  const [branchIds, setBranchIds] = useState<number[]>(student?.branches.map((b) => b.id) ?? []);

  const initialGuardians: GuardianDraft[] = (student?.parents ?? []).map((p) => ({
    first_name: p.first_name,
    last_name: p.last_name,
    email: p.email,
    phone: p.phone,
  }));
  const [guardians, setGuardians] = useState<GuardianDraft[]>(
    initialGuardians.length > 0 ? initialGuardians : [{ ...EMPTY_GUARDIAN }],
  );

  const derivedAge = useMemo(() => {
    if (!birthDate) return null;
    try {
      return computeAgeGroup(birthDate);
    } catch {
      return null;
    }
  }, [birthDate]);
  const effectiveAge = derivedAge ?? ageGroup;

  const setGuardianField = (idx: number, field: keyof GuardianDraft, value: string) =>
    setGuardians((prev) => prev.map((g, i) => (i === idx ? { ...g, [field]: value } : g)));

  const parentsPayload = guardians.filter((g) => !guardianEmpty(g));
  const emails = parentsPayload.map((g) => g.email.trim().toLowerCase());
  const duplicateEmail = new Set(emails).size !== emails.length;

  const validationError = (() => {
    if (parentsPayload.length === 0) return "Přidej alespoň jednoho zákonného zástupce.";
    if (parentsPayload.some((g) => !guardianComplete(g)))
      return "Vyplň u zástupce jméno, příjmení, e-mail i telefon.";
    if (duplicateEmail) return "Zástupci nemohou mít stejný e-mail.";
    return null;
  })();

  const save = useMutation({
    mutationFn: async () => {
      const parents = parentsPayload.map((g) => ({
        first_name: g.first_name.trim(),
        last_name: g.last_name.trim(),
        email: g.email.trim(),
        phone: g.phone.trim(),
      }));
      if (student) {
        await api.updateStudent(student.id, {
          first_name: firstName,
          last_name: lastName,
          age_group: effectiveAge,
          branch_ids: branchIds,
          parents,
          ...(birthDate ? { birth_date: birthDate } : {}),
        });
      } else {
        await api.createStudent({
          first_name: firstName,
          last_name: lastName,
          age_group: effectiveAge,
          branch_ids: branchIds,
          parents,
          ...(birthDate ? { birth_date: birthDate } : {}),
        });
      }
    },
    onSuccess: onSaved,
  });

  const canSave = firstName.trim() && lastName.trim() && branchIds.length > 0 && !validationError;

  return (
    <Modal title={student ? "Upravit dítě" : "Nové dítě"} onClose={onClose}>
      <form
        className="admin-form"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          if (canSave) save.mutate();
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
          <label>Datum narození (nepovinné, dopočítá kategorii)</label>
          <input type="date" value={birthDate} onChange={(e) => setBirthDate(e.target.value)} />
        </div>
        <div className="admin-field">
          <label>Kategorie {derivedAge ? "(dopočítáno)" : ""}</label>
          <select
            value={effectiveAge}
            disabled={!!derivedAge}
            onChange={(e) => setAgeGroup(e.target.value as AgeGroup)}
          >
            {AGE_GROUPS.map((g) => (
              <option key={g} value={g}>
                {g}
              </option>
            ))}
          </select>
        </div>
        <div className="admin-field">
          <label>Pobočky</label>
          <BranchChecks
            branches={branches}
            selected={branchIds}
            onToggle={(id) =>
              setBranchIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
            }
          />
        </div>

        <div className="admin-field">
          <label>Zákonní zástupci (1–2)</label>
          {guardians.map((g, idx) => (
            <div key={idx} className="admin-guardian">
              <div className="admin-guardian__head">
                <span>{idx + 1}. zástupce</span>
                {guardians.length > 1 && (
                  <button
                    type="button"
                    className="admin-btn-sm admin-btn-sm--danger"
                    onClick={() => setGuardians((prev) => prev.filter((_, i) => i !== idx))}
                  >
                    Odebrat
                  </button>
                )}
              </div>
              <div className="admin-guardian__grid">
                <input
                  placeholder="Jméno"
                  value={g.first_name}
                  onChange={(e) => setGuardianField(idx, "first_name", e.target.value)}
                />
                <input
                  placeholder="Příjmení"
                  value={g.last_name}
                  onChange={(e) => setGuardianField(idx, "last_name", e.target.value)}
                />
                <input
                  type="email"
                  placeholder="E-mail"
                  value={g.email}
                  onChange={(e) => setGuardianField(idx, "email", e.target.value)}
                />
                <input
                  placeholder="Telefon"
                  value={g.phone}
                  onChange={(e) => setGuardianField(idx, "phone", e.target.value)}
                />
              </div>
            </div>
          ))}
          {guardians.length < 2 && (
            <button
              type="button"
              className="admin-btn-sm"
              onClick={() => setGuardians((prev) => [...prev, { ...EMPTY_GUARDIAN }])}
            >
              + Druhý zákonný zástupce
            </button>
          )}
        </div>

        {validationError && <p className="page-header__sub" style={{ margin: 0 }}>{validationError}</p>}
        {save.isError && <p className="error-box">{String(save.error)}</p>}
        <div className="admin-form__actions">
          <button type="button" className="btn btn--ghost" onClick={onClose}>
            Zrušit
          </button>
          <button type="submit" className="btn btn--primary" disabled={!canSave || save.isPending}>
            {save.isPending ? "Ukládám…" : "Uložit"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

// --- Parents ---

function ParentsTab() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<ParentRow | null>(null);
  const [viewing, setViewing] = useState<ParentRow | null>(null);
  const [credentials, setCredentials] = useState<ResendCredentialsRead | null>(null);

  const parents = useQuery({ queryKey: ["admin", "parents"], queryFn: () => api.adminParents() });
  const students = useQuery({ queryKey: ["admin", "students"], queryFn: () => api.students() });

  const del = useMutation({
    mutationFn: (id: number) => api.deleteParent(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "parents"] }),
  });
  const resend = useMutation({
    mutationFn: (id: number) => api.resendParentCredentials(id),
    onSuccess: (data) => setCredentials(data),
  });

  const list = (parents.data ?? []).filter((p) =>
    matches(search, p.first_name, p.last_name, p.email, p.phone),
  );

  const childrenForParent = (parentId: number) =>
    (students.data ?? []).filter((s) => s.parents?.some((par) => par.id === parentId));

  return (
    <div>
      <SearchBar value={search} onChange={setSearch} placeholder="Hledat rodiče…" />
      {parents.isError && <p className="error-box">{String(parents.error)}</p>}
      {del.isError && <p className="error-box">{String(del.error)}</p>}
      {resend.isError && <p className="error-box">{String(resend.error)}</p>}
      <div className="admin-list">
        {list.map((p) => (
          <div key={p.id} className="admin-row">
            <div className="admin-row__main">
              <div className="admin-row__title">
                {p.first_name} {p.last_name}
              </div>
              <div className="admin-row__sub">
                {p.email} · {p.phone}
              </div>
            </div>
            <div className="admin-row__actions">
              <button type="button" className="admin-btn-sm" onClick={() => setViewing(p)}>
                Zobrazit
              </button>
              <button type="button" className="admin-btn-sm" onClick={() => setEditing(p)}>
                Upravit
              </button>
              <button
                type="button"
                className="admin-btn-sm"
                disabled={resend.isPending}
                onClick={() => {
                  if (confirm(`Vygenerovat nové heslo a poslat ${p.first_name} ${p.last_name}?`)) {
                    resend.mutate(p.id);
                  }
                }}
              >
                Znovu poslat údaje
              </button>
              <button
                type="button"
                className="admin-btn-sm admin-btn-sm--danger"
                onClick={() => {
                  if (confirm(`Smazat rodiče ${p.first_name} ${p.last_name}?`)) del.mutate(p.id);
                }}
              >
                Smazat
              </button>
            </div>
          </div>
        ))}
        {list.length === 0 && !parents.isLoading && <p className="admin-empty">Žádní rodiče.</p>}
      </div>

      {viewing && (
        <AdminDetailModal title={`${viewing.first_name} ${viewing.last_name}`} onClose={() => setViewing(null)}>
          <DetailRow label="Jméno" value={`${viewing.first_name} ${viewing.last_name}`} />
          <DetailRow label="E-mail" value={viewing.email} />
          <DetailRow label="Telefon" value={viewing.phone} />
          <DetailRow
            label="Děti"
            value={
              childrenForParent(viewing.id).length
                ? childrenForParent(viewing.id)
                    .map((c) => `${c.first_name} ${c.last_name} (${c.age_group})`)
                    .join("; ")
                : "—"
            }
          />
        </AdminDetailModal>
      )}

      {editing && (
        <ParentForm
          parent={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            qc.invalidateQueries({ queryKey: ["admin", "parents"] });
          }}
        />
      )}

      {credentials && (
        <Modal title="Přihlašovací údaje" onClose={() => setCredentials(null)}>
          <div className="admin-credential-box">
            <p>
              Uživatel: <code>{credentials.username}</code>
            </p>
            <p>
              Heslo: <code>{credentials.password}</code>
            </p>
            <p style={{ marginTop: 10, color: "var(--muted)" }}>
              {credentials.email_sent
                ? `E-mail odeslán na ${credentials.email}.`
                : `E-mail nebyl odeslán: ${credentials.email_error ?? "neznámá chyba"}. Předej údaje ručně.`}
            </p>
          </div>
          <div className="admin-form__actions">
            <button type="button" className="btn btn--primary" onClick={() => setCredentials(null)}>
              Hotovo
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

function ParentForm({
  parent,
  onClose,
  onSaved,
}: {
  parent: ParentRow;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [firstName, setFirstName] = useState(parent.first_name);
  const [lastName, setLastName] = useState(parent.last_name);
  const [email, setEmail] = useState(parent.email);
  const [phone, setPhone] = useState(parent.phone);

  const save = useMutation({
    mutationFn: () =>
      api.updateParent(parent.id, {
        first_name: firstName,
        last_name: lastName,
        email,
        phone,
      }),
    onSuccess: onSaved,
  });

  return (
    <Modal title="Upravit rodiče" onClose={onClose}>
      <form
        className="admin-form"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          save.mutate();
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
          <input value={phone} onChange={(e) => setPhone(e.target.value)} />
        </div>
        {save.isError && <p className="error-box">{String(save.error)}</p>}
        <div className="admin-form__actions">
          <button type="button" className="btn btn--ghost" onClick={onClose}>
            Zrušit
          </button>
          <button type="submit" className="btn btn--primary" disabled={save.isPending}>
            {save.isPending ? "Ukládám…" : "Uložit"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

// --- Registrations ---

const REGISTRATION_STATUS_LABELS: Record<RegistrationRequestListItem["status"], string> = {
  pending: "Čeká",
  approved: "Schváleno",
  rejected: "Zamítnuto",
};

function RegistrationsTab() {
  const qc = useQueryClient();
  const [filter, setFilter] = useState<RegistrationRequestListItem["status"] | "all">("pending");
  const [viewing, setViewing] = useState<RegistrationRequestDetail | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);

  const list = useQuery({
    queryKey: ["admin", "registration-requests", filter],
    queryFn: () =>
      api.adminRegistrationRequests(filter === "all" ? undefined : filter),
  });

  const approve = useMutation({
    mutationFn: (id: number) => api.approveRegistrationRequest(id),
    onSuccess: (result) => {
      setViewing(null);
      setActionError(null);
      qc.invalidateQueries({ queryKey: ["admin", "registration-requests"] });
      qc.invalidateQueries({ queryKey: ["admin", "stats"] });
      qc.invalidateQueries({ queryKey: ["admin", "parents"] });
      qc.invalidateQueries({ queryKey: ["admin", "students"] });
      alert(
        result.credentials_email_sent
          ? "Registrace schválena. Přihlašovací údaje odeslány e-mailem."
          : `Registrace schválena. E-mail neodeslán: ${result.credentials_email_error ?? "neznámá chyba"}.`,
      );
    },
    onError: (e) => setActionError(String(e)),
  });

  const reject = useMutation({
    mutationFn: ({ id, reason }: { id: number; reason: string }) =>
      api.rejectRegistrationRequest(id, reason),
    onSuccess: () => {
      setViewing(null);
      setRejectReason("");
      setActionError(null);
      qc.invalidateQueries({ queryKey: ["admin", "registration-requests"] });
      qc.invalidateQueries({ queryKey: ["admin", "stats"] });
    },
    onError: (e) => setActionError(String(e)),
  });

  const openDetail = async (id: number) => {
    setActionError(null);
    setRejectReason("");
    try {
      const detail = await api.adminRegistrationRequest(id);
      setViewing(detail);
    } catch (e) {
      setActionError(String(e));
    }
  };

  const rows = list.data ?? [];

  return (
    <div>
      <div className="admin-toolbar">
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value as RegistrationRequestListItem["status"] | "all")}
        >
          <option value="pending">Čekající</option>
          <option value="approved">Schválené</option>
          <option value="rejected">Zamítnuté</option>
          <option value="all">Vše</option>
        </select>
      </div>

      {list.isError && <p className="error-box">{String(list.error)}</p>}
      {actionError && <p className="error-box">{actionError}</p>}

      <div className="admin-list">
        {rows.map((row) => (
          <div key={row.id} className="admin-list__row">
            <div>
              <strong>
                {row.parent_first_name} {row.parent_last_name}
              </strong>
              <div className="admin-list__sub">
                {row.parent_email} · {row.children_count} dětí ·{" "}
                {REGISTRATION_STATUS_LABELS[row.status]}
              </div>
            </div>
            <button type="button" className="btn btn--ghost" onClick={() => void openDetail(row.id)}>
              Detail
            </button>
          </div>
        ))}
        {rows.length === 0 && !list.isLoading && <p className="admin-empty">Žádné registrace.</p>}
      </div>

      {viewing && (
        <AdminDetailModal title={`Registrace #${viewing.id}`} onClose={() => setViewing(null)}>
          <DetailRow label="Stav" value={REGISTRATION_STATUS_LABELS[viewing.status]} />
          <DetailRow label="Rodič" value={`${viewing.parent_first_name} ${viewing.parent_last_name}`} />
          <DetailRow label="E-mail" value={viewing.parent_email} />
          <DetailRow label="Telefon" value={viewing.parent_phone} />
          <DetailRow
            label="Děti"
            value={viewing.children.map(
              (c) =>
                `${c.first_name} ${c.last_name} (${c.age_group}, ${c.branch_names.join(", ")}, ${c.birth_date})`,
            ).join("; ")}
          />
          {viewing.second_guardian && (
            <DetailRow
              label="2. zástupce"
              value={`${viewing.second_guardian.first_name} ${viewing.second_guardian.last_name}, ${viewing.second_guardian.email}`}
            />
          )}
          {viewing.rejection_reason && <DetailRow label="Důvod zamítnutí" value={viewing.rejection_reason} />}
          {viewing.status === "pending" && (
            <div style={{ marginTop: 16 }}>
              <div className="admin-field">
                <label>Důvod zamítnutí (povinný při zamítnutí)</label>
                <textarea
                  rows={3}
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  placeholder="Např. špatná pobočka, neúplné údaje…"
                />
              </div>
              <div className="admin-form__actions">
                <button
                  type="button"
                  className="btn btn--primary"
                  disabled={approve.isPending}
                  onClick={() => approve.mutate(viewing.id)}
                >
                  {approve.isPending ? "Schvaluji…" : "Schválit"}
                </button>
                <button
                  type="button"
                  className="btn btn--ghost"
                  disabled={reject.isPending || !rejectReason.trim()}
                  onClick={() => reject.mutate({ id: viewing.id, reason: rejectReason.trim() })}
                >
                  {reject.isPending ? "Zamítám…" : "Zamítnout"}
                </button>
              </div>
            </div>
          )}
        </AdminDetailModal>
      )}
    </div>
  );
}

// --- Branches ---

function BranchesTab() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<BranchBrief | "new" | null>(null);
  const [viewing, setViewing] = useState<BranchDetail | null>(null);

  const branches = useQuery({ queryKey: ["branches"], queryFn: () => api.branches() });
  const del = useMutation({
    mutationFn: (id: number) => api.deleteBranch(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["branches"] }),
  });

  const list = (branches.data ?? []).filter((b) => matches(search, b.name, b.address));

  return (
    <div>
      <SearchBar
        value={search}
        onChange={setSearch}
        onAdd={() => setEditing("new")}
        addLabel="+ Pobočka"
        placeholder="Hledat pobočku…"
      />
      {branches.isError && <p className="error-box">{String(branches.error)}</p>}
      {del.isError && <p className="error-box">{String(del.error)}</p>}
      <div className="admin-list">
        {list.map((b) => (
          <div key={b.id} className="admin-row">
            <div className="admin-row__main">
              <div className="admin-row__title">{b.name}</div>
              <div className="admin-row__sub">{b.address}</div>
            </div>
            <div className="admin-row__actions">
              <button
                type="button"
                className="admin-btn-sm"
                onClick={() => setViewing(branches.data?.find((x) => x.id === b.id) ?? b)}
              >
                Zobrazit
              </button>
              <button type="button" className="admin-btn-sm" onClick={() => setEditing(b)}>
                Upravit
              </button>
              <button
                type="button"
                className="admin-btn-sm admin-btn-sm--danger"
                onClick={() => {
                  if (confirm(`Smazat pobočku ${b.name}?`)) del.mutate(b.id);
                }}
              >
                Smazat
              </button>
            </div>
          </div>
        ))}
        {list.length === 0 && !branches.isLoading && <p className="admin-empty">Žádné pobočky.</p>}
      </div>

      {viewing && (
        <AdminDetailModal title={viewing.name} onClose={() => setViewing(null)}>
          <DetailRow label="Název" value={viewing.name} />
          <DetailRow label="Adresa" value={viewing.address} />
          <DetailRow
            label="Trenéři"
            value={
              viewing.trainers?.length
                ? viewing.trainers.map((t) => `${t.first_name} ${t.last_name}`).join(", ")
                : "—"
            }
          />
          <DetailRow
            label="Děti"
            value={
              viewing.students?.length
                ? viewing.students.map((s) => `${s.first_name} ${s.last_name} (${s.age_group})`).join(", ")
                : "—"
            }
          />
        </AdminDetailModal>
      )}

      {editing && (
        <BranchForm
          branch={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            qc.invalidateQueries({ queryKey: ["branches"] });
          }}
        />
      )}
    </div>
  );
}

function BranchForm({
  branch,
  onClose,
  onSaved,
}: {
  branch: BranchBrief | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(branch?.name ?? "");
  const [address, setAddress] = useState(branch?.address ?? "");

  const save = useMutation({
    mutationFn: () =>
      branch ? api.updateBranch(branch.id, { name, address }) : api.createBranch({ name, address }),
    onSuccess: onSaved,
  });

  const canSave = name.trim() && address.trim();

  return (
    <Modal title={branch ? "Upravit pobočku" : "Nová pobočka"} onClose={onClose}>
      <form
        className="admin-form"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <div className="admin-field">
          <label>Název</label>
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="admin-field">
          <label>Adresa</label>
          <input value={address} onChange={(e) => setAddress(e.target.value)} />
        </div>
        {save.isError && <p className="error-box">{String(save.error)}</p>}
        <div className="admin-form__actions">
          <button type="button" className="btn btn--ghost" onClick={onClose}>
            Zrušit
          </button>
          <button type="submit" className="btn btn--primary" disabled={!canSave || save.isPending}>
            {save.isPending ? "Ukládám…" : "Uložit"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

// --- Events ---

function EventsTab() {
  const now = new Date();
  const defaultMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  const [month, setMonth] = useState(defaultMonth);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const events = useQuery({
    queryKey: ["admin", "event-participation", month],
    queryFn: () => api.adminEventParticipation(month),
    enabled: /^\d{4}-\d{2}$/.test(month),
  });

  const download = useMutation({
    mutationFn: () => api.downloadEventParticipationCsv(month),
  });

  const list = events.data ?? [];

  const monthTotals = list.reduce(
    (acc, e) => ({
      yes: acc.yes + e.yes_count,
      maybe: acc.maybe + e.maybe_count,
      no: acc.no + e.no_count,
      trainerYes: acc.trainerYes + e.trainer_yes,
      studentYes: acc.studentYes + e.student_yes,
    }),
    { yes: 0, maybe: 0, no: 0, trainerYes: 0, studentYes: 0 },
  );

  return (
    <div>
      <div className="admin-form" style={{ maxWidth: 520, marginBottom: 16 }}>
        <div className="admin-section-title">Účast na akcích</div>
        <p className="page-header__sub" style={{ margin: "0 0 12px" }}>
          Přehled potvrzení účasti (RSVP) trenérů a dětí na akcích v kalendáři.
        </p>
        <div className="admin-guardian__grid">
          <div className="admin-field">
            <label>Měsíc</label>
            <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} />
          </div>
        </div>
        <div className="admin-form__actions">
          <button
            type="button"
            className="btn btn--primary"
            disabled={!month || download.isPending}
            onClick={() => download.mutate()}
          >
            {download.isPending ? "Stahuji…" : "Export CSV"}
          </button>
        </div>
        {download.isError && <p className="error-box">{String(download.error)}</p>}
      </div>

      {events.isLoading && <p className="admin-empty">Načítám akce…</p>}
      {events.isError && <p className="error-box">{String(events.error)}</p>}
      {!events.isLoading && list.length === 0 && (
        <p className="admin-empty">V tomto měsíci nejsou žádné akce.</p>
      )}

      {list.length > 0 && (
        <div className="admin-event-chart-block">
          <div className="admin-charts-grid">
            <div className="admin-chart">
              <div className="admin-chart__title">Účast za měsíc (všechny akce)</div>
              <AdminStackedBar
                segments={RSVP_CHART_SEGMENTS(monthTotals.yes, monthTotals.maybe, monthTotals.no)}
                showLegend
              />
              <p className="admin-row__sub" style={{ margin: "10px 0 0" }}>
                Potvrzeno ano: {monthTotals.trainerYes} trenérů, {monthTotals.studentYes} dětí
              </p>
            </div>
            <AdminBarChart
              title="Potvrzená účast po akcích"
              items={list.map((e) => ({
                label: e.title,
                value: e.yes_count,
                color: ADMIN_CHART_COLORS.present,
              }))}
            />
          </div>
        </div>
      )}

      <div className="admin-list">
        {list.map((event) => {
          const when = new Date(event.starts_at).toLocaleString("cs-CZ", {
            day: "numeric",
            month: "long",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          });
          const expanded = expandedId === event.event_id;
          return (
            <div key={event.event_id} className="admin-row" style={{ flexDirection: "column", alignItems: "stretch" }}>
              <div style={{ display: "flex", gap: 12, alignItems: "flex-start", width: "100%" }}>
                <div className="admin-row__main">
                  <div className="admin-row__title">{event.title}</div>
                  <div className="admin-row__sub">
                    {when}
                    {event.location ? ` · ${event.location}` : ""}
                    {" · "}
                    {EVENT_TYPE_LABELS[event.event_type] ?? event.event_type}
                  </div>
                  <div className="admin-row__sub">
                    Účast: {event.yes_count} ano ({event.trainer_yes} trenérů, {event.student_yes} dětí)
                    {event.maybe_count > 0 ? ` · ${event.maybe_count} možná` : ""}
                    {event.no_count > 0 ? ` · ${event.no_count} ne` : ""}
                  </div>
                  <div className="admin-event-row-chart">
                    <AdminStackedBar segments={RSVP_CHART_SEGMENTS(event.yes_count, event.maybe_count, event.no_count)} />
                  </div>
                </div>
                <div className="admin-row__actions">
                  <button
                    type="button"
                    className="admin-btn-sm"
                    onClick={() => setExpandedId(expanded ? null : event.event_id)}
                  >
                    {expanded ? "Skrýt" : "Účastníci"}
                  </button>
                </div>
              </div>
              {expanded && <EventParticipantsTable event={event} />}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function EventParticipantsTable({ event }: { event: AdminEventParticipation }) {
  if (event.participants.length === 0) {
    return <p className="admin-empty" style={{ margin: "12px 0 0" }}>Zatím nikdo nepotvrdil účast.</p>;
  }

  return (
    <table className="admin-mini-table" style={{ marginTop: 12 }}>
      <thead>
        <tr>
          <th>Role</th>
          <th>Jméno</th>
          <th>Kategorie</th>
          <th>Rodič</th>
          <th>Účast</th>
        </tr>
      </thead>
      <tbody>
        {event.participants.map((p) => (
          <tr key={`${p.kind}-${p.person_id}`}>
            <td>{p.kind === "trainer" ? "Trenér" : "Dítě"}</td>
            <td>{p.name}</td>
            <td>{p.age_group ?? "—"}</td>
            <td>{p.parent_name ?? "—"}</td>
            <td>{RSVP_LABELS[p.status]}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// --- Export ---

function ExportTab() {
  const now = new Date();
  const defaultMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  const [month, setMonth] = useState(defaultMonth);
  const [branchId, setBranchId] = useState<number | "">("");

  const branches = useQuery({ queryKey: ["branches"], queryFn: () => api.branches() });
  const downloadTraining = useMutation({
    mutationFn: () => api.downloadAttendanceCsv(month, branchId === "" ? undefined : branchId),
  });
  const downloadEvents = useMutation({
    mutationFn: () => api.downloadEventParticipationCsv(month),
  });

  return (
    <div className="admin-form" style={{ maxWidth: 480 }}>
      <div className="admin-section-title">Export docházky na trénincích</div>
      <div className="admin-field">
        <label>Měsíc</label>
        <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} />
      </div>
      <div className="admin-field">
        <label>Pobočka</label>
        <select
          value={branchId}
          onChange={(e) => setBranchId(e.target.value === "" ? "" : Number(e.target.value))}
        >
          <option value="">Všechny pobočky</option>
          {(branches.data ?? []).map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
            </option>
          ))}
        </select>
      </div>
      {downloadTraining.isError && <p className="error-box">{String(downloadTraining.error)}</p>}
      <div className="admin-form__actions">
        <button
          type="button"
          className="btn btn--primary"
          disabled={!month || downloadTraining.isPending}
          onClick={() => downloadTraining.mutate()}
        >
          {downloadTraining.isPending ? "Stahuji…" : "Stáhnout CSV tréninků"}
        </button>
      </div>

      <div className="admin-section-title" style={{ marginTop: 28 }}>Export účasti na akcích</div>
      <p className="page-header__sub" style={{ margin: "0 0 12px" }}>
        Potvrzení účasti trenérů a dětí (RSVP) za vybraný měsíc.
      </p>
      {downloadEvents.isError && <p className="error-box">{String(downloadEvents.error)}</p>}
      <div className="admin-form__actions">
        <button
          type="button"
          className="btn btn--primary"
          disabled={!month || downloadEvents.isPending}
          onClick={() => downloadEvents.mutate()}
        >
          {downloadEvents.isPending ? "Stahuji…" : "Stáhnout CSV akcí"}
        </button>
      </div>
    </div>
  );
}
