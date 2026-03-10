import { useState, useEffect } from 'react';
import {
  BarChart3, MessageSquare, Users, FileText, Database,
  TrendingUp,
} from 'lucide-react';
import { auditApi, kbApi, usersApi } from '../../services/api';
import '../admin/AdminLayout.css';

/**
 * Admin dashboard with overview statistics and recent activity.
 */
export default function DashboardPage() {
  const [stats, setStats] = useState(null);
  const [recentLogs, setRecentLogs] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    setIsLoading(true);
    try {
      const [auditStats, logsData] = await Promise.all([
        auditApi.getStats(),
        auditApi.listLogs({ per_page: 10 }),
      ]);
      setStats(auditStats);
      setRecentLogs(logsData.logs || []);
    } catch (err) {
      console.error('Failed to load dashboard:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const formatDate = (iso) => {
    if (!iso) return '-';
    return new Date(iso).toLocaleString('id-ID', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  };

  const actionLabels = {
    login: 'Login',
    logout: 'Logout',
    login_failed: 'Login Gagal',
    doc_upload: 'Upload Dokumen',
    doc_delete: 'Hapus Dokumen',
    collection_create: 'Buat Koleksi',
    collection_delete: 'Hapus Koleksi',
    user_create: 'Buat User',
    user_update: 'Update User',
    user_deactivate: 'Nonaktifkan User',
    chat_query: 'Chat Query',
    password_change: 'Ganti Password',
    export_audit_log: 'Export Audit',
  };

  if (isLoading) {
    return (
      <div className="admin-page" style={{ display: 'flex', justifyContent: 'center', paddingTop: 80 }}>
        <div className="login-spinner" />
      </div>
    );
  }

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <h1 className="admin-page-title">Dashboard</h1>
          <p className="admin-page-subtitle">Ringkasan aktivitas sistem ExecMind</p>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-card-header">
            <span className="stat-card-label">Total Queries</span>
            <div className="stat-card-icon purple">
              <MessageSquare size={20} />
            </div>
          </div>
          <div className="stat-card-value">{stats?.total_queries ?? 0}</div>
        </div>

        <div className="stat-card">
          <div className="stat-card-header">
            <span className="stat-card-label">Pengguna Aktif</span>
            <div className="stat-card-icon blue">
              <Users size={20} />
            </div>
          </div>
          <div className="stat-card-value">{stats?.active_users ?? 0}</div>
        </div>

        <div className="stat-card">
          <div className="stat-card-header">
            <span className="stat-card-label">Dokumen Diupload</span>
            <div className="stat-card-icon green">
              <FileText size={20} />
            </div>
          </div>
          <div className="stat-card-value">{stats?.total_document_uploads ?? 0}</div>
        </div>

        <div className="stat-card">
          <div className="stat-card-header">
            <span className="stat-card-label">Total Login</span>
            <div className="stat-card-icon orange">
              <TrendingUp size={20} />
            </div>
          </div>
          <div className="stat-card-value">{stats?.total_logins ?? 0}</div>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="data-table-wrapper">
        <div className="data-table-header">
          <span className="data-table-title">Aktivitas Terbaru</span>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Waktu</th>
              <th>Aksi</th>
              <th>Resource</th>
              <th>IP Address</th>
            </tr>
          </thead>
          <tbody>
            {recentLogs.length === 0 ? (
              <tr>
                <td colSpan={4} className="data-table-empty">
                  Belum ada aktivitas tercatat
                </td>
              </tr>
            ) : (
              recentLogs.map((log) => (
                <tr key={log.id}>
                  <td style={{ whiteSpace: 'nowrap', fontSize: 13 }}>
                    {formatDate(log.created_at)}
                  </td>
                  <td>
                    <span className={`badge ${
                      log.action?.includes('failed') ? 'badge-danger' :
                      log.action?.includes('delete') || log.action?.includes('deactivate') ? 'badge-warning' :
                      'badge-info'
                    }`}>
                      {actionLabels[log.action] || log.action}
                    </span>
                  </td>
                  <td style={{ color: 'var(--color-text-secondary)' }}>
                    {log.resource || '-'}
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: 13 }}>
                    {log.ip_address || '-'}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
