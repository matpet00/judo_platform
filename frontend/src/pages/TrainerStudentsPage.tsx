import { useEffect, useMemo, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { StudentWithBranches, TrainerStudentRead } from "../api/types";
import { useTrainer } from "../context/TrainerContext";
import "../components/StudentSwipeDeck.css";
import "../pages/AdminPage.css";

function formatDate(value: string | null): string {
  if (!value) return "—";
  const [year, month, day] = value.split("-");
  if (!year || !month || !day) return value;
  return `${day}.${month}.${year}`;
}

function studentToTrainerRead(
  student: StudentWithBranches,
  rosterById: Map<number, TrainerStudentRead>,
): TrainerStudentRead {
  const roster = rosterById.get(student.id);
  if (roster) return roster;
  const branchNames = student.branches.map((branch) => branch.name).join(", ");
  return {
    id: student.id,
    first_name: student.first_name,
    last_name: student.last_name,
    age_group: student.age_group,
    birth_date: student.birth_date ?? null,
    birth_number: student.birth_number ?? null,
    health_insurance: student.health_insurance ?? null,
    branches: student.branches,
    parents: student.parents ?? [],
    training_groups: [],
    is_guest: false,
    home_branch: branchNames || null,
  };
}

function matchesClubStudent(query: string, student: StudentWithBranches): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return false;
  const haystack = [
    student.first_name,
    student.last_name,
    `${student.first_name} ${student.last_name}`,
    `${student.last_name} ${student.first_name}`,
    student.age_group,
    student.birth_number ?? "",
    ...student.branches.map((branch) => branch.name),
  ]
    .join(" ")
    .toLowerCase();
  return haystack.includes(q);
}

function isExternalToRoster(studentId: number, rosterById: Map<number, TrainerStudentRead>): boolean {
  return !rosterById.has(studentId);
}

function StudentDetailModal({
  student,
  onClose,
}: {
  student: TrainerStudentRead;
  onClose: () => void;
}) {
  const title = (
    <>
      {student.first_name} {student.last_name}
      {student.is_guest && <span className="attendance-guest-badge">Host</span>}
    </>
  );
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal__head">
          <h2 className="modal__title">{title}</h2>
          <button type="button" className="modal__close" onClick={onClose} aria-label="Zavřít">
            ×
          </button>
        </div>
        <div className="modal__body">
          <dl className="admin-detail">
            <div className="admin-detail__row">
              <dt className="admin-detail__label">Kategorie</dt>
              <dd className="admin-detail__value">{student.age_group}</dd>
            </div>
            <div className="admin-detail__row">
              <dt className="admin-detail__label">Datum narození</dt>
              <dd className="admin-detail__value">{formatDate(student.birth_date)}</dd>
            </div>
            <div className="admin-detail__row">
              <dt className="admin-detail__label">Rodné číslo</dt>
              <dd className="admin-detail__value">{student.birth_number || "—"}</dd>
            </div>
            <div className="admin-detail__row">
              <dt className="admin-detail__label">Zdravotní pojišťovna</dt>
              <dd className="admin-detail__value">{student.health_insurance || "—"}</dd>
            </div>
            <div className="admin-detail__row">
              <dt className="admin-detail__label">Pobočky</dt>
              <dd className="admin-detail__value">
                {student.branches.map((b) => b.name).join(", ") || "—"}
              </dd>
            </div>
            {student.is_guest && (
              <div className="admin-detail__row">
                <dt className="admin-detail__label">Domovská pobočka</dt>
                <dd className="admin-detail__value">{student.home_branch || "—"}</dd>
              </div>
            )}
            {!student.is_guest && student.training_groups.length === 0 && student.home_branch && (
              <div className="admin-detail__row">
                <dt className="admin-detail__label">Pobočka v klubu</dt>
                <dd className="admin-detail__value">{student.home_branch}</dd>
              </div>
            )}
            {!student.is_guest && student.training_groups.length > 0 && (
              <div className="admin-detail__row">
                <dt className="admin-detail__label">Tréninkové skupiny</dt>
                <dd className="admin-detail__value">{student.training_groups.join(", ") || "—"}</dd>
              </div>
            )}
            <div className="admin-detail__row">
              <dt className="admin-detail__label">Rodiče</dt>
              <dd className="admin-detail__value">
                {student.parents.length
                  ? student.parents
                      .map((p) => `${p.first_name} ${p.last_name} · ${p.email} · ${p.phone}`)
                      .join("; ")
                  : "—"}
              </dd>
            </div>
          </dl>
        </div>
      </div>
    </div>
  );
}

