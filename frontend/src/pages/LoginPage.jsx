import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Brain, Eye, EyeOff, LogIn, Shield } from 'lucide-react';
import useAuthStore from '../stores/authStore';
import './LoginPage.css';

/**
 * Login page with username/password authentication.
 * Displays ExecMind branding with a clean dark form.
 */
export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const login = useAuthStore((s) => s.login);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      await login(username, password);
      navigate('/');
    } catch (err) {
      const message = err.response?.data?.detail || 'Login gagal. Periksa kembali kredensial Anda.';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-bg-effects">
        <div className="bg-orb bg-orb-1" />
        <div className="bg-orb bg-orb-2" />
        <div className="bg-orb bg-orb-3" />
      </div>

      <div className="login-container">
        <div className="login-card">
          <div className="login-header">
            <div className="login-logo">
              <Brain size={32} />
            </div>
            <h1 className="login-title">ExecMind</h1>
            <p className="login-subtitle">Private AI Knowledge Assistant</p>
          </div>

          <form onSubmit={handleSubmit} className="login-form">
            {error && (
              <div className="login-error animate-fade-in">
                <Shield size={16} />
                <span>{error}</span>
              </div>
            )}

            <div className="form-group">
              <label className="label" htmlFor="username">Username</label>
              <input
                id="username"
                type="text"
                className="input"
                placeholder="Masukkan username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
                required
              />
            </div>

            <div className="form-group">
              <label className="label" htmlFor="password">Password</label>
              <div className="password-wrapper">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  className="input"
                  placeholder="Masukkan password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
                <button
                  type="button"
                  className="password-toggle"
                  onClick={() => setShowPassword(!showPassword)}
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              className="btn btn-primary login-btn"
              disabled={isLoading || !username || !password}
            >
              {isLoading ? (
                <span className="login-spinner" />
              ) : (
                <>
                  <LogIn size={18} />
                  Masuk
                </>
              )}
            </button>
          </form>

          <div className="login-footer">
            <Shield size={14} />
            <span>Sistem berjalan 100% on-premise. Data tidak dikirim ke internet.</span>
          </div>
        </div>
      </div>
    </div>
  );
}
