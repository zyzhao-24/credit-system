import type { ReactNode } from "react";
import { Navigate } from "react-router";
import { useAuth } from "./auth-context";

interface RequireAuthProps {
  userType: "student" | "admin";
  children: ReactNode;
}

/** 路由守卫：未登录或角色不符时跳转到对应登录页。 */
export function RequireAuth({ userType, children }: RequireAuthProps) {
  const { token, user } = useAuth();

  if (!token || !user) {
    return <Navigate to={userType === "admin" ? "/admin/login" : "/login"} replace />;
  }
  if (user.user_type !== userType) {
    return <Navigate to={user.user_type === "admin" ? "/admin" : "/student"} replace />;
  }
  return <>{children}</>;
}

/** 已登录用户访问登录页时跳转到各自主页。 */
export function RedirectIfAuthed({ children }: { children: ReactNode }) {
  const { token, user } = useAuth();
  if (token && user) {
    return <Navigate to={user.user_type === "admin" ? "/admin" : "/student"} replace />;
  }
  return <>{children}</>;
}
