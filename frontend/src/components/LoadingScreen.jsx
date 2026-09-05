import { useState, useEffect } from 'react';
import './LoadingScreen.css';

const PIPELINE_STEPS = [
  { label: 'Parsing soil description…', icon: '📝' },
  { label: 'Extracting structured features…', icon: '🔍' },
  { label: 'Running ML pH model…', icon: '🤖' },
  { label: 'Calculating uncertainty…', icon: '📊' },
  { label: 'Fetching weather data…', icon: '🌤' },
  { label: 'Generating crop recommendations…', icon: '🌾' },
  { label: 'Writing AI explanation…', icon: '✦' },
];

export default function LoadingScreen() {
  const [currentStep, setCurrentStep] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentStep((s) => Math.min(s + 1, PIPELINE_STEPS.length - 1));
    }, 800);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="loading-screen">
      <div className="loading-icon">🌱</div>
      <h2 className="loading-title">Analysing Your Soil</h2>
      <p className="loading-subtitle">
        Running the AI agent pipeline…
      </p>

      <div className="pipeline-steps">
        {PIPELINE_STEPS.map((step, i) => {
          const status = i < currentStep ? 'done' : i === currentStep ? 'active' : 'waiting';
          return (
            <div key={i} className={`pipeline-step ${status}`}>
              <div className={`step-indicator ${status}`}>
                {status === 'done' ? '✓' : i + 1}
              </div>
              <span>{step.icon} {step.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
