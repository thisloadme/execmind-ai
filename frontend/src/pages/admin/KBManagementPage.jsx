import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Database, Plus, Trash2, Upload, FileText, FolderOpen,
  ChevronLeft, Search, AlertCircle, CheckCircle, Clock,
  Loader2, File, X,
} from 'lucide-react';
import { kbApi } from '../../services/api';
import '../admin/AdminLayout.css';

const STATUS_BADGE = {
  uploading: { label: 'Uploading', cls: 'badge-warning' },
  processing: { label: 'Processing', cls: 'badge-info' },
  indexed: { label: 'Indexed', cls: 'badge-success' },
  failed: { label: 'Failed', cls: 'badge-danger' },
};

const SENSITIVITY_LABEL = {
  public: 'Publik',
  internal: 'Internal',
  confidential: 'Rahasia',
  top_secret: 'Sangat Rahasia',
};

/**
 * Knowledge Base Management — Collections and document CRUD with drag-drop upload.
 */
export default function KBManagementPage() {
  const [collections, setCollections] = useState([]);
  const [selectedCollection, setSelectedCollection] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(null);
  const [dragging, setDragging] = useState(false);

  const fileInputRef = useRef(null);

  // ─── Form state for new collection ──────────
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [newSensitivity, setNewSensitivity] = useState('confidential');

  useEffect(() => {
    loadCollections();
  }, []);

  useEffect(() => {
    if (selectedCollection) {
      loadDocuments(selectedCollection.id);
    }
  }, [selectedCollection]);

  const loadCollections = async () => {
    setIsLoading(true);
    try {
      const data = await kbApi.listCollections();
      setCollections(data.collections || []);
    } catch (err) {
      console.error('Failed to load collections:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const loadDocuments = async (collectionId) => {
    try {
      const data = await kbApi.listDocuments(collectionId);
      setDocuments(data.documents || []);
    } catch (err) {
      console.error('Failed to load documents:', err);
    }
  };

  const handleCreateCollection = async (e) => {
    e.preventDefault();
    try {
      const data = await kbApi.createCollection({
        name: newName,
        description: newDesc || null,
        sensitivity: newSensitivity,
      });
      setCollections((prev) => [data, ...prev]);
      setShowCreateModal(false);
      setNewName('');
      setNewDesc('');
      setNewSensitivity('confidential');
    } catch (err) {
      alert(err.response?.data?.detail || 'Gagal membuat koleksi.');
    }
  };

  const handleDeleteCollection = async (collectionId) => {
    if (!confirm('Yakin ingin menghapus koleksi ini beserta semua dokumennya?')) return;
    try {
      await kbApi.deleteCollection(collectionId);
      setCollections((prev) => prev.filter((c) => c.id !== collectionId));
      if (selectedCollection?.id === collectionId) {
        setSelectedCollection(null);
        setDocuments([]);
      }
    } catch (err) {
      alert(err.response?.data?.detail || 'Gagal menghapus koleksi.');
    }
  };

  const handleFileUpload = async (files) => {
    if (!selectedCollection || !files.length) return;

    for (const file of files) {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('title', file.name);

      setUploadProgress({ name: file.name, progress: 0 });

      try {
        await kbApi.uploadDocument(
          selectedCollection.id,
          formData,
          (progressEvent) => {
            const pct = Math.round((progressEvent.loaded / progressEvent.total) * 100);
            setUploadProgress({ name: file.name, progress: pct });
          },
        );
        await loadDocuments(selectedCollection.id);
      } catch (err) {
        alert(`Gagal upload ${file.name}: ${err.response?.data?.detail || err.message}`);
      } finally {
        setUploadProgress(null);
      }
    }
  };

  const handleDeleteDocument = async (docId) => {
    if (!confirm('Yakin ingin menghapus dokumen ini?')) return;
    try {
      await kbApi.deleteDocument(docId);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
    } catch (err) {
      alert(err.response?.data?.detail || 'Gagal menghapus dokumen.');
    }
  };

  // ─── Drag & Drop ────────────────────────────
  const handleDragOver = (e) => {
    e.preventDefault();
    setDragging(true);
  };
  const handleDragLeave = () => setDragging(false);
  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    handleFileUpload(Array.from(e.dataTransfer.files));
  };

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (iso) => {
    if (!iso) return '-';
    return new Date(iso).toLocaleString('id-ID', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  };

  // ─── Collection Detail View ────────────────
  if (selectedCollection) {
    return (
      <div className="admin-page">
        <div className="admin-page-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <button
              className="btn btn-icon btn-ghost"
              onClick={() => { setSelectedCollection(null); setDocuments([]); }}
            >
              <ChevronLeft size={20} />
            </button>
            <div>
              <h1 className="admin-page-title">{selectedCollection.name}</h1>
              <p className="admin-page-subtitle">
                {selectedCollection.description || 'Tidak ada deskripsi'} ·{' '}
                <span className={`badge ${
                  selectedCollection.sensitivity === 'top_secret' ? 'badge-danger' :
                  selectedCollection.sensitivity === 'confidential' ? 'badge-warning' :
                  'badge-info'
                }`}>
                  {SENSITIVITY_LABEL[selectedCollection.sensitivity]}
                </span>
              </p>
            </div>
          </div>
        </div>

        {/* Upload Zone */}
        <div
          className={`upload-zone ${dragging ? 'dragging' : ''}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <Upload size={36} className="upload-zone-icon" />
          <div className="upload-zone-text">
            Seret file ke sini atau <strong>klik untuk memilih</strong>
          </div>
          <div className="upload-zone-hint">
            PDF, DOCX, XLSX, PPTX, TXT — Maksimal 50MB
          </div>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.xlsx,.pptx,.txt"
            style={{ display: 'none' }}
            onChange={(e) => handleFileUpload(Array.from(e.target.files))}
          />
        </div>

        {/* Upload Progress */}
        {uploadProgress && (
          <div style={{ marginBottom: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
              <Loader2 size={14} className="spin" />
              <span>Mengupload {uploadProgress.name}...</span>
              <span style={{ marginLeft: 'auto', color: 'var(--color-accent)' }}>
                {uploadProgress.progress}%
              </span>
            </div>
            <div className="progress-bar">
              <div className="progress-bar-fill" style={{ width: `${uploadProgress.progress}%` }} />
            </div>
          </div>
        )}

        {/* Documents Table */}
        <div className="data-table-wrapper">
          <div className="data-table-header">
            <span className="data-table-title">
              Dokumen ({documents.length})
            </span>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Nama File</th>
                <th>Ukuran</th>
                <th>Status</th>
                <th>Chunks</th>
                <th>Diupload</th>
                <th style={{ width: 60 }}></th>
              </tr>
            </thead>
            <tbody>
              {documents.length === 0 ? (
                <tr>
                  <td colSpan={6} className="data-table-empty">
                    <FileText size={32} style={{ opacity: 0.2, marginBottom: 8 }} />
                    <div>Belum ada dokumen. Upload file pertama Anda di atas.</div>
                  </td>
                </tr>
              ) : (
                documents.map((doc) => {
                  const statusInfo = STATUS_BADGE[doc.status] || { label: doc.status, cls: '' };
                  return (
                    <tr key={doc.id}>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <File size={16} style={{ color: 'var(--color-text-muted)', flexShrink: 0 }} />
                          <div>
                            <div style={{ fontWeight: 500 }}>{doc.title || doc.original_name}</div>
                            {doc.category && (
                              <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
                                {doc.category}
                              </div>
                            )}
                          </div>
                        </div>
                      </td>
                      <td style={{ whiteSpace: 'nowrap', fontSize: 13 }}>
                        {formatFileSize(doc.file_size)}
                      </td>
                      <td>
                        <span className={`badge ${statusInfo.cls}`}>{statusInfo.label}</span>
                        {doc.error_message && (
                          <div style={{ fontSize: 11, color: 'var(--color-danger)', marginTop: 2 }}>
                            {doc.error_message}
                          </div>
                        )}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: 13 }}>
                        {doc.chunk_count}
                      </td>
                      <td style={{ whiteSpace: 'nowrap', fontSize: 13 }}>
                        {formatDate(doc.created_at)}
                      </td>
                      <td>
                        <button
                          className="btn btn-icon btn-ghost btn-sm"
                          onClick={() => handleDeleteDocument(doc.id)}
                          title="Hapus dokumen"
                        >
                          <Trash2 size={14} />
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  // ─── Collections List View ─────────────────
  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <h1 className="admin-page-title">Knowledge Base</h1>
          <p className="admin-page-subtitle">Kelola koleksi dan dokumen yang dapat diakses oleh AI</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreateModal(true)}>
          <Plus size={18} />
          Buat Koleksi
        </button>
      </div>

      {isLoading ? (
        <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 60 }}>
          <div className="login-spinner" />
        </div>
      ) : collections.length === 0 ? (
        <div style={{
          textAlign: 'center', padding: '60px 20px', color: 'var(--color-text-muted)',
        }}>
          <Database size={48} style={{ opacity: 0.2, marginBottom: 12 }} />
          <p>Belum ada koleksi. Buat koleksi pertama untuk mulai mengupload dokumen.</p>
        </div>
      ) : (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
          gap: 16,
        }}>
          {collections.map((col) => (
            <div
              key={col.id}
              className="stat-card"
              style={{ cursor: 'pointer' }}
              onClick={() => setSelectedCollection(col)}
            >
              <div className="stat-card-header">
                <span className={`badge ${
                  col.sensitivity === 'top_secret' ? 'badge-danger' :
                  col.sensitivity === 'confidential' ? 'badge-warning' :
                  col.sensitivity === 'internal' ? 'badge-info' :
                  'badge-success'
                }`}>
                  {SENSITIVITY_LABEL[col.sensitivity]}
                </span>
                <button
                  className="btn btn-icon btn-ghost btn-sm"
                  onClick={(e) => { e.stopPropagation(); handleDeleteCollection(col.id); }}
                  title="Hapus koleksi"
                >
                  <Trash2 size={14} />
                </button>
              </div>
              <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>{col.name}</h3>
              {col.description && (
                <p style={{
                  fontSize: 13, color: 'var(--color-text-secondary)',
                  marginBottom: 12, lineHeight: 1.4,
                }}>
                  {col.description.length > 80
                    ? col.description.slice(0, 80) + '...'
                    : col.description}
                </p>
              )}
              <div style={{
                display: 'flex', alignItems: 'center', gap: 8,
                fontSize: 13, color: 'var(--color-text-muted)',
              }}>
                <FileText size={14} />
                <span>{col.document_count ?? 0} dokumen</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Collection Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2 className="modal-title">Buat Koleksi Baru</h2>
            <form className="modal-form" onSubmit={handleCreateCollection}>
              <div>
                <label className="label">Nama Koleksi *</label>
                <input
                  className="input"
                  placeholder="Contoh: Laporan Keuangan 2024"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  required
                  autoFocus
                />
              </div>
              <div>
                <label className="label">Deskripsi</label>
                <textarea
                  className="input"
                  placeholder="Deskripsi singkat tentang koleksi ini"
                  rows={3}
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  style={{ resize: 'vertical' }}
                />
              </div>
              <div>
                <label className="label">Tingkat Kerahasiaan</label>
                <select
                  className="input"
                  value={newSensitivity}
                  onChange={(e) => setNewSensitivity(e.target.value)}
                >
                  <option value="public">Publik</option>
                  <option value="internal">Internal</option>
                  <option value="confidential">Rahasia</option>
                  <option value="top_secret">Sangat Rahasia</option>
                </select>
              </div>
              <div className="modal-actions">
                <button type="button" className="btn btn-ghost" onClick={() => setShowCreateModal(false)}>
                  Batal
                </button>
                <button type="submit" className="btn btn-primary" disabled={!newName.trim()}>
                  <Plus size={16} />
                  Buat Koleksi
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
