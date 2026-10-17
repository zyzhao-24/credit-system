import { createContext, useContext } from "react";
import type { AuthUser, TokenResponse } from "@/api/types";

export interface AuthContextValue {
  token: string | null;
  user: AuthUser | null;
  /** 两步登录完成后写入令牌与用户信息（页面负责密码/OTP两个步骤）。 */
  finishLogin: (result: TokenResponse, username: string) => void;
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
