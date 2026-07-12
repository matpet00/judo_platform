import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { TrainerChangePinForm } from "./TrainerChangePinForm";
import { useTrainer } from "../context/TrainerContext";

type TrainerPinSecurityGateProps = {
  children: ReactNode;
};

export function TrainerPinSecurityGate({ children }: TrainerPinSecurityGateProps) {
  const { isAuthenticated, trainer, pinChangeRequired, clearPinChangeRequired, clearTrainer } = useTrainer();

  if (!isAuthenticated || !trainer) {
    return <Navigate to="/" replace />;
  }

  if (pinChangeRequired) {
    return (
      <div className="boot-screen app-shell">
        <TrainerChangePinForm
          required
          onClose={clearTrainer}
          onSuccess={() => {
            clearPinChangeRequired();
            clearTrainer();
          }}
        />
      </div>
    );
  }

  return children;
}
