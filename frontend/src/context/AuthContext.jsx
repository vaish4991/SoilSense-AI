import { createContext, useContext, useEffect, useRef, useState } from 'react';
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
import { api } from '../services/api';
import GoogleSignInModal from '../components/GoogleSignInModal';

const AuthContext = createContext(null);

const ACTIVE_USER_KEY = 'soilsense_active_user';
const REGISTERED_USERS_KEY = 'soilsense_registered_users';

function getRegisteredUsers() {
  try {
    const raw = localStorage.getItem(REGISTERED_USERS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveRegisteredUsers(users) {
  localStorage.setItem(REGISTERED_USERS_KEY, JSON.stringify(users));
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [googleModalOpen, setGoogleModalOpen] = useState(false);
  const googlePromiseRef = useRef(null);

  useEffect(() => {
    if (isFirebaseConfigured && auth) {
      const unsubscribe = onAuthStateChanged(auth, (currentUser) => {
        setUser(currentUser);
        setLoading(false);
      });
      return unsubscribe;
    } else {
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

  const persistSessionUser = (sessionUser) => {
    setUser(sessionUser);
    localStorage.setItem(ACTIVE_USER_KEY, JSON.stringify(sessionUser));
    return { user: sessionUser };
  };

  /**
   * SIGN IN
   * - Firebase mode: real Firebase auth
   * - Local/Backend mode: authenticates against SQLite backend (with localStorage fallback)
   */
  const login = async (email, password) => {
    const normalizedEmail = (email || '').trim().toLowerCase();

    if (isFirebaseConfigured && auth) {
      return signInWithEmailAndPassword(auth, normalizedEmail, password);
    }

    try {
      const res = await api.authLogin(normalizedEmail, password);
      const sessionUser = { ...res.user, isDemo: true };
      return persistSessionUser(sessionUser);
    } catch (err) {
      if (err.status === 404) {
        const notFound = new Error(err.message);
        notFound.code = 'auth/user-not-found';
        throw notFound;
      }
      if (err.status === 401) {
        const badPwd = new Error(err.message);
        badPwd.code = 'auth/wrong-password';
        throw badPwd;
      }
      // Fallback to localStorage only if backend is unreachable
      if (err.name === 'TypeError') {
        const users = getRegisteredUsers();
        const existing = users.find((u) => u.email === normalizedEmail);
        if (!existing) {
          const nf = new Error('No account found with this email. Please sign up first.');
          nf.code = 'auth/user-not-found';
          throw nf;
        }
        if (existing.password !== password) {
          const bp = new Error('Incorrect password. Please verify your credentials.');
          bp.code = 'auth/wrong-password';
          throw bp;
        }
        const sessionUser = {
          uid: existing.uid,
          email: existing.email,
          displayName: existing.displayName || existing.email.split('@')[0],
          photoURL: existing.photoURL || `https://api.dicebear.com/7.x/bottts/svg?seed=${existing.email}`,
          authProvider: 'email',
          isDemo: true,
        };
        return persistSessionUser(sessionUser);
      }
      throw err;
    }
  };

  /**
   * SIGN UP
   * - Firebase mode: creates user in Firebase
   * - Local/Backend mode: registers in SQLite backend & records login event
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

    try {
      const res = await api.authRegister(normalizedEmail, password, displayName);
      const sessionUser = { ...res.user, isDemo: true };
      return persistSessionUser(sessionUser);
    } catch (err) {
      if (err.status === 409) {
        const existsErr = new Error(err.message);
        existsErr.code = 'auth/email-already-in-use';
        throw existsErr;
      }
      if (err.name === 'TypeError') {
        const users = getRegisteredUsers();
        if (users.find((u) => u.email === normalizedEmail)) {
          const existsErr = new Error('An account with this email address already exists.');
          existsErr.code = 'auth/email-already-in-use';
          throw existsErr;
        }
        const newUser = {
          uid: 'user_' + Date.now(),
          email: normalizedEmail,
          password,
          displayName: displayName || normalizedEmail.split('@')[0],
          photoURL: `https://api.dicebear.com/7.x/bottts/svg?seed=${normalizedEmail}`,
          authProvider: 'email',
          createdAt: new Date().toISOString(),
        };
        users.push(newUser);
        saveRegisteredUsers(users);
        return persistSessionUser({
          uid: newUser.uid,
          email: newUser.email,
          displayName: newUser.displayName,
          photoURL: newUser.photoURL,
          authProvider: 'email',
          isDemo: true,
        });
      }
      throw err;
    }
  };

  /**
   * GOOGLE SIGN-IN
   * - Firebase mode: uses real Firebase signInWithPopup & records login in backend SQLite
   * - Local mode (no Firebase keys): opens Google Account Picker / Sign-In Modal & persists in backend SQLite
   */
  const loginWithGoogle = async () => {
    if (isFirebaseConfigured && auth && googleProvider) {
      const cred = await signInWithPopup(auth, googleProvider);
      try {
        await api.authGoogle({
          email: cred.user.email,
          displayName: cred.user.displayName,
          photoURL: cred.user.photoURL,
          uid: cred.user.uid,
        });
      } catch {
        // Non-fatal if backend tracking fails while Firebase succeeded
      }
      return cred;
    }

    return new Promise((resolve, reject) => {
      googlePromiseRef.current = { resolve, reject };
      setGoogleModalOpen(true);
    });
  };

  const handleGoogleModalConfirm = async ({ email, displayName, photoURL, uid }) => {
    let sessionUser;
    try {
      const res = await api.authGoogle({ email, displayName, photoURL, uid });
      sessionUser = { ...res.user, isDemo: true };
    } catch (err) {
      if (err.name === 'TypeError') {
        const normalizedEmail = email.trim().toLowerCase();
        sessionUser = {
          uid: uid || 'google_' + Date.now(),
          email: normalizedEmail,
          displayName: displayName || normalizedEmail.split('@')[0],
          photoURL: photoURL || `https://api.dicebear.com/7.x/bottts/svg?seed=${normalizedEmail}`,
          authProvider: 'google',
          isDemo: true,
        };
      } else {
        throw err;
      }
    }

    const result = persistSessionUser(sessionUser);
    setGoogleModalOpen(false);
    googlePromiseRef.current?.resolve(result);
    googlePromiseRef.current = null;
  };

  const handleGoogleModalCancel = () => {
    setGoogleModalOpen(false);
    const err = new Error('Google Sign-In was cancelled.');
    err.code = 'auth/popup-closed-by-user';
    googlePromiseRef.current?.reject(err);
    googlePromiseRef.current = null;
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
        isDemoMode: !isFirebaseConfigured,
      }}
    >
      {children}
      <GoogleSignInModal
        isOpen={googleModalOpen}
        onConfirm={handleGoogleModalConfirm}
        onCancel={handleGoogleModalCancel}
      />
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
