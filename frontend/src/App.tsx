import { lazy, Suspense, useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router";
import { RedirectIfAuthed, RequireAuth } from "@/auth/guards";
import { ActivityRegistrationPage } from "@/pages/ActivityRegistrationPage";
import { AdminDashboard } from "@/pages/AdminDashboard";
import { AdminLoginPage } from "@/pages/AdminLoginPage";
import { LoginPage } from "@/pages/LoginPage";
import { QuestionnaireAdminPage } from "@/pages/QuestionnaireAdminPage";
import { StudentDashboard } from "@/pages/StudentDashboard";
import { StudentProfilePage } from "@/pages/StudentProfilePage";

// 设计器依赖 CodeMirror，体积较大，按需加载
const QuestionnaireDesignerPage = lazy(() =>
  import("@/pages/QuestionnaireDesignerPage").then((module) => ({
    default: module.QuestionnaireDesignerPage,
  })),
);

export default function App() {
  // 角色主题：/admin 路径（含管理员登录）为红，其余学生页面为蓝；维护台灰在服务端页面内联。
  // 主题类挂在 <html> 上，使 Radix 弹窗等 portal 内容也随角色换色。
  const { pathname } = useLocation();
  const theme = pathname.startsWith("/admin") ? "theme-admin" : "theme-student";
  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove("theme-student", "theme-admin");
    root.classList.add(theme);
  }, [theme]);
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route
        path="/login"
        element={
          <RedirectIfAuthed>
            <LoginPage />
          </RedirectIfAuthed>
        }
      />
      <Route
        path="/admin/login"
        element={
          <RedirectIfAuthed>
            <AdminLoginPage />
          </RedirectIfAuthed>
        }
      />
      <Route
        path="/student"
        element={
          <RequireAuth userType="student">
            <StudentDashboard />
          </RequireAuth>
        }
      />
      <Route
        path="/student/profile"
        element={
          <RequireAuth userType="student">
            <StudentProfilePage />
          </RequireAuth>
        }
      />
      <Route
        path="/student/activities"
        element={
          <RequireAuth userType="student">
            <ActivityRegistrationPage />
          </RequireAuth>
        }
      />
      <Route
        path="/admin"
        element={
          <RequireAuth userType="admin">
            <AdminDashboard />
          </RequireAuth>
        }
      />
      <Route
        path="/admin/questionnaires"
        element={
          <RequireAuth userType="admin">
            <QuestionnaireAdminPage />
          </RequireAuth>
        }
      />
      <Route
        path="/admin/questionnaires/design"
        element={
          <RequireAuth userType="admin">
            <Suspense fallback={<p className="py-10 text-center text-[#999]">加载设计器...</p>}>
              <QuestionnaireDesignerPage />
            </Suspense>
          </RequireAuth>
        }
      />
      <Route
        path="/admin/questionnaires/design/:questionnaireId"
        element={
          <RequireAuth userType="admin">
            <Suspense fallback={<p className="py-10 text-center text-[#999]">加载设计器...</p>}>
              <QuestionnaireDesignerPage />
            </Suspense>
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
