import { HashRouter, Routes, Route, Navigate } from "react-router-dom";
import { lazy, Suspense, useEffect } from "react";
import ProtectedRoute from "./components/ProtectedRoute";
import SessionGuard from "./components/SessionGuard";
import LoginModalProvider from "./components/LoginModalProvider";
import { api } from "./api/client";

const ForgotPasswordPage = lazy(() => import("./pages/ForgotPasswordPage"));
const ResetPasswordPage = lazy(() => import("./pages/ResetPasswordPage"));
const HomePage = lazy(() => import("./pages/HomePage"));
const ProfilePage = lazy(() => import("./pages/ProfilePage"));
const TaskListPage = lazy(() => import("./pages/TaskListPage"));
const TaskDetailPage = lazy(() => import("./pages/TaskDetailPage"));
const TaskFormPage = lazy(() => import("./pages/TaskFormPage"));
const MessagePage = lazy(() => import("./pages/MessagePage"));
const ProposalListPage = lazy(() => import("./pages/ProposalListPage"));
const ProposalFormPage = lazy(() => import("./pages/ProposalFormPage"));
const ProposalDetailPage = lazy(() => import("./pages/ProposalDetailPage"));

function Loading() {
  return <div style={{ textAlign: "center", padding: "80px 0", color: "#6b7280" }}>加载中...</div>;
}

export default function App() {
  // 启动时拉取一次 CSRF cookie。开发态 webpack 直接服务模板、不经 Django 渲染，
  // 无法靠 {% csrf_token %} 下发 cookie，故显式请求该端点，避免匿名 POST 被 403。
  useEffect(() => {
    api.getCsrf().catch(() => {});
  }, []);

  return (
    <HashRouter>
      <LoginModalProvider>
      <SessionGuard>
      <Suspense fallback={<Loading />}>
        <Routes>
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/tasks" element={<ProtectedRoute><TaskListPage /></ProtectedRoute>} />
          <Route path="/tasks/new" element={<ProtectedRoute><TaskFormPage /></ProtectedRoute>} />
          <Route path="/tasks/:id" element={<ProtectedRoute><TaskDetailPage /></ProtectedRoute>} />
          <Route path="/tasks/:id/edit" element={<ProtectedRoute><TaskFormPage /></ProtectedRoute>} />
          <Route path="/messages" element={<ProtectedRoute><MessagePage /></ProtectedRoute>} />
          <Route path="/messages/:id" element={<ProtectedRoute><MessagePage /></ProtectedRoute>} />
          <Route path="/activity" element={<ProposalListPage />} />
          <Route path="/activity/new" element={<ProtectedRoute><ProposalFormPage /></ProtectedRoute>} />
          <Route path="/activity/:id" element={<ProtectedRoute><ProposalDetailPage /></ProtectedRoute>} />
          <Route path="/activity/:id/edit" element={<ProtectedRoute><ProposalFormPage /></ProtectedRoute>} />
          <Route path="/" element={<HomePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
      </SessionGuard>
      </LoginModalProvider>
    </HashRouter>
  );
}
