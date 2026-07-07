import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { api } from "../api/client";
import { clearAdminAuth, getAdminToken, setAdminAuth } from "../lib/auth";

type AdminContextValue = {
  isAuthenticated: boolean;
  loginAdmin: (username: string, password: string) => Promise<void>;
  logoutAdmin: () => void;
};

const AdminContext = createContext<AdminContextValue | null>(null);

export function AdminProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(getAdminToken);

  const loginAdmin = useCallback(async (username: string, password: string) => {
    const auth = await api.adminLogin(username, password);
    setAdminAuth(auth.access_token);
    setToken(auth.access_token);
  }, []);

  const logoutAdmin = useCallback(() => {
    clearAdminAuth();
    setToken(null);
  }, []);

  const value = useMemo(
    () => ({
      isAuthenticated: token !== null,
      loginAdmin,
      logoutAdmin,
    }),
    [token, loginAdmin, logoutAdmin],
  );

  return <AdminContext.Provider value={value}>{children}</AdminContext.Provider>;
}

export function useAdmin() {
  const ctx = useContext(AdminContext);
  if (!ctx) {
    throw new Error("useAdmin must be used within AdminProvider");
  }
  return ctx;
}
