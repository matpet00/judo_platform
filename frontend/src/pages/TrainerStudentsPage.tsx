import { useEffect, useMemo, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { TrainerStudentRead } from "../api/types";
import { useTrainer } from "../context/TrainerContext";
import "../components/StudentSwipeDeck.css";
import "../pages/AdminPage.css";

function formatDate(value: string | null): string {
  if (!value) return "—";
  const [year, month, day] = value.split("-");
  if (!year || !month || !day) return value;
  return `${day}.${month}.${year}`;
}

function matchesStudent(query: string, student: TrainerStudentRead): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const haystack = [
    student.first_name,
    student.last_name,
    student.age_group,
    student.birth_number ?? "",
    student.health_insurance ?? "",
    student.home_branch ?? "",
    ...student.training_groups,
    ...student.branches.map((b) => b.name),
    ...student.parents.map((p) => `${p.first_name} ${p.last_name} ${p.email} ${p.phone}`),
  ]
    .join(" ")
    .toLowerCase();
  return haystack.includes(q);
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
            {!student.is_guest && (
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

  const list = useMemo(
    () => (studentsQuery.data ?? []).filter((student) => matchesStudent(search, student)),
    [studentsQuery.data, search],
  );

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

      <label className="notification-field">
        Hledat
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Jméno, rodné číslo, skupina…"
        />
      </label>

      {studentsQuery.isError && <p className="error-box">{String(studentsQuery.error)}</p>}

      <div className="admin-list" style={{ marginTop: 16 }}>
        {list.map((student) => (
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
        {list.length === 0 && !studentsQuery.isLoading && (
          <p className="admin-empty">Žádní žáci pro vybranou pobočku.</p>
        )}
      </div>

      {viewing && <StudentDetailModal student={viewing} onClose={() => setViewing(null)} />}
    </div>
  );
}
