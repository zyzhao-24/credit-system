import { useCallback, useMemo, useState, type ReactNode } from "react";
import { TOKEN_KEY, USER_KEY, clearStoredAuth, getStoredToken } from "@/api/client";
import { loginWithToken, logoutRemote } from "@/api/service";
import { sha256Hex } from "@/lib/sha256";
import type { AuthUser } from "@/api/types";
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

  const login = useCallback(
    async (username: string, password: string, userType: "student" | "admin") => {
      const digest = await sha256Hex(password);
      const result = await loginWithToken(username, digest, userType);
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
    },
    [],
  );

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

  const value = useMemo(() => ({ token, user, login, logout }), [token, user, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
