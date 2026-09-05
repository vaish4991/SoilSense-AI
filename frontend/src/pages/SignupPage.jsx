import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import '../components/AuthPages.css';

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

// ── Password strength indicator ─────────────────────────────
function PasswordStrength({ password }) {
  const checks = [
    password.length >= 8,
    /[A-Z]/.test(password),
    /[0-9]/.test(password),
    /[^A-Za-z0-9]/.test(password),
  ];
  const strength = checks.filter(Boolean).length;
  const labels = ['', 'Weak (too simple)', 'Fair (good start)', 'Good (secure)', 'Strong (excellent)'];
  const colors = ['', '#ef4444', '#f59e0b', '#22c55e', '#4fa3e0'];

  if (!password) return null;

  return (
    <div style={{ marginTop: 6 }}>
      <div style={{ display: 'flex', gap: 4, marginBottom: 4 }}>
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            style={{
              flex: 1,
              height: 3,
              borderRadius: 2,
              background: i <= strength ? colors[strength] : 'rgba(255,255,255,0.08)',
              transition: 'background 0.3s ease',
            }}
          />
        ))}
      </div>
      <span style={{ fontSize: 11, color: colors[strength], fontWeight: 600 }}>
        Security: {labels[strength]}
      </span>
    </div>
  );
}

// ── Main Signup Component ────────────────────────────────────
export default function SignupPage() {
  const [name, setName]         = useState('');
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm]   = useState('');
  const [showPwd, setShowPwd]   = useState(false);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');

  const { signup, loginWithGoogle } = useAuth();
  const navigate = useNavigate();

  const friendlyError = (err) => {
    const code = err?.code;
    const msg = err?.message;

    if (code === 'auth/firebase-not-configured') {
      return 'Real-Time Google Sign-In requires active Firebase credentials. Please add VITE_FIREBASE_API_KEY and VITE_FIREBASE_PROJECT_ID to your .env file.';
    }
    if (code === 'auth/email-already-in-use') {
      return 'An account with this email address already exists. Please switch to the Sign In tab.';
    }
    if (code === 'auth/invalid-email') {
      return 'Please enter a valid email address.';
    }
    if (code === 'auth/weak-password') {
      return 'Password is too weak. Please use at least 6 characters with numbers and letters.';
    }
    return msg || 'Sign up failed. Please check your information.';
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (!email.trim()) {
      setError('Please enter your email address.');
      return;
    }
    if (password !== confirm) {
      setError('Passwords do not match. Please verify your confirm password.');
      return;
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters long.');
      return;
    }
    setLoading(true);
    try {
      await signup(email, password, name);
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
      {/* Desktop features panel */}
      <div className="auth-features">
        <div>
          <div className="auth-feature-title">
            Start your<br /><span>Soil Journey</span>
          </div>
          <p className="auth-feature-desc">
            Create an agronomist account and unlock AI-powered soil analysis backed by real USDA laboratory data.
          </p>
        </div>
        <div className="auth-feature-list">
          {[
            { icon: '🆓', title: 'Always Free Access',     desc: 'Full analysis suite at zero cost' },
            { icon: '📊', title: 'USDA SSURGO Benchmark', desc: 'Real physical laboratory ground truth' },
            { icon: '🔒', title: 'Strict & Secure',       desc: 'Encrypted credentials and private data' },
            { icon: '📱', title: 'Responsive Telemetry',  desc: 'Seamless across desktop, tablet, and mobile' },
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

      {/* Auth card */}
      <div className="auth-card">
        <div className="auth-logo">
          <div className="auth-logo-icon">🌱</div>
          <div className="auth-logo-text">
            <span className="auth-logo-name">SoilSense AI</span>
            <span className="auth-logo-sub">Razorpay AI Buildathon 2026</span>
          </div>
        </div>

        {/* ── HIGH VISIBILITY MODE TABS ── */}
        <div className="auth-mode-tabs" role="tablist">
          <Link
            to="/login"
            className="auth-tab-btn"
            role="tab"
            aria-selected="false"
          >
            <span>🔑</span>
            <span>Sign In</span>
          </Link>
          <button
            type="button"
            className="auth-tab-btn active"
            role="tab"
            aria-selected="true"
          >
            <span>👤</span>
            <span>Create Account</span>
          </button>
        </div>

        <div className="auth-heading">
          <h1 className="auth-title">Create account</h1>
          <p className="auth-subtitle">Register to unlock strict autonomous soil intelligence</p>
        </div>

        {error && (
          <div className="auth-alert auth-alert-error" role="alert">
            <span>⚠️</span>
            <span>{error}</span>
          </div>
        )}

        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          {/* Full name */}
          <div className="auth-field">
            <label className="auth-label" htmlFor="signup-name">Full Name</label>
            <div className="auth-input-wrap">
              <input
                id="signup-name"
                type="text"
                className="auth-input"
                placeholder="Dr. Jane Smith"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoComplete="name"
                disabled={loading}
              />
              <span className="auth-input-icon">
                <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
              </span>
            </div>
          </div>

          {/* Email */}
          <div className="auth-field">
            <label className="auth-label" htmlFor="signup-email">Email Address</label>
            <div className="auth-input-wrap">
              <input
                id="signup-email"
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
            <label className="auth-label" htmlFor="signup-password">Password</label>
            <div className="auth-input-wrap">
              <input
                id="signup-password"
                type={showPwd ? 'text' : 'password'}
                className="auth-input"
                placeholder="Create a strong password (min 6 characters)"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="new-password"
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
            <PasswordStrength password={password} />
          </div>

          {/* Confirm */}
          <div className="auth-field">
            <label className="auth-label" htmlFor="signup-confirm">Confirm Password</label>
            <div className="auth-input-wrap">
              <input
                id="signup-confirm"
                type={showPwd ? 'text' : 'password'}
                className="auth-input"
                placeholder="Repeat your password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                required
                autoComplete="new-password"
                disabled={loading}
                style={{
                  borderColor: confirm && confirm !== password
                    ? 'rgba(239,68,68,0.5)' : undefined,
                }}
              />
              <span className="auth-input-icon">
                <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
              </span>
            </div>
          </div>

          {/* Submit */}
          <button
            id="signup-submit-btn"
            type="submit"
            className="auth-submit-btn"
            disabled={loading || !email || !password || !confirm}
            style={{ marginTop: 8 }}
          >
            {loading ? (
              <>
                <div className="spinner" style={{ width: 18, height: 18 }} />
                Registering Account…
              </>
            ) : (
              <>
                <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
                </svg>
                Complete Registration
              </>
            )}
          </button>

          {/* Divider */}
          <div className="auth-divider">
            <span className="auth-divider-label">or sign up with</span>
          </div>

          {/* Google */}
          <button
            id="signup-google-btn"
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
            Already have an account?
          </span>
          <br />
          <Link
            to="/login"
            style={{
              display: 'inline-block',
              marginTop: 6,
              color: 'var(--color-soil-gold)',
              fontWeight: 700,
              fontSize: 14,
              textDecoration: 'none',
            }}
          >
            🔑 Click here to Sign In →
          </Link>
        </div>
      </div>
    </div>
  );
}
