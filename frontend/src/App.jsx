import { useState } from 'react';
import './index.css';
import HeroSection from './components/HeroSection';
import AnalysisReport from './components/AnalysisReport';
import LoadingScreen from './components/LoadingScreen';
import ChatInterface from './components/ChatInterface';
import { api, ApiError } from './services/api';

export default function App() {
  const [view, setView] = useState('hero'); // 'hero' | 'loading' | 'report'
  const [analysisData, setAnalysisData] = useState(null);
  const [error, setError] = useState(null);
  const [location, setLocation] = useState('');
  const [targetCrop, setTargetCrop] = useState('');

  const handleAnalyze = async ({ description, location: loc, targetCrop: crop }) => {
    setError(null);
    setLocation(loc || '');
    setTargetCrop(crop || '');
    setView('loading');

    try {
      const result = await api.analyzeSoil(description, loc, crop);
      setAnalysisData(result);
      setView('report');
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

  return (
    <>
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

      {/* Floating chat — always visible */}
      <ChatInterface location={location} targetCrop={targetCrop} />
    </>
  );
}
