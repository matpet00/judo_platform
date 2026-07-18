import { useState } from "react";
import type { AgeGroup, BranchBrief, NotificationTargetCreate } from "../api/types";

type ScopeValue = number | "all";
type RecipientValue = "everyone" | "trainer" | "parent";

const AGE_GROUPS: AgeGroup[] = ["U8", "U10", "U12", "U14", "U16", "U18"];

export function targetKey(target: NotificationTargetCreate) {
  return `${target.audience}:${target.branch_id ?? "all"}:${target.age_group ?? "all"}`;
}

export function recipientLabel(target: NotificationTargetCreate) {
  if (target.audience === "trainer") return "Trenéři";
  return target.age_group ? `Rodiče (${target.age_group})` : "Rodiče";
}

type Props = {
  branches: BranchBrief[];
  targets: NotificationTargetCreate[];
  onChange: (targets: NotificationTargetCreate[]) => void;
};

export function RecipientTargets({ branches, targets, onChange }: Props) {
  const [scope, setScope] = useState<ScopeValue>("all");
  const [recipient, setRecipient] = useState<RecipientValue>("everyone");
  const [categories, setCategories] = useState<AgeGroup[]>([]);

  const branchName = (branchId: number | null | undefined) => {
    if (branchId == null) return "Všechny pobočky";
    return branches.find((b) => b.id === branchId)?.name ?? `Pobočka #${branchId}`;
  };

  const addTarget = () => {
    const branchId = scope === "all" ? null : scope;
    const additions: NotificationTargetCreate[] = [];
    if (recipient === "everyone" || recipient === "trainer") {
      additions.push({ audience: "trainer", branch_id: branchId });
    }
    if (recipient === "everyone" || recipient === "parent") {
      const parentGroups: (AgeGroup | null)[] = categories.length > 0 ? categories : [null];
      for (const age of parentGroups) {
        additions.push({ audience: "parent", branch_id: branchId, age_group: age });
      }
    }
    const existing = new Set(targets.map(targetKey));
    const merged = [...targets];
    for (const target of additions) {
      if (!existing.has(targetKey(target))) {
        merged.push(target);
        existing.add(targetKey(target));
      }
    }
    onChange(merged);
  };

  const removeTarget = (key: string) => {
    onChange(targets.filter((target) => targetKey(target) !== key));
  };

  const toggleCategory = (age: AgeGroup) => {
    setCategories((current) =>
      current.includes(age) ? current.filter((row) => row !== age) : [...current, age],
    );
  };

  return (
    <div className="notification-targeting">
      <div className="notification-targeting__row">
        <label>
          Pobočka
          <select
            value={scope === "all" ? "all" : String(scope)}
            onChange={(event) => setScope(event.target.value === "all" ? "all" : Number(event.target.value))}
          >
            <option value="all">Všechny pobočky</option>
            {branches.map((branch) => (
              <option key={branch.id} value={branch.id}>{branch.name}</option>
            ))}
          </select>
        </label>
        <label>
          Příjemci
          <select value={recipient} onChange={(event) => setRecipient(event.target.value as RecipientValue)}>
            <option value="everyone">Všichni (trenéři + rodiče)</option>
            <option value="trainer">Jen trenéři</option>
            <option value="parent">Jen rodiče</option>
          </select>
        </label>
      </div>
      {recipient !== "trainer" && (
        <div className="notification-categories">
          <span className="notification-categories__label">
            Kategorie rodičů {categories.length === 0 ? "(všechny)" : ""}
          </span>
          <div className="notification-categories__chips">
            {AGE_GROUPS.map((age) => (
              <button
                key={age}
                type="button"
                className={categories.includes(age) ? "is-active" : ""}
                onClick={() => toggleCategory(age)}
              >
                {age}
              </button>
            ))}
          </div>
        </div>
      )}
      <button type="button" className="btn btn--soft notification-compose__add" onClick={addTarget}>
        Přidat příjemce
      </button>
      {targets.length > 0 && (
        <div className="notification-chips">
          {targets.map((target) => {
            const key = targetKey(target);
            return (
              <button key={key} type="button" onClick={() => removeTarget(key)}>
                {branchName(target.branch_id)} · {recipientLabel(target)} ×
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
