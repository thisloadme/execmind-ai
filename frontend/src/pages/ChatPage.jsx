import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import TextareaAutosize from 'react-textarea-autosize';
import {
  Send, Plus, Trash2, MessageSquare, Brain, FileText,
  ThumbsUp, ThumbsDown, Loader2, ChevronDown, LogOut,
  Settings, BookOpen, Database, Paperclip, X, Image as ImageIcon, Download
} from 'lucide-react';
import useAuthStore from '../stores/authStore';
import { chatApi, kbApi } from '../services/api';
import './ChatPage.css';

/**
 * Main chat interface with sidebar, message list, and streaming input.
 * Supports RAG with collection selection and source citations.
 */
export default function ChatPage() {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();
  const isAdmin = user?.role === 'admin' || user?.role === 'superadmin';

  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [collections, setCollections] = useState([]);
  const [selectedCollection, setSelectedCollection] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [selectedFiles, setSelectedFiles] = useState([]);

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const fileInputRef = useRef(null);

  // ─── Load sessions and collections ─────────────

  useEffect(() => {
    loadSessions();
    loadCollections();
  }, []);

  const loadSessions = async () => {
    try {
      const data = await chatApi.listSessions();
      setSessions(data.sessions || []);
    } catch (err) {
      console.error('Failed to load sessions:', err);
    }
  };

  const loadCollections = async () => {
    try {
      const data = await kbApi.listCollections();
      setCollections(data.collections || []);
    } catch {
      /* Qdrant might not be ready */
    }
  };

  // ─── Session Management ────────────────────────

  const createNewSession = async () => {
    try {
      const data = await chatApi.createSession(
        'New Chat',
        selectedCollection?.id || null,
      );
      setSessions((prev) => [data, ...prev]);
      setActiveSessionId(data.id);
      setMessages([]);
      inputRef.current?.focus();
    } catch (err) {
      console.error('Failed to create session:', err);
    }
  };

  const selectSession = async (sessionId) => {
    setActiveSessionId(sessionId);
    try {
      const msgs = await chatApi.getMessages(sessionId);
      setMessages(msgs || []);
    } catch (err) {
      console.error('Failed to load messages:', err);
    }
  };

  const deleteSession = async (sessionId) => {
    try {
      await chatApi.deleteSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      if (activeSessionId === sessionId) {
        setActiveSessionId(null);
        setMessages([]);
      }
    } catch (err) {
      console.error('Failed to delete session:', err);
    }
  };

  // ─── Send Message with SSE Streaming ───────────

  const sendMessage = useCallback(async () => {
    if (!inputValue.trim() || isStreaming) return;

    let currentSessionId = activeSessionId;

    // Auto-create session if none active
    if (!currentSessionId) {
      try {
        const data = await chatApi.createSession(
          inputValue.slice(0, 80),
          selectedCollection?.id || null,
        );
        currentSessionId = data.id;
        setSessions((prev) => [data, ...prev]);
        setActiveSessionId(data.id);
      } catch {
        return;
      }
    }

    // Capture files early
    const filesToSend = [...selectedFiles];
    setSelectedFiles([]);

    const userMessage = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: inputValue,
      attachments: filesToSend.map(f => ({ filename: f.name, content_type: f.type })),
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setIsStreaming(true);

    const assistantMessage = {
      id: `temp-assistant-${Date.now()}`,
      role: 'assistant',
      content: '',
      sources: [],
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, assistantMessage]);

    try {
      const reader = await chatApi.sendMessage(currentSessionId, userMessage.content, filesToSend);
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Parse SSE events
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        let eventType = '';
        let isDone = false;
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            const dataStr = line.slice(6);
            try {
              const data = JSON.parse(dataStr);

              if (eventType === 'token') {
                setMessages((prev) => {
                  const updated = [...prev];
                  const last = updated[updated.length - 1];
                  if (last && last.role === 'assistant') {
                    updated[updated.length - 1] = {
                      ...last,
                      content: last.content + data.content,
                    };
                  }
                  return updated;
                });
              } else if (eventType === 'sources') {
                setMessages((prev) => {
                  const updated = [...prev];
                  const last = updated[updated.length - 1];
                  if (last && last.role === 'assistant') {
                    updated[updated.length - 1] = {
                      ...last,
                      sources: data.sources,
                    };
                  }
                  return updated;
                });
              } else if (eventType === 'done') {
                isDone = true;
              }
            } catch { /* ignore parse errors */ }
          }
        }

        if (isDone) {
          try { await reader.cancel(); } catch { /* ignore cancel errors */ }
          break;
        }
      }
    } catch (err) {
      console.error('Streaming error:', err);
      setMessages((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last && last.role === 'assistant') {
          updated[updated.length - 1] = {
            ...last,
            content: '⚠️ Terjadi kesalahan. Silakan coba lagi.',
          };
        }
        return updated;
      });
    } finally {
      setIsStreaming(false);
      loadSessions(); // Refresh session list for title update
    }
  }, [inputValue, isStreaming, activeSessionId, selectedCollection]);

  // ─── Handle keyboard shortcuts ─────────────────

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
    if (e.key === 'n' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      createNewSession();
    }
  };

  // ─── Handle File Upload ──────────────────────────

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      const newFiles = Array.from(e.target.files);
      const allowedTypes = [
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'text/plain',
        'image/png',
        'image/jpeg',
        'image/jpg',
      ];
      
      const validFiles = newFiles.filter(file => allowedTypes.includes(file.type));
      if (validFiles.length < newFiles.length) {
        alert('Beberapa format file tidak didukung. Harap unggah PDF, DOCX, XLSX, PPTX, TXT, PNG, atau JPG.');
      }
      
      setSelectedFiles(prev => [...prev, ...validFiles]);
    }
    // Reset input so the same file can be selected again if removed
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const removeFile = (index) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
  };

  // ─── Auto-scroll ───────────────────────────────

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ─── Render ────────────────────────────────────

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className={`sidebar ${sidebarOpen ? 'open' : 'closed'}`}>
        <div className="sidebar-header">
          <div className="sidebar-brand">
            <Brain size={24} className="brand-icon" />
            <span className="brand-text">ExecMind</span>
          </div>
          <button className="btn btn-icon btn-ghost" onClick={createNewSession} title="New Chat (Ctrl+N)">
            <Plus size={20} />
          </button>
        </div>

        {/* Collection Selector */}
        {collections.length > 0 && (
          <div className="sidebar-section">
            <label className="label" style={{ padding: '0 12px' }}>
              <Database size={14} style={{ marginRight: 4, verticalAlign: 'middle' }} />
              Knowledge Base
            </label>
            <select
              className="input collection-select"
              value={selectedCollection?.id || ''}
              onChange={(e) => {
                const col = collections.find(c => c.id === e.target.value);
                setSelectedCollection(col || null);
              }}
            >
              <option value="">Semua (tanpa RAG)</option>
              {collections.map((col) => (
                <option key={col.id} value={col.id}>{col.name}</option>
              ))}
            </select>
          </div>
        )}

        {/* Session List */}
        <div className="session-list">
          {sessions.map((session) => (
            <div
              key={session.id}
              className={`session-item ${session.id === activeSessionId ? 'active' : ''}`}
              onClick={() => selectSession(session.id)}
            >
              <MessageSquare size={16} className="session-icon" />
              <span className="session-title">{session.title}</span>
              <button
                className="session-delete"
                onClick={(e) => {
                  e.stopPropagation();
                  deleteSession(session.id);
                }}
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}

          {sessions.length === 0 && (
            <div className="sidebar-empty">
              <MessageSquare size={32} style={{ opacity: 0.2 }} />
              <p>Belum ada percakapan</p>
            </div>
          )}
        </div>

        {/* Admin Link */}
        {isAdmin && (
          <div style={{ padding: '8px' }}>
            <button
              className="btn btn-ghost"
              style={{ width: '100%', justifyContent: 'flex-start', fontSize: 13 }}
              onClick={() => navigate('/admin')}
            >
              <Settings size={16} />
              Admin Panel
            </button>
          </div>
        )}

        {/* User Footer */}
        <div className="sidebar-footer">
          <div className="user-info">
            <div className="user-avatar">
              {user?.full_name?.charAt(0)?.toUpperCase() || 'U'}
            </div>
            <div className="user-details">
              <span className="user-name">{user?.full_name || 'User'}</span>
              <span className="user-role">{user?.role || 'executive'}</span>
            </div>
          </div>
          <button className="btn btn-icon btn-ghost" onClick={logout} title="Keluar">
            <LogOut size={18} />
          </button>
        </div>
      </aside>

      {/* Main Chat Area */}
      <main className="chat-main">
        {activeSessionId || messages.length > 0 ? (
          <>
            {/* Messages */}
            <div className="messages-container">
              {messages.map((msg, idx) => (
                <div
                  key={msg.id || idx}
                  className={`message ${msg.role} animate-fade-in`}
                >
                  <div className="message-avatar">
                    {msg.role === 'user' ? (
                      user?.full_name?.charAt(0)?.toUpperCase() || 'U'
                    ) : (
                      <Brain size={18} />
                    )}
                  </div>
                  <div className="message-body">
                    <div className="message-header">
                      <span className="message-role">
                        {msg.role === 'user' ? (user?.full_name || 'Anda') : 'ExecMind'}
                      </span>
                      {msg.created_at && (
                        <span className="message-time">
                          {new Date(msg.created_at).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      )}
                    </div>
                    <div className="message-content markdown-content">
                      {msg.role === 'assistant' && !msg.content && isStreaming ? (
                        <div className="streaming-indicator">
                          <Loader2 size={16} className="spin" />
                          <span>Menyusun jawaban...</span>
                        </div>
                      ) : (
                        <ReactMarkdown>{msg.content}</ReactMarkdown>
                      )}
                    </div>

                    {/* Attachments Display */}
                    {msg.role === 'user' && msg.attachments && msg.attachments.length > 0 && (
                      <div className="message-attachments">
                        {msg.attachments.map((att, i) => {
                          const isImage = att.content_type?.startsWith('image/') || att.filename.match(/\.(jpg|jpeg|png)$/i);
                          // Handle temp messages via Object URL if we needed to, but for simplicity let's rely on DB load
                          // If it's a temp message it might not have the path yet, but that's fine for the immediate visual feedback
                          const downloadUrl = activeSessionId && att.filename ? 
                            `${import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'}/chat/sessions/${activeSessionId}/attachments/${encodeURIComponent(att.filename)}` : null;
                          
                          return (
                            <a 
                              key={i} 
                              href={downloadUrl} 
                              target="_blank" 
                              rel="noreferrer" 
                              className="attachment-card"
                              title="Download lampiran"
                            >
                              {isImage ? (
                                <ImageIcon size={16} className="attachment-icon" />
                              ) : (
                                <FileText size={16} className="attachment-icon" />
                              )}
                              <span className="attachment-name">{att.filename}</span>
                              <Download size={14} className="attachment-download" />
                            </a>
                          );
                        })}
                      </div>
                    )}

                    {/* Source Citations */}
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="source-citations">
                        <div className="sources-label">
                          <FileText size={14} />
                          <span>Sumber Dokumen</span>
                        </div>
                        <div className="sources-list">
                          {msg.sources.map((source, i) => (
                            <div key={i} className="source-card">
                              <div className="source-title">{source.doc_title}</div>
                              <div className="source-meta">
                                {source.page > 0 && <span>Hal. {source.page}</span>}
                                <span className="source-score">
                                  Relevansi: {(source.score * 100).toFixed(0)}%
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Feedback */}
                    {msg.role === 'assistant' && msg.content && !isStreaming && (
                      <div className="message-actions">
                        <button className="btn btn-icon btn-ghost btn-sm feedback-btn">
                          <ThumbsUp size={14} />
                        </button>
                        <button className="btn btn-icon btn-ghost btn-sm feedback-btn">
                          <ThumbsDown size={14} />
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="input-area">
              {selectedFiles.length > 0 && (
                <div className="file-preview-container">
                  {selectedFiles.map((file, idx) => (
                    <div key={idx} className="file-preview-chip">
                      {file.type.startsWith('image/') ? (
                        <ImageIcon size={14} className="file-icon" />
                      ) : (
                        <FileText size={14} className="file-icon" />
                      )}
                      <span className="file-name" title={file.name}>{file.name}</span>
                      <button 
                        className="file-remove-btn" 
                        onClick={() => removeFile(idx)}
                        disabled={isStreaming}
                      >
                        <X size={12} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <div className="input-wrapper">
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileChange}
                  style={{ display: 'none' }}
                  multiple
                  accept=".pdf,.doc,.docx,.xlsx,.pptx,.txt,image/png,image/jpeg,image/jpg"
                />
                <button
                  className="attach-btn"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isStreaming}
                  title="Lampirkan Dokumen/Gambar"
                >
                  <Paperclip size={20} />
                </button>
                <TextareaAutosize
                  ref={inputRef}
                  className="chat-input"
                  placeholder="Tanyakan sesuatu tentang dokumen Anda..."
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={handleKeyDown}
                  maxRows={6}
                  disabled={isStreaming}
                />
                <button
                  className="send-btn"
                  onClick={sendMessage}
                  disabled={(!inputValue.trim() && selectedFiles.length === 0) || isStreaming}
                >
                  {isStreaming ? (
                    <Loader2 size={20} className="spin" />
                  ) : (
                    <Send size={20} />
                  )}
                </button>
              </div>
              <div className="input-hint">
                <span>Enter untuk kirim • Shift+Enter baris baru • Ctrl+N chat baru</span>
              </div>
            </div>
          </>
        ) : (
          /* Welcome Screen */
          <div className="welcome-screen">
            <div className="welcome-logo">
              <Brain size={48} />
            </div>
            <h2 className="welcome-title">Selamat Datang di ExecMind</h2>
            <p className="welcome-subtitle">
              Asisten AI pribadi untuk mengakses dan menganalisis dokumen internal Anda.
              Semua data diproses secara lokal — tidak ada yang dikirim ke internet.
            </p>
            <div className="welcome-features">
              <div className="feature-card">
                <BookOpen size={24} />
                <h3>Tanya Dokumen</h3>
                <p>Ajukan pertanyaan dan dapatkan jawaban dari dokumen internal</p>
              </div>
              <div className="feature-card">
                <FileText size={24} />
                <h3>Sitasi Sumber</h3>
                <p>Setiap jawaban dilengkapi dengan referensi dokumen sumber</p>
              </div>
              <div className="feature-card">
                <Database size={24} />
                <h3>Knowledge Base</h3>
                <p>Pilih koleksi dokumen yang relevan untuk konteks pencarian</p>
              </div>
            </div>
            <button className="btn btn-primary" onClick={createNewSession}>
              <Plus size={18} />
              Mulai Percakapan Baru
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
