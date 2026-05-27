import type { Trainer } from "../api/types";

function trainerLabel(trainer: Trainer): string {
  return `${trainer.first_name} ${trainer.last_name}`;
}

function branchNames(trainer: Trainer): string {
  return trainer.branches.map((b) => b.name).join(", ");
}

type TrainerPickerProps = {
  trainers: Trainer[];
  selectedId?: number | null;
  onSelect: (trainer: Trainer) => void;
  title?: string;
  subtitle?: string;
};

export function TrainerPicker({
  trainers,
  selectedId,
  onSelect,
  title = "Kdo jsi?",
  subtitle = "Vyber trenéra pro dnešní docházku",
}: TrainerPickerProps) {
  if (trainers.length === 0) {
    return (
      <div className="trainer-picker">
        <p className="error-box">V systému není žádný trenér. Přidej ho přes API.</p>
      </div>
    );
  }

  return (
    <div className="trainer-picker">
      <header className="trainer-picker__header">
        <p className="page-header__eyebrow">Přihlášení</p>
        <h1 className="trainer-picker__title">{title}</h1>
        <p className="trainer-picker__sub">{subtitle}</p>
      </header>

      <div className="trainer-picker__list">
        {trainers.map((trainer, index) => {
          const active = trainer.id === selectedId;
          return (
            <button
              key={trainer.id}
              type="button"
              className={`trainer-card${active ? " trainer-card--active" : ""}`}
              style={{ animationDelay: `${index * 0.05}s` }}
              onClick={() => onSelect(trainer)}
            >
              <span className="trainer-card__name">{trainerLabel(trainer)}</span>
              <span className="trainer-card__branch">{branchNames(trainer)}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export { trainerLabel };
