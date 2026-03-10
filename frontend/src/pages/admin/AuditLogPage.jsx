import { useState, useEffect } from 'react';
import {
  ClipboardList, Download, Filter, Calendar,
  ChevronLeft, ChevronRight,
} from 'lucide-react';
import { auditApi } from '../../services/api';
import '../admin/AdminLayout.css';

const ACTION_LABELS = {
  login: 'Login',
  logout: 'Logout',
  login_failed: 'Login Gagal',
  password_change: 'Ganti Password',
  doc_upload: 'Upload Dokumen',
  doc_delete: 'Hapus Dokumen',
  doc_update: 'Update Dokumen',
  doc_view: 'Lihat Dokumen',
  collection_create: 'Buat Koleksi',
  collection_delete: 'Hapus Koleksi',
  user_create: 'Buat User',
  user_update: 'Update User',
  user_deactivate: 'Nonaktifkan User',
  chat_query: 'Chat Query',
  export_audit_log: 'Export Audit',
};

/**
 * Audit Log Viewer with filtering, pagination, and CSV/JSON export.
 */
export default function AuditLogPage() {
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);

  // Filters
  const [filterAction, setFilterAction] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  const PER_PAGE = 50;

  useEffect(() => {
    loadLogs();
  }, [page, filterAction, startDate, endDate]);

  const loadLogs = async () => {
    setIsLoading(true);
    try {
      const params = { page, per_page: PER_PAGE };
      if (filterAction) params.action = filterAction;
      if (startDate) params.start_date = new Date(startDate).toISOString();
      if (endDate) params.end_date = new Date(endDate).toISOString();

      const data = await auditApi.listLogs(params);
      setLogs(data.logs || []);
      setTotal(data.total || 0);
    } catch (err) {
      console.error('Failed to load audit logs:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleExport = async (format) => {
    try {
      const response = await auditApi.exportLogs(format);
      const blob = new Blob(
        [typeof response.data === 'string' ? response.data : JSON.stringify(response.data, null, 2)],
        { type: format === 'csv' ? 'text/csv' : 'application/json' },
      );
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `audit_logs.${format}`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert('Gagal mengexport audit log.');
    }
  };

  const formatDate = (iso) => {
    if (!iso) return '-';
    return new Date(iso).toLocaleString('id-ID', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  };

  const getActionBadgeClass = (action) => {
    if (action?.includes('failed') || action?.includes('delete') || action?.includes('deactivate')) {
      return 'badge-danger';
    }
    if (action?.includes('create') || action?.includes('upload')) return 'badge-success';
    if (action?.includes('login') || action?.includes('logout')) return 'badge-info';
    return 'badge-warning';
  };

  const totalPages = Math.ceil(total / PER_PAGE);

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <h1 className="admin-page-title">Audit Log</h1>
          <p className="admin-page-subtitle">
            Riwayat seluruh aktivitas sistem ({total.toLocaleString()} entri)
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-ghost" onClick={() => handleExport('csv')}>
            <Download size={16} />
            Export CSV
          </button>
          <button className="btn btn-ghost" onClick={() => handleExport('json')}>
            <Download size={16} />
            Export JSON
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="filters-row">
        <select
          className="filter-select"
          value={filterAction}
          onChange={(e) => { setFilterAction(e.target.value); setPage(1); }}
        >
          <option value="">Semua Aksi</option>
          {Object.entries(ACTION_LABELS).map(([key, label]) => (
            <option key={key} value={key}>{label}</option>
          ))}
        </select>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Calendar size={14} style={{ color: 'var(--color-text-muted)' }} />
          <input
            type="date"
            className="filter-select"
            value={startDate}
            onChange={(e) => { setStartDate(e.target.value); setPage(1); }}
            style={{ minWidth: 140 }}
          />
          <span style={{ color: 'var(--color-text-muted)' }}>—</span>
          <input
            type="date"
            className="filter-select"
            value={endDate}
            onChange={(e) => { setEndDate(e.target.value); setPage(1); }}
            style={{ minWidth: 140 }}
          />
        </div>
      </div>

      {/* Logs Table */}
      <div className="data-table-wrapper">
        <table className="data-table">
          <thead>
            <tr>
              <th style={{ width: 180 }}>Waktu</th>
              <th>Aksi</th>
              <th>Resource</th>
              <th>User ID</th>
              <th>IP Address</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={6} className="data-table-empty">
                  <div className="login-spinner" style={{ margin: '0 auto' }} />
                </td>
              </tr>
            ) : logs.length === 0 ? (
              <tr>
                <td colSpan={6} className="data-table-empty">
                  <ClipboardList size={32} style={{ opacity: 0.2, marginBottom: 8 }} />
                  <div>Tidak ada log yang sesuai filter</div>
                </td>
              </tr>
            ) : (
              logs.map((log) => (
                <tr key={log.id}>
                  <td style={{ whiteSpace: 'nowrap', fontSize: 13 }}>
                    {formatDate(log.created_at)}
                  </td>
                  <td>
                    <span className={`badge ${getActionBadgeClass(log.action)}`}>
                      {ACTION_LABELS[log.action] || log.action}
                    </span>
                  </td>
                  <td style={{ color: 'var(--color-text-secondary)', fontSize: 13 }}>
                    {log.resource || '-'}
                  </td>
                  <td style={{
                    fontFamily: 'var(--font-mono)', fontSize: 12,
                    color: 'var(--color-text-muted)',
                    maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis',
                  }}>
                    {log.user_id ? log.user_id.slice(0, 8) + '...' : '-'}
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: 13 }}>
                    {log.ip_address || '-'}
                  </td>
                  <td style={{ fontSize: 12, color: 'var(--color-text-muted)', maxWidth: 200 }}>
                    {log.metadata && Object.keys(log.metadata).length > 0 ? (
                      <span title={JSON.stringify(log.metadata)}>
                        {JSON.stringify(log.metadata).slice(0, 60)}
                        {JSON.stringify(log.metadata).length > 60 ? '...' : ''}
                      </span>
                    ) : '-'}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="pagination">
            <button
              className="pagination-btn"
              disabled={page <= 1}
              onClick={() => setPage(page - 1)}
            >
              <ChevronLeft size={14} /> Sebelumnya
            </button>
            <span className="pagination-info">
              Halaman {page} dari {totalPages}
            </span>
            <button
              className="pagination-btn"
              disabled={page >= totalPages}
              onClick={() => setPage(page + 1)}
            >
              Selanjutnya <ChevronRight size={14} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
