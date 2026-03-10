import { create } from 'zustand';
import { authApi } from '../services/api';

/**
 * Global auth state store using Zustand.
 * Manages user session, tokens, and login/logout flows.
 */
const useAuthStore = create((set, get) => ({
  user: null,
  isAuthenticated: !!localStorage.getItem('access_token'),
  isLoading: true,

  /** Initialize auth state from stored token. */
  initialize: async () => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      set({ isAuthenticated: false, isLoading: false, user: null });
      return;
    }

    try {
      const user = await authApi.getMe();
      set({ user, isAuthenticated: true, isLoading: false });
    } catch {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },

  /** Login with credentials. */
  login: async (username, password) => {
    const data = await authApi.login(username, password);
    set({ user: data.user, isAuthenticated: true });
    return data;
  },

  /** Logout and clear tokens. */
  logout: async () => {
    await authApi.logout();
    set({ user: null, isAuthenticated: false });
  },
}));

export default useAuthStore;
