import { createContext, useContext, useState } from "react";
import type { ReactNode } from "react";
import { api, getToken, setToken } from "../api/client";

interface AuthContextValue {
  authed: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [authed, setAuthed] = useState<boolean>(() => Boolean(getToken()));

  return (
    <AuthContext.Provider
      value={{
        authed,
        login: async (username, password) => {
          const token = await api.login(username, password);
          setToken(token.access_token);
          setAuthed(true);
        },
        logout: async () => {
          try {
            await api.logout();
          } finally {
            setToken(null);
            setAuthed(false);
          }
        },
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}