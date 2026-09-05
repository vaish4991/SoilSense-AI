import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import '../components/AuthPages.css';

export default function ForgotPasswordPage() {
  const [email, setEmail]     = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');
  const [message, setMessage] = useState('');

  const { resetPassword } = useAuth();

  const friendlyError = (code) => {
    const map = {
      'auth/user-not-found':        'No account found with this email address.',
      'auth/invalid-email':         'Please enter a valid email address.',
      'auth/too-many-requests':     'Too many requests. Please wait a moment.',
      'auth/network-request-failed':'Network error. Check your connection.',
    };
    return map[code] || 'Failed to send reset email. Please try again.';
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setMessage('');
    setLoading(true);

    try {
      await resetPassword(email);
      setMessage('Password reset link sent! Please check your inbox (and spam folder).');
    } catch (err) {
      setError(friendlyError(err.code));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card" style={{ maxWidth: 440 }}>
        {/* Brand */}
        <div className="auth-logo">
          <div className="auth-logo-icon">🌱</div>
          <div className="auth-logo-text">
            <span className="auth-logo-name">SoilSense AI</span>
            <span className="auth-logo-sub">Buildathon 2026</span>
          </div>
        </div>

        <div className="auth-heading">
          <h1 className="auth-title">Reset password</h1>
          <p className="auth-subtitle">
            Enter your email and we&apos;ll send you instructions to reset your password.
          </p>
        </div>

        {error && (
          <div className="auth-alert auth-alert-error" role="alert">
            <span>⚠️</span>
            <span>{error}</span>
          </div>
        )}

        {message && (
          <div className="auth-alert auth-alert-success" role="alert">
            <span>✉️</span>
            <span>{message}</span>
          </div>
        )}

        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          <div className="auth-field">
            <label className="auth-label" htmlFor="reset-email">Email Address</label>
            <div className="auth-input-wrap">
              <input
                id="reset-email"
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

          <button
            id="reset-submit-btn"
            type="submit"
            className="auth-submit-btn"
            disabled={loading || !email}
            style={{ marginTop: 8 }}
          >
            {loading ? (
              <>
                <div className="spinner" style={{ width: 18, height: 18 }} />
                Sending link…
              </>
            ) : (
              <>
                <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
                Send Reset Link
              </>
            )}
          </button>
        </form>

        <div className="auth-switch" style={{ marginTop: 24 }}>
          Remember your password?&nbsp;
          <Link to="/login" className="auth-link">Back to sign in</Link>
        </div>
      </div>
    </div>
  );
}
