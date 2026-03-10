import { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  Brain, Database, Users, ClipboardList, BarChart3,
  MessageSquare, LogOut, ChevronLeft,
} from 'lucide-react';
import useAuthStore from '../../stores/authStore';
import './AdminLayout.css';

/**
 * Admin layout with sidebar navigation for KB, Users, Audit, and Dashboard.
 * Only accessible by admin and superadmin roles.
 */
export default function AdminLayout() {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);

  const navItems = [
    { path: '/admin', icon: BarChart3, label: 'Dashboard', end: true },
    { path: '/admin/kb', icon: Database, label: 'Knowledge Base' },
    { path: '/admin/users', icon: Users, label: 'Pengguna' },
    { path: '/admin/audit', icon: ClipboardList, label: 'Audit Log' },
  ];

  return (
    <div className="admin-layout">
      <aside className={`admin-sidebar ${collapsed ? 'collapsed' : ''}`}>
        <div className="admin-sidebar-header">
          <div className="admin-brand" onClick={() => navigate('/')}>
            <Brain size={24} className="brand-icon" />
            {!collapsed && <span className="brand-text">ExecMind</span>}
          </div>
          <button
            className="btn btn-icon btn-ghost collapse-btn"
            onClick={() => setCollapsed(!collapsed)}
          >
            <ChevronLeft size={18} className={collapsed ? 'rotated' : ''} />
          </button>
        </div>

        <nav className="admin-nav">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.end}
              className={({ isActive }) =>
                `admin-nav-item ${isActive ? 'active' : ''}`
              }
            >
              <item.icon size={20} />
              {!collapsed && <span>{item.label}</span>}
            </NavLink>
          ))}
        </nav>

        <div className="admin-sidebar-divider" />

        <NavLink to="/" className="admin-nav-item back-link">
          <MessageSquare size={20} />
          {!collapsed && <span>Kembali ke Chat</span>}
        </NavLink>

        <div className="admin-sidebar-footer">
          <div className="admin-user-info">
            <div className="user-avatar">
              {user?.full_name?.charAt(0)?.toUpperCase() || 'A'}
            </div>
            {!collapsed && (
              <div className="user-details">
                <span className="user-name">{user?.full_name}</span>
                <span className="user-role">{user?.role}</span>
              </div>
            )}
          </div>
          {!collapsed && (
            <button className="btn btn-icon btn-ghost" onClick={logout} title="Keluar">
              <LogOut size={18} />
            </button>
          )}
        </div>
      </aside>

      <main className="admin-main">
        <Outlet />
      </main>
    </div>
  );
}