export function TrainerStudentsPage() {
  const { trainer, isAuthenticated, isLoading: trainersLoading } = useTrainer();
  const [branchId, setBranchId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [viewing, setViewing] = useState<TrainerStudentRead | null>(null);

  useEffect(() => {
    if (!trainer || branchId !== null) return;
    if (trainer.branches.length > 0) {
      setBranchId(trainer.branches[0].id);
    }
  }, [trainer, branchId]);

  const studentsQuery = useQuery({
    queryKey: ["trainer-students", trainer?.id, branchId],
    queryFn: () => api.trainerStudents(branchId!),
    enabled: isAuthenticated && branchId !== null,
  });

  const clubStudentsQuery = useQuery({
    queryKey: ["students"],
    queryFn: () => api.students(),
    enabled: isAuthenticated,
  });

  const roster = studentsQuery.data ?? [];
  const rosterById = useMemo(
    () => new Map(roster.map((student) => [student.id, student])),
    [roster],
  );

  const searchQuery = search.trim();
  const searchMatches = useMemo(() => {
    if (!searchQuery) return [];
    return (clubStudentsQuery.data ?? [])
      .filter((student) => matchesClubStudent(searchQuery, student))
      .slice(0, 8);
  }, [clubStudentsQuery.data, searchQuery]);

  if (!trainersLoading && !isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  if (!trainer) {
    return <div className="loading app-shell">Načítám…</div>;
  }

  return (
    <div className="app-shell">
      <header className="page-header">
        <div className="page-header__row">
          <div>
            <p className="page-header__eyebrow">Trenér</p>
            <h1 className="page-header__title">Děti v mé pobočce</h1>
            <p className="page-header__sub">Informace o žácích ze skupin a hostech (jen prohlížení)</p>
          </div>
          <Link className="board-link" to="/">
            Menu
          </Link>
        </div>
      </header>

      {trainer.branches.length > 1 && (
        <label className="notification-field" style={{ marginBottom: 12 }}>
          Pobočka
          <select
            value={branchId ?? ""}
            onChange={(e) => setBranchId(Number(e.target.value))}
          >
            {trainer.branches.map((branch) => (
              <option key={branch.id} value={branch.id}>
                {branch.name}
              </option>
            ))}
          </select>
        </label>
      )}

      <div className="guest-picker">
        <label className="notification-field guest-picker__field">
          Hledat v celém klubu
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Jméno, rodné číslo, pobočka…"
            autoComplete="off"
          />
        </label>
        {searchQuery && (
          <div className="guest-picker__list">
            {clubStudentsQuery.isLoading && <div className="guest-picker__empty">Načítám…</div>}
            {!clubStudentsQuery.isLoading && searchMatches.length === 0 && (
              <div className="guest-picker__empty">Nikdo nenalezen.</div>
            )}
            {searchMatches.map((student) => {
              const external = isExternalToRoster(student.id, rosterById);
              return (
                <button
                  key={student.id}
                  type="button"
                  className="guest-picker__item"
                  onClick={() => {
                    setViewing(studentToTrainerRead(student, rosterById));
                    setSearch("");
                  }}
                >
                  <span className="guest-picker__name">
                    {student.first_name} {student.last_name}
                    {external && <span className="attendance-guest-badge">Jiná pobočka</span>}
                  </span>
                  <span className="guest-picker__meta">
                    {student.age_group}
                    {student.branches.length ? ` · ${student.branches.map((b) => b.name).join(", ")}` : ""}
                    {student.birth_number ? ` · ${student.birth_number}` : ""}
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {studentsQuery.isError && <p className="error-box">{String(studentsQuery.error)}</p>}

      <div className="admin-list" style={{ marginTop: 16 }}>
        {roster.map((student) => (
          <div key={`${student.is_guest ? "guest" : "roster"}-${student.id}`} className="admin-row">
            <div className="admin-row__main">
              <div className="admin-row__title">
                {student.first_name} {student.last_name}
                <span style={{ color: "var(--gold)" }}> · {student.age_group}</span>
                {student.is_guest && <span className="attendance-guest-badge">Host</span>}
              </div>
              <div className="admin-row__sub">
                {student.is_guest
                  ? student.home_branch || "Host z jiné pobočky"
                  : student.training_groups.join(", ") || "Bez skupiny"}
                {student.birth_number ? ` · ${student.birth_number}` : ""}
              </div>
            </div>
            <div className="admin-row__actions">
              <button type="button" className="admin-btn-sm" onClick={() => setViewing(student)}>
                Detail
              </button>
            </div>
          </div>
        ))}
        {roster.length === 0 && !studentsQuery.isLoading && (
          <p className="admin-empty">Žádní žáci pro vybranou pobočku.</p>
        )}
      </div>

      {viewing && <StudentDetailModal student={viewing} onClose={() => setViewing(null)} />}
    </div>
  );
}
