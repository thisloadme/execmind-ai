import { useState, useEffect } from 'react';
import {
  Users, Plus, Trash2, Edit2, Shield, ShieldCheck,
  ShieldAlert, Lock, Unlock, X, UserCheck, UserX,
} from 'lucide-react';
import { usersApi } from '../../services/api';
import useAuthStore from '../../stores/authStore';
import '../admin/AdminLayout.css';

const ROLE_LABELS = {
  superadmin: { label: 'Super Admin', cls: 'badge-danger' },
  admin: { label: 'Admin', cls: 'badge-warning' },
  executive: { label: 'Eksekutif', cls: 'badge-info' },
  viewer: { label: 'Viewer', cls: 'badge-success' },
};

const STATUS_LABELS = {
  active: { label: 'Aktif', cls: 'badge-success' },
  inactive: { label: 'Nonaktif', cls: 'badge-warning' },
  locked: { label: 'Terkunci', cls: 'badge-danger' },
};

/**
 * User Management page — CRUD users with role and status controls.
 */
export default function UserManagementPage() {
  const currentUser = useAuthStore((s) => s.user);

  const [users, setUsers] = useState([]);
  const [totalUsers, setTotalUsers] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingUser, setEditingUser] = useState(null);

  // Filters
  const [filterStatus, setFilterStatus] = useState('');
  const [filterRole, setFilterRole] = useState('');

  // Create form
  const [formData, setFormData] = useState({
    username: '', email: '', password: '', full_name: '',
    position: '', unit: '', role: 'executive',
  });

  const PER_PAGE = 20;

  useEffect(() => {
    loadUsers();
  }, [page, filterStatus, filterRole]);

  const loadUsers = async () => {
    setIsLoading(true);
    try {
      const params = { page, per_page: PER_PAGE };
      if (filterStatus) params.status = filterStatus;
      if (filterRole) params.role = filterRole;

      const data = await usersApi.listUsers(params);
      setUsers(data.users || []);
      setTotalUsers(data.total || 0);
    } catch (err) {
      console.error('Failed to load users:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateUser = async (e) => {
    e.preventDefault();
    try {
      await usersApi.createUser(formData);
      setShowCreateModal(false);
      resetForm();
      loadUsers();
    } catch (err) {
      alert(err.response?.data?.detail || 'Gagal membuat user.');
    }
  };

  const handleUpdateUser = async (e) => {
    e.preventDefault();
    if (!editingUser) return;
    try {
      const updateData = {};
      if (formData.email) updateData.email = formData.email;
      if (formData.full_name) updateData.full_name = formData.full_name;
      if (formData.position) updateData.position = formData.position;
      if (formData.unit) updateData.unit = formData.unit;
      if (formData.role) updateData.role = formData.role;

      await usersApi.updateUser(editingUser.id, updateData);
      setEditingUser(null);
      resetForm();
      loadUsers();
    } catch (err) {
      alert(err.response?.data?.detail || 'Gagal mengupdate user.');
    }
  };

  const handleDeleteUser = async (userId) => {
    if (!confirm('Yakin ingin menghapus user ini? Aksi tidak dapat dikembalikan.')) return;
    try {
      await usersApi.deleteUser(userId);
      loadUsers();
    } catch (err) {
      alert(err.response?.data?.detail || 'Gagal menghapus user.');
    }
  };

  const openEditModal = (user) => {
    setEditingUser(user);
    setFormData({
      username: user.username,
      email: user.email,
      full_name: user.full_name,
      position: user.position || '',
      unit: user.unit || '',
      role: user.role,
      password: '',
    });
  };

  const resetForm = () => {
    setFormData({
      username: '', email: '', password: '', full_name: '',
      position: '', unit: '', role: 'executive',
    });
  };

  const formatDate = (iso) => {
    if (!iso) return '-';
    return new Date(iso).toLocaleString('id-ID', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  };

  const totalPages = Math.ceil(totalUsers / PER_PAGE);

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <h1 className="admin-page-title">Manajemen Pengguna</h1>
          <p className="admin-page-subtitle">Kelola akun pengguna dan hak akses</p>
        </div>
        <button className="btn btn-primary" onClick={() => { resetForm(); setShowCreateModal(true); }}>
          <Plus size={18} />
          Tambah User
        </button>
      </div>

      {/* Filters */}
      <div className="filters-row">
        <select
          className="filter-select"
          value={filterStatus}
          onChange={(e) => { setFilterStatus(e.target.value); setPage(1); }}
        >
          <option value="">Semua Status</option>
          <option value="active">Aktif</option>
          <option value="inactive">Nonaktif</option>
          <option value="locked">Terkunci</option>
        </select>
        <select
          className="filter-select"
          value={filterRole}
          onChange={(e) => { setFilterRole(e.target.value); setPage(1); }}
        >
          <option value="">Semua Role</option>
          <option value="superadmin">Super Admin</option>
          <option value="admin">Admin</option>
          <option value="executive">Eksekutif</option>
          <option value="viewer">Viewer</option>
        </select>
      </div>

      {/* Users Table */}
      <div className="data-table-wrapper">
        <table className="data-table">
          <thead>
            <tr>
              <th>User</th>
              <th>Role</th>
              <th>Status</th>
              <th>Unit</th>
              <th>Login Terakhir</th>
              <th style={{ width: 100 }}>Aksi</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={6} className="data-table-empty">
                  <div className="login-spinner" style={{ margin: '0 auto' }} />
                </td>
              </tr>
            ) : users.length === 0 ? (
              <tr>
                <td colSpan={6} className="data-table-empty">
                  Tidak ada pengguna ditemukan
                </td>
              </tr>
            ) : (
              users.map((u) => {
                const roleInfo = ROLE_LABELS[u.role] || { label: u.role, cls: '' };
                const statusInfo = STATUS_LABELS[u.status] || { label: u.status, cls: '' };
                const isSelf = u.id === currentUser?.id;

                return (
                  <tr key={u.id}>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <div className="user-avatar" style={{ width: 32, height: 32, fontSize: 12, borderRadius: 8 }}>
                          {u.full_name?.charAt(0)?.toUpperCase() || 'U'}
                        </div>
                        <div>
                          <div style={{ fontWeight: 500 }}>
                            {u.full_name}
                            {isSelf && (
                              <span style={{ fontSize: 11, color: 'var(--color-accent)', marginLeft: 6 }}>
                                (Anda)
                              </span>
                            )}
                          </div>
                          <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
                            @{u.username} · {u.email}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <span className={`badge ${roleInfo.cls}`}>{roleInfo.label}</span>
                    </td>
                    <td>
                      <span className={`badge ${statusInfo.cls}`}>{statusInfo.label}</span>
                    </td>
                    <td style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
                      {u.unit || '-'}
                    </td>
                    <td style={{ whiteSpace: 'nowrap', fontSize: 13 }}>
                      {formatDate(u.last_login_at)}
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: 4 }}>
                        <button
                          className="btn btn-icon btn-ghost btn-sm"
                          onClick={() => openEditModal(u)}
                          title="Edit user"
                        >
                          <Edit2 size={14} />
                        </button>
                        {!isSelf && currentUser?.role === 'superadmin' && (
                          <button
                            className="btn btn-icon btn-ghost btn-sm"
                            onClick={() => handleDeleteUser(u.id)}
                            title="Hapus user"
                            style={{ color: 'var(--color-danger)' }}
                          >
                            <Trash2 size={14} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })
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
              ‹ Sebelumnya
            </button>
            <span className="pagination-info">
              Halaman {page} dari {totalPages}
            </span>
            <button
              className="pagination-btn"
              disabled={page >= totalPages}
              onClick={() => setPage(page + 1)}
            >
              Selanjutnya ›
            </button>
          </div>
        )}
      </div>

      {/* Create User Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2 className="modal-title">Tambah Pengguna Baru</h2>
            <form className="modal-form" onSubmit={handleCreateUser}>
              <div>
                <label className="label">Username *</label>
                <input
                  className="input" required autoFocus
                  placeholder="contoh: joko.widodo"
                  value={formData.username}
                  onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                />
              </div>
              <div>
                <label className="label">Email *</label>
                <input
                  className="input" type="email" required
                  placeholder="contoh: joko@lembaga.go.id"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                />
              </div>
              <div>
                <label className="label">Nama Lengkap *</label>
                <input
                  className="input" required
                  placeholder="Nama lengkap pengguna"
                  value={formData.full_name}
                  onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                />
              </div>
              <div>
                <label className="label">Password *</label>
                <input
                  className="input" type="password" required
                  placeholder="Minimal 8 karakter"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label className="label">Jabatan</label>
                  <input
                    className="input"
                    placeholder="Contoh: Direktur"
                    value={formData.position}
                    onChange={(e) => setFormData({ ...formData, position: e.target.value })}
                  />
                </div>
                <div>
                  <label className="label">Unit</label>
                  <input
                    className="input"
                    placeholder="Contoh: Keuangan"
                    value={formData.unit}
                    onChange={(e) => setFormData({ ...formData, unit: e.target.value })}
                  />
                </div>
              </div>
              <div>
                <label className="label">Role</label>
                <select
                  className="input"
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                >
                  <option value="executive">Eksekutif</option>
                  <option value="viewer">Viewer</option>
                  <option value="admin">Admin</option>
                  {currentUser?.role === 'superadmin' && (
                    <option value="superadmin">Super Admin</option>
                  )}
                </select>
              </div>
              <div className="modal-actions">
                <button type="button" className="btn btn-ghost" onClick={() => setShowCreateModal(false)}>
                  Batal
                </button>
                <button type="submit" className="btn btn-primary">
                  <Plus size={16} />
                  Tambah User
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit User Modal */}
      {editingUser && (
        <div className="modal-overlay" onClick={() => setEditingUser(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2 className="modal-title">Edit Pengguna: {editingUser.full_name}</h2>
            <form className="modal-form" onSubmit={handleUpdateUser}>
              <div>
                <label className="label">Email</label>
                <input
                  className="input" type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                />
              </div>
              <div>
                <label className="label">Nama Lengkap</label>
                <input
                  className="input"
                  value={formData.full_name}
                  onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label className="label">Jabatan</label>
                  <input
                    className="input"
                    value={formData.position}
                    onChange={(e) => setFormData({ ...formData, position: e.target.value })}
                  />
                </div>
                <div>
                  <label className="label">Unit</label>
                  <input
                    className="input"
                    value={formData.unit}
                    onChange={(e) => setFormData({ ...formData, unit: e.target.value })}
                  />
                </div>
              </div>
              <div>
                <label className="label">Role</label>
                <select
                  className="input"
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                >
                  <option value="executive">Eksekutif</option>
                  <option value="viewer">Viewer</option>
                  <option value="admin">Admin</option>
                  {currentUser?.role === 'superadmin' && (
                    <option value="superadmin">Super Admin</option>
                  )}
                </select>
              </div>
              <div className="modal-actions">
                <button type="button" className="btn btn-ghost" onClick={() => setEditingUser(null)}>
                  Batal
                </button>
                <button type="submit" className="btn btn-primary">
                  Simpan Perubahan
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
