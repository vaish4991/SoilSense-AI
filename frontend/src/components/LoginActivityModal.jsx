import { useEffect, useState } from 'react';
import { api } from '../services/api';

function formatTime(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function LoginActivityModal({ isOpen, onClose }) {
  const [tab, setTab] = useState('users'); // 'users' | 'logins'
  const [users, setUsers] = useState([]);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!isOpen) return;
    let active = true;
    setLoading(true);
    setError('');

    Promise.all([api.getAuthUsers(), api.getAuthLogins(50)])
      .then(([uRes, lRes]) => {
        if (!active) return;
        setUsers(uRes?.users || []);
        setEvents(lRes?.events || []);
      })
      .catch((err) => {
        if (!active) return;
        setError(err?.message || 'Could not load login records from backend.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const googleCount = users.filter((u) => u.authProvider === 'google').length;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="login-activity-title"
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
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: 720,
          maxHeight: '85vh',
          display: 'flex',
          flexDirection: 'column',
          background: '#131920',
          border: '1px solid rgba(255, 255, 255, 0.12)',
          borderRadius: 20,
          padding: 24,
          boxShadow: '0 24px 60px rgba(0, 0, 0, 0.55)',
          color: '#f3f4f6',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <div>
            <h2 id="login-activity-title" style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>
              👥 Users &amp; Login Activity
            </h2>
            <p style={{ margin: '4px 0 0', fontSize: 12, color: '#9ca3af' }}>
              Persisted in SQLite backend database (users &amp; login audit log)
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close Users & Login Activity"
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

        {/* Summary pills */}
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 16 }}>
          <div style={{ padding: '8px 14px', borderRadius: 10, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', fontSize: 12 }}>
            Total Users: <strong>{users.length}</strong>
          </div>
          <div style={{ padding: '8px 14px', borderRadius: 10, background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.25)', fontSize: 12, color: '#93c5fd' }}>
            Google Sign-In Users: <strong>{googleCount}</strong>
          </div>
          <div style={{ padding: '8px 14px', borderRadius: 10, background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.25)', fontSize: 12, color: '#86efac' }}>
            Recent Logins: <strong>{events.length}</strong>
          </div>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
          <button
            type="button"
            onClick={() => setTab('users')}
            style={{
              padding: '8px 14px',
              borderRadius: 10,
              border: 'none',
              cursor: 'pointer',
              fontSize: 13,
              fontWeight: 600,
              background: tab === 'users' ? '#c97b2a' : 'rgba(255,255,255,0.06)',
              color: tab === 'users' ? '#fff' : '#d1d5db',
            }}
          >
            Registered Users ({users.length})
          </button>
          <button
            type="button"
            onClick={() => setTab('logins')}
            style={{
              padding: '8px 14px',
              borderRadius: 10,
              border: 'none',
              cursor: 'pointer',
              fontSize: 13,
              fontWeight: 600,
              background: tab === 'logins' ? '#c97b2a' : 'rgba(255,255,255,0.06)',
              color: tab === 'logins' ? '#fff' : '#d1d5db',
            }}
          >
            Login History ({events.length})
          </button>
        </div>

        {/* Content */}
        <div style={{ overflowY: 'auto', flex: 1, paddingRight: 4 }}>
          {loading && <div style={{ padding: 24, textAlign: 'center', color: '#9ca3af' }}>Loading records…</div>}
          {error && (
            <div style={{ padding: 12, borderRadius: 10, background: 'rgba(239,68,68,0.14)', color: '#fca5a5', fontSize: 13 }}>
              {error}
            </div>
          )}

          {!loading && !error && tab === 'users' && (
            users.length === 0 ? (
              <div style={{ padding: 24, textAlign: 'center', color: '#9ca3af' }}>No users recorded yet.</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {users.map((u) => (
                  <div
                    key={u.uid}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 12,
                      padding: '10px 12px',
                      borderRadius: 12,
                      background: 'rgba(255,255,255,0.03)',
                      border: '1px solid rgba(255,255,255,0.08)',
                    }}
                  >
                    <img
                      src={u.photoURL}
                      alt={u.displayName}
                      style={{ width: 36, height: 36, borderRadius: '50%', background: '#1f2937' }}
                    />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: 600, fontSize: 14 }}>
                        {u.displayName}{' '}
                        <span
                          style={{
                            fontSize: 10,
                            padding: '2px 7px',
                            borderRadius: 999,
                            marginLeft: 6,
                            background: u.authProvider === 'google' ? 'rgba(59,130,246,0.2)' : 'rgba(201,123,42,0.2)',
                            color: u.authProvider === 'google' ? '#93c5fd' : '#fcd34d',
                          }}
                        >
                          {u.authProvider === 'google' ? 'Google' : 'Email'}
                        </span>
                      </div>
                      <div style={{ fontSize: 12, color: '#9ca3af' }}>{u.email}</div>
                    </div>
                    <div style={{ textAlign: 'right', fontSize: 11, color: '#9ca3af' }}>
                      <div>Logins: <strong style={{ color: '#f3f4f6' }}>{u.loginCount}</strong></div>
                      <div>Last: {formatTime(u.lastLoginAt)}</div>
                    </div>
                  </div>
                ))}
              </div>
            )
          )}

          {!loading && !error && tab === 'logins' && (
            events.length === 0 ? (
              <div style={{ padding: 24, textAlign: 'center', color: '#9ca3af' }}>No login events recorded yet.</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {events.map((ev) => (
                  <div
                    key={ev.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: 12,
                      padding: '10px 12px',
                      borderRadius: 12,
                      background: 'rgba(255,255,255,0.03)',
                      border: '1px solid rgba(255,255,255,0.08)',
                      fontSize: 13,
                    }}
                  >
                    <div>
                      <strong>{ev.displayName}</strong>{' '}
                      <span style={{ color: '#9ca3af' }}>({ev.email})</span>
                      <span
                        style={{
                          fontSize: 10,
                          padding: '2px 7px',
                          borderRadius: 999,
                          marginLeft: 8,
                          background: ev.authProvider === 'google' ? 'rgba(59,130,246,0.2)' : 'rgba(201,123,42,0.2)',
                          color: ev.authProvider === 'google' ? '#93c5fd' : '#fcd34d',
                        }}
                      >
                        {ev.authProvider === 'google' ? 'Google' : 'Email'}
                      </span>
                    </div>
                    <div style={{ fontSize: 11, color: '#9ca3af', whiteSpace: 'nowrap' }}>
                      {formatTime(ev.loginAt)}
                    </div>
                  </div>
                ))}
              </div>
            )
          )}
        </div>
      </div>
    </div>
  );
}
