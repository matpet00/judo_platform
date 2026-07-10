import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useTrainer } from "../context/TrainerContext";
import type { Trainer } from "../api/types";
import { TrainerPicker, trainerLabel } from "./TrainerPicker";
import { TrainerPinGate } from "./TrainerPinGate";

type TrainerSwitcherProps = {
  variant?: "bar" | "compact";
};

function isTrainerGoneError(err: unknown): boolean {
  const msg = String(err).toLowerCase();
  return msg.includes("trainer not found") || msg.includes("404");
}

function usePinTrainerFlow(trainers: Trainer[]) {
  const queryClient = useQueryClient();
  const [pinTrainer, setPinTrainer] = useState<Trainer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (!pinTrainer) return;
    if (!trainers.some((t) => t.id === pinTrainer.id)) {
      setPinTrainer(null);
      setError("Tento trenér už není v systému. Vyber jiného.");
    }
  }, [trainers, pinTrainer]);

  const selectTrainer = (trainer: Trainer) => {
    setPinTrainer(trainer);
    setError(null);
  };

  const cancelPin = () => {
    setPinTrainer(null);
    setError(null);
  };

  const handleLoginError = async (err: unknown) => {
    if (isTrainerGoneError(err)) {
      await queryClient.invalidateQueries({ queryKey: ["trainers"] });
      setPinTrainer(null);
      setError("Tento trenér už není v systému. Vyber jiného.");
      return;
    }
    setError(String(err));
  };

  return {
    pinTrainer,
    error,
    pending,
    setPending,
    selectTrainer,
    cancelPin,
    handleLoginError,
    clearError: () => setError(null),
  };
}

function TrainerChangeOverlay({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { trainer, trainers, loginTrainer, clearTrainer } = useTrainer();
  const pin = usePinTrainerFlow(trainers);

  if (!open || !trainer) return null;

  const handleSelect = (next: (typeof trainers)[number]) => {
    pin.selectTrainer(next);
  };

  const handlePin = async (pinValue: string) => {
    if (!pin.pinTrainer) return;
    pin.setPending(true);
    pin.clearError();
    try {
      await loginTrainer(pin.pinTrainer.id, pinValue);
      pin.cancelPin();
      onClose();
    } catch (e) {
      await pin.handleLoginError(e);
    } finally {
      pin.setPending(false);
    }
  };

  return (
    <div className="trainer-overlay" role="dialog" aria-modal="true" aria-label="Změnit trenéra">
      <div className="trainer-overlay__panel app-shell">
        {pin.pinTrainer ? (
          <TrainerPinGate
            trainer={pin.pinTrainer}
            pending={pin.pending}
            error={pin.error}
            onCancel={pin.cancelPin}
            onSubmit={handlePin}
          />
        ) : (
          <>
            {pin.error && <p className="error-box trainer-pin-gate__error">{pin.error}</p>}
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
  const pin = usePinTrainerFlow(trainers);

  const handlePin = async (pinValue: string) => {
    if (!pin.pinTrainer) return;
    pin.setPending(true);
    pin.clearError();
    try {
      await loginTrainer(pin.pinTrainer.id, pinValue);
      pin.cancelPin();
      onDone?.();
    } catch (e) {
      await pin.handleLoginError(e);
    } finally {
      pin.setPending(false);
    }
  };

  if (pin.pinTrainer) {
    return (
      <TrainerPinGate
        trainer={pin.pinTrainer}
        pending={pin.pending}
        error={pin.error}
        onCancel={pin.cancelPin}
        onSubmit={handlePin}
      />
    );
  }

  return (
    <>
      {pin.error && <p className="error-box trainer-pin-gate__error">{pin.error}</p>}
      <TrainerPicker
        trainers={trainers}
        onSelect={pin.selectTrainer}
      />
    </>
  );
}
