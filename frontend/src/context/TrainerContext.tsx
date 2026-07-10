import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Trainer } from "../api/types";
import { clearTrainerAuth, getStoredTrainerId, getTrainerToken, setTrainerAuth } from "../lib/auth";

type TrainerContextValue = {
  trainer: Trainer | null;
  trainers: Trainer[];
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  isAuthenticated: boolean;
  loginTrainer: (trainerId: number, pin: string) => Promise<void>;
  clearTrainer: () => void;
};

const TrainerContext = createContext<TrainerContextValue | null>(null);

export function TrainerProvider({ children }: { children: ReactNode }) {
  const [trainerId, setTrainerId] = useState<number | null>(getStoredTrainerId);
  const [token, setToken] = useState<string | null>(getTrainerToken);

  const trainersQuery = useQuery({
    queryKey: ["trainers"],
    queryFn: () => api.trainers(),
    staleTime: 5_000,
    refetchOnWindowFocus: true,
  });

  const trainers = trainersQuery.data ?? [];
  const trainer = trainers.find((t) => t.id === trainerId) ?? null;
  const isAuthenticated = trainerId !== null && token !== null && trainer !== null;

  useEffect(() => {
    if (!trainersQuery.isSuccess || trainerId === null) return;
    if (!trainers.some((t) => t.id === trainerId)) {
      setTrainerId(null);
      setToken(null);
      clearTrainerAuth();
    }
  }, [trainersQuery.isSuccess, trainers, trainerId]);

  const loginTrainer = useCallback(async (id: number, pin: string) => {
    const auth = await api.verifyPin(id, pin);
    setTrainerAuth(auth.trainer_id, auth.access_token);
    setTrainerId(auth.trainer_id);
    setToken(auth.access_token);
  }, []);

  const clearTrainer = useCallback(() => {
    setTrainerId(null);
    setToken(null);
    clearTrainerAuth();
  }, []);

  const value = useMemo(
    () => ({
      trainer,
      trainers,
      isLoading: trainersQuery.isLoading,
      isError: trainersQuery.isError,
      error: trainersQuery.error,
      isAuthenticated,
      loginTrainer,
      clearTrainer,
    }),
    [
      trainer,
      trainers,
      trainersQuery.isLoading,
      trainersQuery.isError,
      trainersQuery.error,
      isAuthenticated,
      loginTrainer,
      clearTrainer,
    ],
  );

  return <TrainerContext.Provider value={value}>{children}</TrainerContext.Provider>;
}

export function useTrainer() {
  const ctx = useContext(TrainerContext);
  if (!ctx) {
    throw new Error("useTrainer must be used within TrainerProvider");
  }
  return ctx;
}
