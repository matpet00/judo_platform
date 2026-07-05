import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { ParentSelf } from "../api/types";
import { clearParentAuth, getParentToken, getStoredParentId, setParentAuth } from "../lib/auth";

type ParentContextValue = {
  parent: ParentSelf | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  loginParent: (username: string, password: string) => Promise<void>;
  clearParent: () => void;
};

const ParentContext = createContext<ParentContextValue | null>(null);

export function ParentProvider({ children }: { children: ReactNode }) {
  const [parentId, setParentId] = useState<number | null>(getStoredParentId);
  const [token, setToken] = useState<string | null>(getParentToken);

  const meQuery = useQuery({
    queryKey: ["parent-me", parentId],
    queryFn: () => api.parentMe(),
    enabled: parentId !== null && token !== null,
    retry: false,
  });

  const loginParent = useCallback(async (username: string, password: string) => {
    const auth = await api.parentLogin(username, password);
    setParentAuth(auth.parent_id, auth.access_token);
    setParentId(auth.parent_id);
    setToken(auth.access_token);
  }, []);

  const clearParent = useCallback(() => {
    setParentId(null);
    setToken(null);
    clearParentAuth();
  }, []);

  const parent = meQuery.data ?? null;
  const isAuthenticated = parentId !== null && token !== null;

  const value = useMemo(
    () => ({
      parent,
      isAuthenticated,
      isLoading: isAuthenticated && meQuery.isLoading,
      loginParent,
      clearParent,
    }),
    [parent, isAuthenticated, meQuery.isLoading, loginParent, clearParent],
  );

  return <ParentContext.Provider value={value}>{children}</ParentContext.Provider>;
}

export function useParent() {
  const ctx = useContext(ParentContext);
  if (!ctx) {
    throw new Error("useParent must be used within ParentProvider");
  }
  return ctx;
}
