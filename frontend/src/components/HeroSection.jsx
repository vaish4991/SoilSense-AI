import { useState } from 'react';
import './HeroSection.css';

const EXAMPLE_PROMPTS = [
  "Dark brown clay soil, sticky when wet, drains slowly, earthworms present",
  "Red sandy soil, gritty texture, water drains very quickly, dry conditions",
  "Black loamy soil with moderate drainage and high moisture content",
];

export default function HeroSection({ onAnalyze, loading, error }) {
  const [description, setDescription] = useState('');
  const [location, setLocation] = useState('');
  const [targetCrop, setTargetCrop] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!description.trim() || description.trim().length < 10) return;
    onAnalyze({ description: description.trim(), location: location.trim(), targetCrop: targetCrop.trim() });
  };

  const useExample = (prompt) => setDescription(prompt);

  return (
    <section className="hero">
      {/* Logo */}
      <div className="hero-logo">
        <div className="hero-logo-icon">🌱</div>
        <div className="hero-logo-text">Soil<span>Sense</span> AI</div>
      </div>

      {/* Headline */}
      <h1 className="hero-title">
        Meet <span className="highlight">SoilSense AI</span>
      </h1>
      <p className="hero-subtitle">
        Describe your soil in plain language. Get AI-powered insights, pH estimation, weather-aware crop recommendations — and honest uncertainty.
      </p>

      {/* Form card */}
      <div className="card hero-form-card">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
          <span className="ai-chip">✦ AI Agent</span>
          <span className="ai-chip" style={{ background: 'rgba(74,124,89,0.15)', borderColor: 'rgba(74,124,89,0.3)', color: '#6aaa7a' }}>
            🔬 ML pH Model
          </span>
          <span className="ai-chip" style={{ background: 'rgba(79,163,224,0.1)', borderColor: 'rgba(79,163,224,0.3)', color: '#4fa3e0' }}>
            🌤 Live Weather
          </span>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="soil-description">
              Soil Description *
            </label>
            <textarea
              id="soil-description"
              className="input-field"
              rows={5}
              placeholder="Describe your soil naturally... e.g., 'My soil is dark brown, sticky when wet, forms hard clumps when dry, holds water a long time and drains slowly. I notice earthworms. I want to grow tomatoes.'"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              required
              minLength={10}
            />
            <div className="char-count">{description.length} chars</div>

            {/* Example prompts */}
            <div className="example-prompts">
              <p className="example-label">Try an example:</p>
              <div className="example-chips">
                {EXAMPLE_PROMPTS.map((p, i) => (
                  <button
                    key={i}
                    type="button"
                    className="example-chip"
                    onClick={() => useExample(p)}
                  >
                    {p.length > 45 ? p.slice(0, 45) + '…' : p}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="form-row">
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label" htmlFor="location">
                📍 Location
              </label>
              <input
                id="location"
                className="input-field"
                type="text"
                placeholder="e.g., Pune, India"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
              />
            </div>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label" htmlFor="target-crop">
                🌾 Target Crop (optional)
              </label>
              <input
                id="target-crop"
                className="input-field"
                type="text"
                placeholder="e.g., Tomato, Wheat"
                value={targetCrop}
                onChange={(e) => setTargetCrop(e.target.value)}
              />
            </div>
          </div>

          {error && (
            <div className="error-message" role="alert">
              ⚠️ {error}
            </div>
          )}

          <button
            type="submit"
            className="btn-primary analyze-btn"
            disabled={loading || description.trim().length < 10}
            id="analyze-btn"
          >
            {loading ? (
              <>
                <span className="spinner" />
                Analysing Soil…
              </>
            ) : (
              <>
                🔬 Analyse My Soil
              </>
            )}
          </button>
        </form>
      </div>

      {/* Feature pills */}
      <div className="hero-features">
        {[
          'Natural language understanding',
          'ML pH estimation',
          'Honest uncertainty',
          'Live weather',
          'Crop recommendations',
          'No fake measurements',
        ].map((f) => (
          <div key={f} className="hero-feature">
            <div className="hero-feature-dot" />
            {f}
          </div>
        ))}
      </div>
    </section>
  );
}
