import { HashRouter, Routes, Route, Navigate } from "react-router-dom";
import { lazy, Suspense, useEffect } from "react";
import ProtectedRoute from "./components/ProtectedRoute";
import SessionGuard from "./components/SessionGuard";
import LoginModalProvider from "./components/LoginModalProvider";
import MascotHost from "./components/mascot/MascotHost";
import { useEmbedMode } from "./embed";
import { api } from "./api/client";
import { fetchSitePolicy } from "./api/sitePolicy";

const ForgotPasswordPage = lazy(() => import("./pages/ForgotPasswordPage"));
const ResetPasswordPage = lazy(() => import("./pages/ResetPasswordPage"));
const RegisterPage = lazy(() => import("./pages/RegisterPage"));
const VerifyEmailPage = lazy(() => import("./pages/VerifyEmailPage"));
const VerifyEmailPendingPage = lazy(() => import("./pages/VerifyEmailPendingPage"));
const HomePage = lazy(() => import("./pages/HomePage"));
const UserProfile = lazy(() => import("./pages/UserProfile"));
const ProfileRedirect = lazy(() => import("./pages/ProfileRedirect"));
const TaskListPage = lazy(() => import("./pages/TaskListPage"));
const TaskDetailPage = lazy(() => import("./pages/TaskDetailPage"));
const TaskFormPage = lazy(() => import("./pages/TaskFormPage"));
const MessagePage = lazy(() => import("./pages/MessagePage"));
const NotificationsPage = lazy(() => import("./pages/NotificationsPage"));
const FeedbackPage = lazy(() => import("./pages/FeedbackPage"));
const FeedbackDetailPage = lazy(() => import("./pages/FeedbackDetailPage"));
const ActivityListPage = lazy(() => import("./pages/ActivityListPage"));
const ActivityFormPage = lazy(() => import("./pages/ActivityFormPage"));
const ActivityDetailPage = lazy(() => import("./pages/ActivityDetailPage"));
const InboxPage = lazy(() => import("./pages/InboxPage"));
const NewsListPage = lazy(() => import("./pages/NewsListPage"));
const NewsDetailPage = lazy(() => import("./pages/NewsDetailPage"));
const NewsFormPage = lazy(() => import("./pages/NewsFormPage"));
const ReviewQueuePage = lazy(() => import("./pages/ReviewQueuePage"));
const AboutPage = lazy(() => import("./pages/AboutPage"));
const ExamBoardPage = lazy(() => import("./pages/ExamBoardPage"));
const TutorialListPage = lazy(() => import("./pages/TutorialListPage"));
const TutorialDetailPage = lazy(() => import("./pages/TutorialDetailPage"));
const TutorialFormPage = lazy(() => import("./pages/TutorialFormPage"));
const JoinPage = lazy(() => import("./pages/JoinPage"));
const JoinFormPage = lazy(() => import("./pages/JoinFormPage"));
const JoinEditorPage = lazy(() => import("./pages/JoinEditorPage"));
const SurveyEditorPage = lazy(() => import("./pages/SurveyEditorPage"));

function Loading() {
  return <div style={{ textAlign: "center", padding: "80px 0", color: "#6b7280" }}>加载中...</div>;
}

function MaybeMascot() {
  const embed = useEmbedMode();
  if (embed) return null;
  return <MascotHost />;
}

export default function App() {
  // 启动时拉取一次 CSRF cookie。开发态 webpack 直接服务模板、不经 Django 渲染，
  // 无法靠 {% csrf_token %} 下发 cookie，故显式请求该端点，避免匿名 POST 被 403。
  useEffect(() => {
    api.getCsrf().catch(() => {});
    fetchSitePolicy();
  }, []);

  return (
    <HashRouter>
      <LoginModalProvider>
      <SessionGuard>
      <Suspense fallback={<Loading />}>
        <Routes>
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/verify-email" element={<VerifyEmailPage />} />
          <Route path="/verify-email-pending" element={<VerifyEmailPendingPage />} />
          <Route path="/profile" element={<ProfileRedirect />} />
          <Route path="/u/:id" element={<UserProfile />} />
          <Route path="/tasks" element={<ProtectedRoute><TaskListPage /></ProtectedRoute>} />
          <Route path="/tasks/new" element={<ProtectedRoute><TaskFormPage /></ProtectedRoute>} />
          <Route path="/tasks/:id" element={<ProtectedRoute><TaskDetailPage /></ProtectedRoute>} />
          <Route path="/tasks/:id/edit" element={<ProtectedRoute><TaskFormPage /></ProtectedRoute>} />
          <Route path="/messages" element={<ProtectedRoute><MessagePage /></ProtectedRoute>} />
          <Route path="/messages/:id" element={<ProtectedRoute><MessagePage /></ProtectedRoute>} />
          <Route path="/notifications" element={<ProtectedRoute><NotificationsPage /></ProtectedRoute>} />
          <Route path="/activity" element={<ActivityListPage />} />
          <Route path="/activity/new" element={<ProtectedRoute><ActivityFormPage /></ProtectedRoute>} />
          <Route path="/activity/:id" element={<ActivityDetailPage />} />
          <Route path="/activity/:id/edit" element={<ProtectedRoute><ActivityFormPage /></ProtectedRoute>} />
          <Route path="/activity/:id/survey-edit" element={<ProtectedRoute><SurveyEditorPage /></ProtectedRoute>} />
          <Route path="/inbox" element={<ProtectedRoute><InboxPage /></ProtectedRoute>} />
          <Route path="/feedback" element={<FeedbackPage />} />
          <Route path="/feedback/:id" element={<ProtectedRoute><FeedbackDetailPage /></ProtectedRoute>} />
          <Route path="/news" element={<NewsListPage />} />
          <Route path="/news/new" element={<ProtectedRoute><NewsFormPage /></ProtectedRoute>} />
          <Route path="/news/:id" element={<NewsDetailPage />} />
          <Route path="/news/:id/edit" element={<ProtectedRoute><NewsFormPage /></ProtectedRoute>} />
          <Route path="/reviews" element={<ProtectedRoute><ReviewQueuePage /></ProtectedRoute>} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="/exam" element={<ExamBoardPage />} />
          <Route path="/tutorials" element={<TutorialListPage />} />
          <Route path="/tutorials/new" element={<ProtectedRoute><TutorialFormPage /></ProtectedRoute>} />
          <Route path="/tutorials/:id" element={<TutorialDetailPage />} />
          <Route path="/join" element={<JoinPage />} />
          <Route path="/join/form" element={<JoinFormPage />} />
          <Route path="/join/editor" element={<ProtectedRoute><JoinEditorPage /></ProtectedRoute>} />
          <Route path="/" element={<HomePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
      </SessionGuard>
      </LoginModalProvider>
      <MaybeMascot />
    </HashRouter>
  );
}
