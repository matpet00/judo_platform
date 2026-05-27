import { useState } from "react";
import { useTrainer } from "../context/TrainerContext";
import { TrainerPicker, trainerLabel } from "./TrainerPicker";
import { TrainerPinGate } from "./TrainerPinGate";

type TrainerSwitcherProps = {
  variant?: "bar" | "compact";
};

function TrainerChangeOverlay({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { trainer, trainers, loginTrainer, clearTrainer } = useTrainer();
  const [pinTrainer, setPinTrainer] = useState<typeof trainer>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  if (!open || !trainer) return null;

  const handleSelect = (next: (typeof trainers)[number]) => {
    setPinTrainer(next);
    setError(null);
  };

  const handlePin = async (pin: string) => {
    if (!pinTrainer) return;
    setPending(true);
    setError(null);
    try {
      await loginTrainer(pinTrainer.id, pin);
      setPinTrainer(null);
      onClose();
    } catch (e) {
      setError(String(e));
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="trainer-overlay" role="dialog" aria-modal="true" aria-label="Změnit trenéra">
      <div className="trainer-overlay__panel app-shell">
        {pinTrainer ? (
          <TrainerPinGate
            trainer={pinTrainer}
            pending={pending}
            error={error}
            onCancel={() => setPinTrainer(null)}
            onSubmit={handlePin}
          />
        ) : (
          <>
            <TrainerPicker
              trainers={trainers}
              selectedId={trainer.id}
              title="Změnit trenéra"
              subtitle="Vyber jméno a zadej PIN"
              onSelect={handleSelect}
            />
            <button
              type="button"
              className="btn btn--ghost trainer-overlay__close"
              onClick={() => {
                clearTrainer();
                onClose();
              }}
            >
              Odhlásit
            </button>
            <button type="button" className="btn btn--ghost trainer-overlay__close" onClick={onClose}>
              Zrušit
            </button>
          </>
        )}
      </div>
    </div>
  );
}

export function TrainerSwitcher({ variant = "bar" }: TrainerSwitcherProps) {
  const { trainer } = useTrainer();
  const [open, setOpen] = useState(false);

  if (!trainer) return null;

  return (
    <>
      {variant === "bar" ? (
        <div className="trainer-bar">
          <div className="trainer-bar__info">
            <span className="trainer-bar__label">Přihlášen</span>
            <span className="trainer-bar__name">{trainerLabel(trainer)}</span>
          </div>
          <button type="button" className="trainer-bar__change" onClick={() => setOpen(true)}>
            Změnit
          </button>
        </div>
      ) : (
        <button
          type="button"
          className="trainer-chip"
          onClick={() => setOpen(true)}
          aria-label={`Trenér ${trainerLabel(trainer)}, klepnutím změníš`}
        >
          <span className="trainer-chip__label">Trenér</span>
          <span className="trainer-chip__name">{trainerLabel(trainer)}</span>
          <span className="trainer-chip__change">Změnit</span>
        </button>
      )}

      <TrainerChangeOverlay open={open} onClose={() => setOpen(false)} />
    </>
  );
}

export function TrainerLoginFlow({ onDone }: { onDone?: () => void }) {
  const { trainers, loginTrainer } = useTrainer();
  const [pinTrainer, setPinTrainer] = useState<(typeof trainers)[number] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const handlePin = async (pin: string) => {
    if (!pinTrainer) return;
    setPending(true);
    setError(null);
    try {
      await loginTrainer(pinTrainer.id, pin);
      onDone?.();
    } catch (e) {
      setError(String(e));
    } finally {
      setPending(false);
    }
  };

  if (pinTrainer) {
    return (
      <TrainerPinGate
        trainer={pinTrainer}
        pending={pending}
        error={error}
        onCancel={() => setPinTrainer(null)}
        onSubmit={handlePin}
      />
    );
  }

  return (
    <TrainerPicker
      trainers={trainers}
      onSelect={(trainer) => {
        setPinTrainer(trainer);
        setError(null);
      }}
    />
  );
}
