import { createContext, useContext } from "react";
import type { AuthUser } from "@/api/types";

export interface AuthContextValue {
  token: string | null;
  user: AuthUser | null;
  login: (username: string, password: string, userType: "student" | "admin") => Promise<void>;
  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
