import { useCallback, useMemo, useState, type ReactNode } from "react";
import { TOKEN_KEY, USER_KEY, clearStoredAuth, getStoredToken } from "@/api/client";
import { logoutRemote } from "@/api/service";
import type { AuthUser, TokenResponse } from "@/api/types";
import { AuthContext } from "./auth-context";

function readStoredUser(): AuthUser | null {
  const raw = sessionStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => getStoredToken());
  const [user, setUser] = useState<AuthUser | null>(() => readStoredUser());

  const finishLogin = useCallback((result: TokenResponse, username: string) => {
    const authUser: AuthUser = {
      sub: username,
      user_type: result.user_type,
      role: result.role,
      department: result.department,
      name: result.name,
    };
    sessionStorage.setItem(TOKEN_KEY, result.access_token);
    sessionStorage.setItem(USER_KEY, JSON.stringify(authUser));
    setToken(result.access_token);
    setUser(authUser);
  }, []);

  const logout = useCallback(async () => {
    try {
      await logoutRemote();
    } catch {
      // 即使后端不可达也清除本地登录状态
    }
    clearStoredAuth();
    setToken(null);
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ token, user, finishLogin, logout }),
    [token, user, finishLogin, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
