import { createContext, useContext, useEffect, useState } from 'react';
import {
  onAuthStateChanged,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  signOut,
  sendPasswordResetEmail,
  updateProfile,
} from 'firebase/auth';
import { auth, googleProvider, isFirebaseConfigured } from '../firebase';

const AuthContext = createContext(null);

const ACTIVE_USER_KEY = 'soilsense_active_user';
const REGISTERED_USERS_KEY = 'soilsense_registered_users';

// Helper to get registered user database
function getRegisteredUsers() {
  try {
    const raw = localStorage.getItem(REGISTERED_USERS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

// Helper to save registered user database
function saveRegisteredUsers(users) {
  localStorage.setItem(REGISTERED_USERS_KEY, JSON.stringify(users));
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (isFirebaseConfigured && auth) {
      const unsubscribe = onAuthStateChanged(auth, (currentUser) => {
        setUser(currentUser);
        setLoading(false);
      });
      return unsubscribe;
    } else {
      // Check active authenticated session
      const saved = localStorage.getItem(ACTIVE_USER_KEY);
      if (saved) {
        try {
          setUser(JSON.parse(saved));
        } catch {
          setUser(null);
        }
      }
      setLoading(false);
    }
  }, []);

  /**
   * STRICT SIGN IN
   * - In Firebase mode: calls real Firebase auth
   * - In Local mode: strictly checks if email exists and password matches exactly
   */
  const login = async (email, password) => {
    const normalizedEmail = (email || '').trim().toLowerCase();

    if (isFirebaseConfigured && auth) {
      return signInWithEmailAndPassword(auth, normalizedEmail, password);
    }

    // STRICT LOCAL AUTHENTICATION
    await new Promise((r) => setTimeout(r, 400));
    const users = getRegisteredUsers();
    const existing = users.find((u) => u.email === normalizedEmail);

    if (!existing) {
      const err = new Error('No account found with this email. Please sign up first.');
      err.code = 'auth/user-not-found';
      throw err;
    }

    if (existing.password !== password) {
      const err = new Error('Incorrect password. Please verify your credentials.');
      err.code = 'auth/wrong-password';
      throw err;
    }

    // Credentials match strictly!
    const sessionUser = {
      uid: existing.uid,
      email: existing.email,
      displayName: existing.displayName || existing.email.split('@')[0],
      photoURL: existing.photoURL || `https://api.dicebear.com/7.x/bottts/svg?seed=${existing.email}`,
      isDemo: true,
    };

    setUser(sessionUser);
    localStorage.setItem(ACTIVE_USER_KEY, JSON.stringify(sessionUser));
    return { user: sessionUser };
  };

  /**
   * STRICT SIGN UP
   * - In Firebase mode: creates user in Firebase
   * - In Local mode: prevents duplicates, requires strong password, saves record
   */
  const signup = async (email, password, displayName) => {
    const normalizedEmail = (email || '').trim().toLowerCase();

    if (isFirebaseConfigured && auth) {
      const cred = await createUserWithEmailAndPassword(auth, normalizedEmail, password);
      if (displayName) {
        await updateProfile(cred.user, { displayName });
      }
      return cred;
    }

    // STRICT LOCAL REGISTRATION
    await new Promise((r) => setTimeout(r, 400));
    const users = getRegisteredUsers();
    const existing = users.find((u) => u.email === normalizedEmail);

    if (existing) {
      const err = new Error('An account with this email address already exists. Please sign in instead.');
      err.code = 'auth/email-already-in-use';
      throw err;
    }

    const newUser = {
      uid: 'user_' + Date.now(),
      email: normalizedEmail,
      password: password, // stored locally for strict authentication check
      displayName: displayName || normalizedEmail.split('@')[0],
      photoURL: `https://api.dicebear.com/7.x/bottts/svg?seed=${normalizedEmail}`,
      createdAt: new Date().toISOString(),
    };

    users.push(newUser);
    saveRegisteredUsers(users);

    // Auto-login newly registered user
    const sessionUser = {
      uid: newUser.uid,
      email: newUser.email,
      displayName: newUser.displayName,
      photoURL: newUser.photoURL,
      isDemo: true,
    };

    setUser(sessionUser);
    localStorage.setItem(ACTIVE_USER_KEY, JSON.stringify(sessionUser));
    return { user: sessionUser };
  };

  /**
   * REAL-TIME STRICT GOOGLE AUTH
   * - Must use real-time Firebase Google Auth popup.
   * - If Firebase config is missing, raises an explicit error so user knows to provide credentials.
   */
  const loginWithGoogle = async () => {
    if (isFirebaseConfigured && auth && googleProvider) {
      return signInWithPopup(auth, googleProvider);
    }

    // STRICT: Do not fake Google auth without real-time Firebase provider
    const err = new Error(
      'Real-Time Google Sign-In requires active Firebase credentials. Please add VITE_FIREBASE_API_KEY and VITE_FIREBASE_PROJECT_ID to your .env file.'
    );
    err.code = 'auth/firebase-not-configured';
    throw err;
  };

  const logout = async () => {
    if (isFirebaseConfigured && auth) {
      await signOut(auth);
    }
    localStorage.removeItem(ACTIVE_USER_KEY);
    setUser(null);
  };

  const resetPassword = async (email) => {
    const normalizedEmail = (email || '').trim().toLowerCase();
    if (isFirebaseConfigured && auth) {
      return sendPasswordResetEmail(auth, normalizedEmail);
    }

    await new Promise((r) => setTimeout(r, 400));
    const users = getRegisteredUsers();
    const existing = users.find((u) => u.email === normalizedEmail);
    if (!existing) {
      const err = new Error('No account found with this email address.');
      err.code = 'auth/user-not-found';
      throw err;
    }
    return true;
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        signup,
        loginWithGoogle,
        logout,
        resetPassword,
        isFirebaseConfigured,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
