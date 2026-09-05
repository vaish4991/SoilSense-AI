import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import '../components/AuthPages.css';

// ── Google SVG Icon ──────────────────────────────────────────
function GoogleIcon() {
  return (
    <svg className="google-icon" viewBox="0 0 48 48">
      <path fill="#FFC107" d="M43.6 20.2H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.1 7.9 3l5.7-5.7C34.1 6.5 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.6-.4-3.8z"/>
      <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.6 16 19 13 24 13c3.1 0 5.8 1.1 7.9 3l5.7-5.7C34.1 6.5 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/>
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.3 35.5 26.8 36 24 36c-5.2 0-9.6-3.3-11.3-8H6.1C9.5 37.4 16.2 44 24 44z"/>
      <path fill="#1976D2" d="M43.6 20.2H42V20H24v8h11.3c-.9 2.4-2.5 4.5-4.6 5.9l6.2 5.2C36.7 40.1 44 34 44 24c0-1.3-.1-2.6-.4-3.8z"/>
    </svg>
  );
}

// ── Main Login Component ─────────────────────────────────────
export default function LoginPage() {
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [showPwd, setShowPwd]   = useState(false);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');

  const { login, loginWithGoogle } = useAuth();
  const navigate = useNavigate();

  const friendlyError = (err) => {
    const code = err?.code;
    const msg = err?.message;

    if (code === 'auth/firebase-not-configured') {
      return 'Real-Time Google Sign-In requires active Firebase credentials. Please add VITE_FIREBASE_API_KEY and VITE_FIREBASE_PROJECT_ID to your .env file.';
    }
    if (code === 'auth/user-not-found') {
      return 'No account found with this email. Please click the "Create Account" tab above to register first.';
    }
    if (code === 'auth/wrong-password' || code === 'auth/invalid-credential') {
      return 'Incorrect password. Please verify your credentials and try again.';
    }
    if (code === 'auth/invalid-email') {
      return 'Please enter a valid email address.';
    }
    if (code === 'auth/too-many-requests') {
      return 'Too many failed login attempts. Please wait a moment before trying again.';
    }
    return msg || 'Sign in failed. Please verify your email and password.';
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email, password);
      navigate('/');
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setLoading(false);
    }
  };

  const handleGoogle = async () => {
    setError('');
    setLoading(true);
    try {
      await loginWithGoogle();
      navigate('/');
    } catch (err) {
      if (err.code !== 'auth/popup-closed-by-user') {
        setError(friendlyError(err));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      {/* Left: Feature panel (desktop only) */}
      <div className="auth-features">
        <div>
          <div className="auth-feature-title">
            AI-powered<br /><span>Soil Intelligence</span>
          </div>
          <p className="auth-feature-desc">
            Join agronomists and researchers using real USDA laboratory records with strict conformal prediction.
          </p>
        </div>
        <div className="auth-feature-list">
          {[
            { icon: '🧪', title: 'USDA SSURGO Ground Truth', desc: '6,000+ laboratory soil benchmark records' },
            { icon: '🤖', title: 'Strict Conformal ML',        desc: 'Calibrated uncertainty intervals (q=0.6644)' },
            { icon: '🌾', title: 'Crop Advisory Engine',      desc: 'Agronomic suitability matching' },
            { icon: '🌦️', title: 'Hyperlocal Climate API',    desc: 'Live precipitation & temperature telemetry' },
          ].map((f) => (
            <div className="auth-feature-item" key={f.title}>
              <div className="auth-feature-icon">{f.icon}</div>
              <div className="auth-feature-item-text">
                <strong>{f.title}</strong>
                <span>{f.desc}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Right: Auth card */}
      <div className="auth-card">
        {/* Brand */}
        <div className="auth-logo">
          <div className="auth-logo-icon">🌱</div>
          <div className="auth-logo-text">
            <span className="auth-logo-name">SoilSense AI</span>
            <span className="auth-logo-sub">Razorpay AI Buildathon 2026</span>
          </div>
        </div>

        {/* ── HIGH VISIBILITY MODE TABS ── */}
        <div className="auth-mode-tabs" role="tablist">
          <button
            type="button"
            className="auth-tab-btn active"
            role="tab"
            aria-selected="true"
          >
            <span>🔑</span>
            <span>Sign In</span>
          </button>
          <Link
            to="/signup"
            className="auth-tab-btn"
            role="tab"
            aria-selected="false"
          >
            <span>👤</span>
            <span>Create Account</span>
          </Link>
        </div>

        <div className="auth-heading">
          <h1 className="auth-title">Welcome back</h1>
          <p className="auth-subtitle">Sign in to access your autonomous soil dashboard</p>
        </div>

        {error && (
          <div className="auth-alert auth-alert-error" role="alert">
            <span>⚠️</span>
            <span>{error}</span>
          </div>
        )}

        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          {/* Email */}
          <div className="auth-field">
            <label className="auth-label" htmlFor="login-email">Email Address</label>
            <div className="auth-input-wrap">
              <input
                id="login-email"
                type="email"
                className="auth-input"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                disabled={loading}
              />
              <span className="auth-input-icon">
                <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              </span>
            </div>
          </div>

          {/* Password */}
          <div className="auth-field">
            <label className="auth-label" htmlFor="login-password">Password</label>
            <div className="auth-input-wrap">
              <input
                id="login-password"
                type={showPwd ? 'text' : 'password'}
                className="auth-input"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                disabled={loading}
              />
              <span className="auth-input-icon">
                <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
              </span>
              <button
                type="button"
                className="auth-eye-btn"
                onClick={() => setShowPwd((p) => !p)}
                aria-label={showPwd ? 'Hide password' : 'Show password'}
              >
                {showPwd ? (
                  <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18" />
                  </svg>
                ) : (
                  <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  </svg>
                )}
              </button>
            </div>
          </div>

          {/* Forgot link */}
          <div className="auth-forgot">
            <Link to="/forgot-password" className="auth-link">Forgot password?</Link>
          </div>

          {/* Submit */}
          <button
            id="login-submit-btn"
            type="submit"
            className="auth-submit-btn"
            disabled={loading || !email || !password}
          >
            {loading ? (
              <>
                <div className="spinner" style={{ width: 18, height: 18 }} />
                Verifying Credentials…
              </>
            ) : (
              <>
                <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1" />
                </svg>
                Sign In
              </>
            )}
          </button>

          {/* Divider */}
          <div className="auth-divider">
            <span className="auth-divider-label">or continue with</span>
          </div>

          {/* Google */}
          <button
            id="login-google-btn"
            type="button"
            className="auth-google-btn"
            onClick={handleGoogle}
            disabled={loading}
          >
            <GoogleIcon />
            Real-Time Google Sign-In
          </button>
        </form>

        {/* Highly Visible Switcher Box */}
        <div
          style={{
            marginTop: 24,
            padding: '14px 16px',
            background: 'rgba(255, 255, 255, 0.03)',
            border: '1px solid rgba(201, 123, 42, 0.2)',
            borderRadius: 14,
            textAlign: 'center',
          }}
        >
          <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>
            Don&apos;t have an account yet?
          </span>
          <br />
          <Link
            to="/signup"
            style={{
              display: 'inline-block',
              marginTop: 6,
              color: 'var(--color-soil-gold)',
              fontWeight: 700,
              fontSize: 14,
              textDecoration: 'none',
            }}
          >
            ✨ Click here to Create New Account →
          </Link>
        </div>
      </div>
    </div>
  );
}
