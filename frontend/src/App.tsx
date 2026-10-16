import { Navigate, Route, Routes } from "react-router";
import { RedirectIfAuthed, RequireAuth } from "@/auth/guards";
import { ActivityRegistrationPage } from "@/pages/ActivityRegistrationPage";
import { AdminDashboard } from "@/pages/AdminDashboard";
import { AdminLoginPage } from "@/pages/AdminLoginPage";
import { LoginPage } from "@/pages/LoginPage";
import { QuestionnaireAdminPage } from "@/pages/QuestionnaireAdminPage";
import { RegistrationQuestionnairePage } from "@/pages/RegistrationQuestionnairePage";
import { StudentDashboard } from "@/pages/StudentDashboard";

export default function App() {
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
        path="/student/questionnaire"
        element={
          <RequireAuth userType="student">
            <RegistrationQuestionnairePage />
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
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
