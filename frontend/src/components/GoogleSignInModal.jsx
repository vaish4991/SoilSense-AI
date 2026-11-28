import { useEffect, useState } from 'react';
import { api } from '../services/api';

function GoogleLogo() {
  return (
    <svg width="24" height="24" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#FFC107" d="M43.6 20.2H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.1 7.9 3l5.7-5.7C34.1 6.5 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.6-.4-3.8z"/>
      <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.6 16 19 13 24 13c3.1 0 5.8 1.1 7.9 3l5.7-5.7C34.1 6.5 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/>
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.3 35.5 26.8 36 24 36c-5.2 0-9.6-3.3-11.3-8H6.1C9.5 37.4 16.2 44 24 44z"/>
      <path fill="#1976D2" d="M43.6 20.2H42V20H24v8h11.3c-.9 2.4-2.5 4.5-4.6 5.9l6.2 5.2C36.7 40.1 44 34 44 24c0-1.3-.1-2.6-.4-3.8z"/>
    </svg>
  );
}

export default function GoogleSignInModal({ isOpen, onConfirm, onCancel }) {
  const [savedAccounts, setSavedAccounts] = useState([]);
  const [useOther, setUseOther] = useState(false);
  const [email, setEmail] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setError('');
    setSubmitting(false);
    let active = true;
    api.getAuthUsers()
      .then((res) => {
        if (!active) return;
        const googleUsers = (res?.users || []).filter((u) => u.authProvider === 'google');
        setSavedAccounts(googleUsers);
        setUseOther(googleUsers.length === 0);
      })
      .catch(() => {
        if (!active) return;
        setSavedAccounts([]);
        setUseOther(true);
      });
    return () => {
      active = false;
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSelectAccount = async (account) => {
    setSubmitting(true);
    setError('');
    try {
      await onConfirm({
        email: account.email,
        displayName: account.displayName,
        photoURL: account.photoURL,
        uid: account.uid,
      });
    } catch (err) {
      setError(err?.message || 'Google sign-in failed.');
      setSubmitting(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const trimmedEmail = email.trim().toLowerCase();
    if (!trimmedEmail || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmedEmail)) {
      setError('Please enter a valid Google email address.');
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      const resolvedName = displayName.trim() || trimmedEmail.split('@')[0];
      await onConfirm({
        email: trimmedEmail,
        displayName: resolvedName,
      });
    } catch (err) {
      setError(err?.message || 'Google sign-in failed.');
      setSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="google-signin-title"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        background: 'rgba(6, 10, 14, 0.78)',
        backdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && !submitting) onCancel();
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: 420,
          background: '#131920',
          border: '1px solid rgba(255, 255, 255, 0.12)',
          borderRadius: 20,
          padding: 28,
          boxShadow: '0 24px 60px rgba(0, 0, 0, 0.55)',
          color: '#f3f4f6',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <GoogleLogo />
            <div>
              <h2 id="google-signin-title" style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>
                Sign in with Google
              </h2>
              <p style={{ margin: 0, fontSize: 12, color: '#9ca3af' }}>
                to continue to SoilSense AI
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onCancel}
            disabled={submitting}
            aria-label="Close Google Sign-In"
            style={{
              background: 'transparent',
              border: 'none',
              color: '#9ca3af',
              fontSize: 20,
              cursor: 'pointer',
              padding: 4,
            }}
          >
            ✕
          </button>
        </div>

        {error && (
          <div
            role="alert"
            style={{
              background: 'rgba(239, 68, 68, 0.14)',
              border: '1px solid rgba(239, 68, 68, 0.35)',
              color: '#fca5a5',
              padding: '10px 12px',
              borderRadius: 10,
              fontSize: 13,
              marginBottom: 14,
            }}
          >
            {error}
          </div>
        )}

        {savedAccounts.length > 0 && !useOther && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 2 }}>
              Choose an account
            </div>
            {savedAccounts.map((acc) => (
              <button
                key={acc.uid}
                type="button"
                disabled={submitting}
                onClick={() => handleSelectAccount(acc)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  width: '100%',
                  padding: '10px 12px',
                  borderRadius: 12,
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  background: 'rgba(255, 255, 255, 0.04)',
                  color: '#f3f4f6',
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                <img
                  src={acc.photoURL}
                  alt={acc.displayName}
                  style={{ width: 36, height: 36, borderRadius: '50%', background: '#1f2937' }}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: 14, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {acc.displayName}
                  </div>
                  <div style={{ fontSize: 12, color: '#9ca3af', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {acc.email}
                  </div>
                </div>
                <span style={{ fontSize: 11, color: '#60a5fa', fontWeight: 600 }}>Continue →</span>
              </button>
            ))}

            <button
              type="button"
              disabled={submitting}
              onClick={() => setUseOther(true)}
              style={{
                marginTop: 6,
                padding: '10px 12px',
                borderRadius: 12,
                border: '1px dashed rgba(255, 255, 255, 0.2)',
                background: 'transparent',
                color: '#d1d5db',
                cursor: 'pointer',
                fontSize: 13,
                fontWeight: 600,
              }}
            >
              + Use another Google account
            </button>
          </div>
        )}

        {(useOther || savedAccounts.length === 0) && (
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div>
              <label htmlFor="google-modal-name" style={{ display: 'block', fontSize: 12, color: '#d1d5db', marginBottom: 6 }}>
                Full Name
              </label>
              <input
                id="google-modal-name"
                type="text"
                placeholder="e.g. Vaishnavi Jagdale"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                disabled={submitting}
                style={{
                  width: '100%',
                  boxSizing: 'border-box',
                  padding: '10px 12px',
                  borderRadius: 10,
                  border: '1px solid rgba(255, 255, 255, 0.14)',
                  background: 'rgba(255, 255, 255, 0.05)',
                  color: '#fff',
                  fontSize: 14,
                }}
              />
            </div>

            <div>
              <label htmlFor="google-modal-email" style={{ display: 'block', fontSize: 12, color: '#d1d5db', marginBottom: 6 }}>
                Google Email
              </label>
              <input
                id="google-modal-email"
                type="email"
                placeholder="you@gmail.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
                disabled={submitting}
                style={{
                  width: '100%',
                  boxSizing: 'border-box',
                  padding: '10px 12px',
                  borderRadius: 10,
                  border: '1px solid rgba(255, 255, 255, 0.14)',
                  background: 'rgba(255, 255, 255, 0.05)',
                  color: '#fff',
                  fontSize: 14,
                }}
              />
            </div>

            <div style={{ display: 'flex', gap: 10, marginTop: 6 }}>
              {savedAccounts.length > 0 && (
                <button
                  type="button"
                  disabled={submitting}
                  onClick={() => setUseOther(false)}
                  style={{
                    flex: 1,
                    padding: '10px 14px',
                    borderRadius: 10,
                    border: '1px solid rgba(255, 255, 255, 0.14)',
                    background: 'transparent',
                    color: '#d1d5db',
                    cursor: 'pointer',
                    fontWeight: 600,
                    fontSize: 13,
                  }}
                >
                  Back
                </button>
              )}
              <button
                id="google-modal-submit"
                type="submit"
                disabled={submitting || !email.trim()}
                style={{
                  flex: 2,
                  padding: '10px 14px',
                  borderRadius: 10,
                  border: 'none',
                  background: '#2563eb',
                  color: '#fff',
                  cursor: 'pointer',
                  fontWeight: 700,
                  fontSize: 14,
                }}
              >
                {submitting ? 'Signing in…' : 'Continue with Google'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
