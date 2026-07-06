import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

export function TrainingGuestPicker({
  existingIds,
  onAdd,
}: {
  existingIds: number[];
  onAdd: (studentId: number) => Promise<void>;
}) {
  const [query, setQuery] = useState("");
  const [adding, setAdding] = useState<number | null>(null);
  const studentsQuery = useQuery({ queryKey: ["students"], queryFn: () => api.students() });

  const q = query.trim().toLowerCase();
  const matches = useMemo(() => {
    if (!q) return [];
    const existing = new Set(existingIds);
    return (studentsQuery.data ?? [])
      .filter((s) => !existing.has(s.id))
      .filter((s) => {
        const a = `${s.first_name} ${s.last_name}`.toLowerCase();
        const b = `${s.last_name} ${s.first_name}`.toLowerCase();
        return a.includes(q) || b.includes(q);
      })
      .slice(0, 6);
  }, [studentsQuery.data, q, existingIds]);

  const handleAdd = async (id: number) => {
    setAdding(id);
    try {
      await onAdd(id);
      setQuery("");
    } finally {
      setAdding(null);
    }
  };

  return (
    <div className="guest-picker">
      <label className="notification-field guest-picker__field">
        Přidat hosta (dítě z jiné pobočky / skupiny)
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Začni psát jméno dítěte…"
          autoComplete="off"
        />
      </label>
      {q && (
        <div className="guest-picker__list">
          {studentsQuery.isLoading && <div className="guest-picker__empty">Načítám…</div>}
          {!studentsQuery.isLoading && matches.length === 0 && (
            <div className="guest-picker__empty">Nikdo nenalezen.</div>
          )}
          {matches.map((s) => (
            <button
              key={s.id}
              type="button"
              className="guest-picker__item"
              disabled={adding != null}
              onClick={() => handleAdd(s.id)}
            >
              <span className="guest-picker__name">
                {s.first_name} {s.last_name}
              </span>
              <span className="guest-picker__meta">
                {s.age_group}
                {s.branches?.length ? ` · ${s.branches.map((b) => b.name).join(", ")}` : ""}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
