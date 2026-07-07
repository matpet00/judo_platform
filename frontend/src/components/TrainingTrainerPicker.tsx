import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

export function TrainingTrainerPicker({
  existingIds,
  onAdd,
}: {
  existingIds: number[];
  onAdd: (trainerId: number) => Promise<void>;
}) {
  const [query, setQuery] = useState("");
  const [adding, setAdding] = useState<number | null>(null);
  const trainersQuery = useQuery({ queryKey: ["trainers"], queryFn: () => api.trainers() });

  const q = query.trim().toLowerCase();
  const matches = useMemo(() => {
    if (!q) return [];
    const existing = new Set(existingIds);
    return (trainersQuery.data ?? [])
      .filter((t) => !existing.has(t.id))
      .filter((t) => {
        const a = `${t.first_name} ${t.last_name}`.toLowerCase();
        const b = `${t.last_name} ${t.first_name}`.toLowerCase();
        return a.includes(q) || b.includes(q);
      })
      .slice(0, 6);
  }, [trainersQuery.data, q, existingIds]);

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
        Přidat hostujícího trenéra
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Začni psát jméno trenéra…"
          autoComplete="off"
        />
      </label>
      {q && (
        <div className="guest-picker__list">
          {trainersQuery.isLoading && <div className="guest-picker__empty">Načítám…</div>}
          {!trainersQuery.isLoading && matches.length === 0 && (
            <div className="guest-picker__empty">Nikdo nenalezen.</div>
          )}
          {matches.map((t) => (
            <button
              key={t.id}
              type="button"
              className="guest-picker__item"
              disabled={adding != null}
              onClick={() => handleAdd(t.id)}
            >
              <span className="guest-picker__name">
                {t.first_name} {t.last_name}
              </span>
              <span className="guest-picker__meta">
                {t.branches?.length ? t.branches.map((b) => b.name).join(", ") : "bez pobočky"}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
