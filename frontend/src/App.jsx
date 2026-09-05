import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import './index.css';

// Context
import { AuthProvider, useAuth } from './context/AuthContext';

// Components
import ProtectedRoute from './components/ProtectedRoute';
import Navbar from './components/Navbar';
import HeroSection from './components/HeroSection';
import AnalysisReport from './components/AnalysisReport';
import LoadingScreen from './components/LoadingScreen';
import ChatInterface from './components/ChatInterface';
import HistoryModal from './components/HistoryModal';

// Pages
import LoginPage from './pages/LoginPage';
import SignupPage from './pages/SignupPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';

// Services
import { api, ApiError } from './services/api';

function Dashboard() {
  const { user } = useAuth();
  const [view, setView] = useState('hero'); // 'hero' | 'loading' | 'report'
  const [analysisData, setAnalysisData] = useState(null);
  const [error, setError] = useState(null);
  const [location, setLocation] = useState('');
  const [targetCrop, setTargetCrop] = useState('');

  // Pro Feature: History Drawer & Local Persistence
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [history, setHistory] = useState([]);

  // Load user-specific history on mount or user change
  useEffect(() => {
    if (!user) return;
    const storageKey = `soilsense_history_${user.email || user.uid}`;
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        setHistory(JSON.parse(saved));
      } else {
        setHistory([]);
      }
    } catch {
      setHistory([]);
    }
  }, [user]);

  // Save item to history
  const saveToHistory = (item) => {
    if (!user) return;
    const storageKey = `soilsense_history_${user.email || user.uid}`;
    setHistory((prev) => {
      const updated = [item, ...prev].slice(0, 25); // keep latest 25
      localStorage.setItem(storageKey, JSON.stringify(updated));
      return updated;
    });
  };

  const handleClearHistory = () => {
    if (!user) return;
    const storageKey = `soilsense_history_${user.email || user.uid}`;
    localStorage.removeItem(storageKey);
    setHistory([]);
  };

  const handleAnalyze = async ({ description, location: loc, targetCrop: crop }) => {
    setError(null);
    setLocation(loc || '');
    setTargetCrop(crop || '');
    setView('loading');

    try {
      const result = await api.analyzeSoil(description, loc, crop);
      setAnalysisData(result);
      setView('report');

      // Automatically store in history
      saveToHistory({
        id: 'rec_' + Date.now(),
        timestamp: new Date().toISOString(),
        description,
        location: loc || '',
        targetCrop: crop || '',
        data: result,
      });
    } catch (err) {
      console.error('Analysis error:', err);
      let msg;
      if (err instanceof ApiError) {
        if (err.status === 503) {
          msg = `LLM service unavailable: ${err.message}. Check your API key in .env file.`;
        } else if (err.status === 422) {
          msg = 'Please provide a more detailed soil description (at least 10 characters).';
        } else {
          msg = err.message;
        }
      } else if (err.name === 'TypeError' && err.message.includes('fetch')) {
        msg = 'Cannot connect to backend. Make sure the server is running on port 8000.';
      } else {
        msg = 'Something went wrong. Please try again.';
      }
      setError(msg);
      setView('hero');
    }
  };

  const handleReset = () => {
    setView('hero');
    setAnalysisData(null);
    setError(null);
  };

  const handleLoadHistoryRecord = (data) => {
    setAnalysisData(data);
    setView('report');
  };

  return (
    <>
      <Navbar
        onReset={handleReset}
        onOpenHistory={() => setIsHistoryOpen(true)}
        historyCount={history.length}
      />

      <main>
        {view === 'hero' && (
          <HeroSection
            onAnalyze={handleAnalyze}
            loading={false}
            error={error}
          />
        )}

        {view === 'loading' && <LoadingScreen />}

        {view === 'report' && analysisData && (
          <AnalysisReport data={analysisData} onReset={handleReset} />
        )}
      </main>

      {/* Floating assistant chat — always available */}
      <ChatInterface location={location} targetCrop={targetCrop} />

      {/* Pro History Drawer */}
      <HistoryModal
        isOpen={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
        history={history}
        onSelect={handleLoadHistoryRecord}
        onClear={handleClearHistory}
      />
    </>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
