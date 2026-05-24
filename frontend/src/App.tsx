import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { lazy, Suspense } from "react";
import ProtectedRoute from "./components/ProtectedRoute";

const LoginPage = lazy(() => import("./pages/LoginPage"));
const ForgotPasswordPage = lazy(() => import("./pages/ForgotPasswordPage"));
const ResetPasswordPage = lazy(() => import("./pages/ResetPasswordPage"));
const HomePage = lazy(() => import("./pages/HomePage"));
const ProfilePage = lazy(() => import("./pages/ProfilePage"));
const TaskListPage = lazy(() => import("./pages/TaskListPage"));
const TaskDetailPage = lazy(() => import("./pages/TaskDetailPage"));
const TaskFormPage = lazy(() => import("./pages/TaskFormPage"));
const MessagePage = lazy(() => import("./pages/MessagePage"));

function Loading() {
  return <div style={{ textAlign: "center", padding: "80px 0", color: "#6b7280" }}>加载中...</div>;
}

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<Loading />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/tasks" element={<ProtectedRoute><TaskListPage /></ProtectedRoute>} />
          <Route path="/tasks/new" element={<ProtectedRoute><TaskFormPage /></ProtectedRoute>} />
          <Route path="/tasks/:id" element={<ProtectedRoute><TaskDetailPage /></ProtectedRoute>} />
          <Route path="/tasks/:id/edit" element={<ProtectedRoute><TaskFormPage /></ProtectedRoute>} />
          <Route path="/messages" element={<ProtectedRoute><MessagePage /></ProtectedRoute>} />
          <Route path="/messages/:id" element={<ProtectedRoute><MessagePage /></ProtectedRoute>} />
          <Route path="/" element={<HomePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
