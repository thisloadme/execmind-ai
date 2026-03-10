import axios from 'axios';

const API_BASE_URL = '/api/v1';

/** Axios instance with JWT interceptors. */
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

// ─── Request Interceptor: Attach access token ───
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ─── Response Interceptor: Auto-refresh on 401 ───
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = localStorage.getItem('refresh_token');
        if (!refreshToken) {
          throw new Error('No refresh token');
        }

        const { data } = await axios.post(`${API_BASE_URL}/auth/refresh`, {
          refresh_token: refreshToken,
        });

        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('refresh_token', data.refresh_token);
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`;

        return api(originalRequest);
      } catch {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
      }
    }

    return Promise.reject(error);
  }
);

// ─── Auth API ─────────────────────────────────────

/** Login and store tokens. */
export const authApi = {
  login: async (username, password) => {
    const { data } = await api.post('/auth/login', { username, password });
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);
    return data;
  },

  logout: async () => {
    try {
      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken) {
        await api.post('/auth/logout', { refresh_token: refreshToken });
      }
    } finally {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
    }
  },

  getMe: () => api.get('/auth/me').then(r => r.data),

  changePassword: (oldPassword, newPassword) =>
    api.post('/auth/change-password', {
      old_password: oldPassword,
      new_password: newPassword,
    }),
};

// ─── Chat API ─────────────────────────────────────

export const chatApi = {
  listSessions: () => api.get('/chat/sessions').then(r => r.data),

  createSession: (title = 'New Chat', collectionId = null) =>
    api.post('/chat/sessions', { title, collection_id: collectionId }).then(r => r.data),

  getSession: (sessionId) => api.get(`/chat/sessions/${sessionId}`).then(r => r.data),

  getMessages: (sessionId) => api.get(`/chat/sessions/${sessionId}/messages`).then(r => r.data),

  deleteSession: (sessionId) => api.delete(`/chat/sessions/${sessionId}`),

  /**
   * Send a message and return an EventSource-like reader for SSE.
   * Uses fetch + ReadableStream since EventSource doesn't support POST.
   */
  sendMessage: async (sessionId, content, files = []) => {
    const token = localStorage.getItem('access_token');
    
    const formData = new FormData();
    formData.append('content', content);
    files.forEach(file => {
      formData.append('files', file);
    });

    const response = await fetch(`${API_BASE_URL}/chat/sessions/${sessionId}/messages`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    return response.body.getReader();
  },

  submitFeedback: (messageId, feedback) =>
    api.patch(`/chat/messages/${messageId}/feedback`, { feedback }),
};

// ─── KB API ───────────────────────────────────────

export const kbApi = {
  listCollections: () => api.get('/kb/collections').then(r => r.data),
  createCollection: (data) => api.post('/kb/collections', data).then(r => r.data),
  getCollection: (id) => api.get(`/kb/collections/${id}`).then(r => r.data),
  deleteCollection: (id) => api.delete(`/kb/collections/${id}`),

  listDocuments: (collectionId) =>
    api.get(`/kb/collections/${collectionId}/documents`).then(r => r.data),
  uploadDocument: (collectionId, formData, onProgress) =>
    api.post(`/kb/collections/${collectionId}/documents`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: onProgress,
    }).then(r => r.data),
  deleteDocument: (docId) => api.delete(`/kb/documents/${docId}`),
};

// ─── Users API ────────────────────────────────────

export const usersApi = {
  listUsers: (params) => api.get('/users', { params }).then(r => r.data),
  createUser: (data) => api.post('/users', data).then(r => r.data),
  updateUser: (id, data) => api.put(`/users/${id}`, data).then(r => r.data),
  deleteUser: (id) => api.delete(`/users/${id}`),
};

// ─── Audit API ────────────────────────────────────

export const auditApi = {
  listLogs: (params) => api.get('/audit/logs', { params }).then(r => r.data),
  getStats: () => api.get('/audit/stats').then(r => r.data),
  exportLogs: (format = 'json') => api.get('/audit/logs/export', { params: { format } }),
};

export default api;
