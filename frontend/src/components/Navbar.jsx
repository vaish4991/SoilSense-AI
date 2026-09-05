import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './Navbar.css';

export default function Navbar({ onReset, onOpenHistory, historyCount = 0 }) {
  const { user, logout, isDemoMode } = useAuth();

  return (
    <header className="navbar">
      <div className="navbar-inner">
        {/* Brand */}
        <div
          className="navbar-brand"
          style={{ cursor: 'pointer' }}
          onClick={onReset}
          role="button"
          tabIndex={0}
        >
          <div className="navbar-logo-icon">🌱</div>
          <div className="navbar-title">
            Soil<span>Sense</span> AI <span className="navbar-tag">PRO</span>
          </div>
        </div>

        {/* Right actions */}
        <div className="navbar-actions">
          {user ? (
            <>
              <button
                type="button"
                className="history-btn"
                style={{ padding: '6px 12px', fontSize: 12 }}
                onClick={onOpenHistory}
                title="View past soil analyses"
              >
                <span>📚 History</span>
                {historyCount > 0 && (
                  <span className="badge badge-amber" style={{ fontSize: 9, padding: '1px 5px' }}>
                    {historyCount}
                  </span>
                )}
              </button>

              <div className={`navbar-auth-badge ${isDemoMode ? 'demo' : ''}`}>
                <span style={{ fontSize: 9 }}>●</span>
                {isDemoMode ? 'Demo Auth' : 'Firebase Verified'}
              </div>

              <div className="navbar-user-pill">
                <img
                  src={
                    user.photoURL ||
                    `https://api.dicebear.com/7.x/bottts/svg?seed=${user.email || 'soil'}`
                  }
                  alt="Avatar"
                  className="navbar-avatar"
                />
                <div className="navbar-user-info">
                  <span className="navbar-user-name">
                    {user.displayName || user.email?.split('@')[0] || 'Agronomist'}
                  </span>
                  <span className="navbar-user-email">{user.email}</span>
                </div>
              </div>

              <button
                type="button"
                className="navbar-btn-signout"
                onClick={logout}
                title="Sign out of your account"
              >
                <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
                Sign Out
              </button>
            </>
          ) : (
            <Link to="/login" className="navbar-btn-login">
              Sign In
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
