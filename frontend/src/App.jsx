import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import useAuthStore from './stores/authStore';
import LoginPage from './pages/LoginPage';
import ChatPage from './pages/ChatPage';
import AdminLayout from './pages/admin/AdminLayout';
import DashboardPage from './pages/admin/DashboardPage';
import KBManagementPage from './pages/admin/KBManagementPage';
import UserManagementPage from './pages/admin/UserManagementPage';
import AuditLogPage from './pages/admin/AuditLogPage';

/** Protected route wrapper — redirects to login if not authenticated. */
function ProtectedRoute({ children }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const isLoading = useAuthStore((s) => s.isLoading);

  if (isLoading) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        color: 'var(--color-text-muted)',
        fontSize: '14px',
        gap: '8px',
      }}>
        <div className="login-spinner" />
        <span>Memuat...</span>
      </div>
    );
  }

  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

/** Admin route — only allows admin and superadmin roles. */
function AdminRoute({ children }) {
  const user = useAuthStore((s) => s.user);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const isLoading = useAuthStore((s) => s.isLoading);

  if (isLoading) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        color: 'var(--color-text-muted)',
        fontSize: '14px',
        gap: '8px',
      }}>
        <div className="login-spinner" />
        <span>Memuat...</span>
      </div>
    );
  }

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  const isAdmin = user?.role === 'admin' || user?.role === 'superadmin';
  if (!isAdmin) return <Navigate to="/" replace />;

  return children;
}

/** Guest route — redirects to home if already authenticated. */
function GuestRoute({ children }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const isLoading = useAuthStore((s) => s.isLoading);

  if (isLoading) return null;

  return !isAuthenticated ? children : <Navigate to="/" replace />;
}

export default function App() {
  const initialize = useAuthStore((s) => s.initialize);

  useEffect(() => {
    initialize();
  }, [initialize]);

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/login"
          element={
            <GuestRoute>
              <LoginPage />
            </GuestRoute>
          }
        />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <ChatPage />
            </ProtectedRoute>
          }
        />

        {/* Admin Panel Routes */}
        <Route
          path="/admin"
          element={
            <AdminRoute>
              <AdminLayout />
            </AdminRoute>
          }
        >
          <Route index element={<DashboardPage />} />
          <Route path="kb" element={<KBManagementPage />} />
          <Route path="users" element={<UserManagementPage />} />
          <Route path="audit" element={<AuditLogPage />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
