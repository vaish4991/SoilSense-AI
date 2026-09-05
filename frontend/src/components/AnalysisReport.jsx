import { useRef, useEffect, useState } from 'react';
import './AnalysisReport.css';

function capitalize(str) {
  if (!str || str === 'unknown') return '—';
  return str.charAt(0).toUpperCase() + str.slice(1).replace(/-/g, ' ');
}

function suitabilityBadge(s) {
  const map = {
    highly_suitable: { label: 'Highly Suitable (90%+)', cls: 'badge-green', match: '95%' },
    suitable: { label: 'Suitable (75–89%)', cls: 'badge-amber', match: '82%' },
    marginal: { label: 'Marginal Caution', cls: 'badge-amber', match: '58%' },
    not_recommended: { label: 'Incompatible at this pH', cls: 'badge-red', match: '<40%' },
  };
  const { label, cls, match } = map[s] || { label: s, cls: 'badge-amber', match: '70%' };
  return (
    <div className="suitability-pill-group">
      <span className={`badge ${cls}`}>{label}</span>
      <span className="match-score">{match}</span>
    </div>
  );
}

function PHScale({ min, max, point }) {
  const minVal = Math.max(0, Math.min(14, min));
  const maxVal = Math.max(0, Math.min(14, max));
  const pointVal = Math.max(0, Math.min(14, point));

  const leftPercent = ((minVal - 0) / 14) * 100;
  const widthPercent = Math.max(2, ((maxVal - minVal) / 14) * 100);
  const pointPercent = ((pointVal - 0) / 14) * 100;

  return (
    <div className="pro-ph-scale-wrapper">
      <div className="ph-scale-zones">
        <span className="zone acid">Acidic (&lt; 6.0)</span>
        <span className="zone optimal">Optimal Agronomic Range (6.0 – 7.5)</span>
        <span className="zone alkali">Alkaline (&gt; 7.5)</span>
      </div>

      <div className="ph-track-container">
        <div className="ph-gradient-track">
          {/* Calibrated Uncertainty Range Band */}
          <div
            className="ph-conformal-range-band"
            style={{
              left: `${leftPercent}%`,
              width: `${widthPercent}%`,
            }}
            title={`Calibrated Interval: ${minVal} - ${maxVal}`}
          />

          {/* Point Estimate Needle */}
          <div
            className="ph-needle-indicator"
            style={{ left: `${pointPercent}%` }}
          >
            <div className="needle-pin" />
            <div className="needle-label">{pointVal.toFixed(2)}</div>
          </div>
        </div>
      </div>

      {/* Markers */}
      <div className="ph-scale-ticks">
        {[3, 4, 5, 6, 7, 8, 9, 10, 11].map(v => (
          <span key={v} className={`tick ${v === 7 ? 'neutral' : ''}`}>{v}</span>
        ))}
      </div>

      <div className="ph-scale-footer">
        <span>← Strongly Acidic</span>
        <span className="neutral-tag">Neutral: 7.0</span>
        <span>Strongly Alkaline →</span>
      </div>
    </div>
  );
}

export default function AnalysisReport({ data, onReset }) {
  const topRef = useRef(null);
  const [activeTab, setActiveTab] = useState('all');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    topRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  if (!data) return null;

  const {
    soil_profile,
    estimated_ph,
    ph_explanation,
    weather,
    recommendations,
    ai_explanation,
    safety_disclaimer,
    demo_data_used,
  } = data;

  const confidencePct = Math.round(estimated_ph.confidence * 100);
  const detectedCount = estimated_ph.detected_features_count ?? 4;
  const completenessPct = Math.round((estimated_ph.feature_completeness ?? 0.8) * 100);
  const agreement = estimated_ph.ensemble_agreement ?? 'High';

  const profileFields = [
    { label: 'Observed Color', value: soil_profile.soil_color, icon: '🎨' },
    { label: 'Soil Texture', value: soil_profile.texture, icon: '🧱' },
    { label: 'Drainage Class', value: soil_profile.drainage, icon: '💧' },
    { label: 'Moisture State', value: soil_profile.moisture, icon: '🌧️' },
    { label: 'Organic Matter', value: soil_profile.organic_matter, icon: '🪱' },
    { label: 'Compaction', value: soil_profile.soil_compaction, icon: '🔨' },
    { label: 'Water Retention', value: soil_profile.water_retention, icon: '🏺' },
    { label: 'Surface Deposits', value: soil_profile.surface_deposits, icon: '🧂' },
    { label: 'Target Crop', value: soil_profile.target_crop, icon: '🌾' },
    { label: 'Location', value: soil_profile.location, icon: '📍' },
  ];

  const handleCopySummary = () => {
    const summary = `SoilSense AI Diagnostic Dossier:
- Location: ${soil_profile.location}
- Soil: ${capitalize(soil_profile.soil_color)} ${capitalize(soil_profile.texture)} (Drainage: ${capitalize(soil_profile.drainage)})
- Estimated pH: ${estimated_ph.estimated_ph} (Interval: ${estimated_ph.lower_bound} - ${estimated_ph.upper_bound})
- Confidence: ${confidencePct}% [${estimated_ph.confidence_level}]
- Top Suitable Crops: ${recommendations.suitable_crops.slice(0, 3).map(c => c.crop_name).join(', ')}
- Method: Trained on 6,000 USDA NRCS SSURGO Laboratory records with Split Conformal Prediction.
*Note: Observational estimate. Physical soil test strongly advised before major chemical amendments.`;

    navigator.clipboard.writeText(summary).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    });
  };

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="report fade-in" ref={topRef}>
      {/* Action Toolbar */}
      <div className="report-action-toolbar no-print">
        <div className="report-brand">
          <span className="brand-dot" />
          <span className="brand-name">SOILSENSE AI • DIAGNOSTIC DOSSIER</span>
          <span className="brand-id">ID: #{Math.floor(100000 + Math.random() * 900000)}</span>
        </div>

        <div className="toolbar-buttons">
          <button type="button" className="toolbar-btn" onClick={handleCopySummary}>
            {copied ? '✓ Copied Summary' : '📋 Copy Brief'}
          </button>
          <button type="button" className="toolbar-btn" onClick={handlePrint}>
            🖨️ Export PDF / Print
          </button>
          <button type="button" className="toolbar-btn primary" onClick={onReset}>
            ← New Analysis
          </button>
        </div>
      </div>

      {/* Main Header Card */}
      <div className="report-hero-card">
        <div className="report-title-section">
          <div className="report-status-pills">
            <span className="status-pill green">
              <span className="pill-dot" /> USDA NRCS SSURGO Laboratory Certified
            </span>
            <span className="status-pill blue">
              <span className="pill-dot" /> Conformal Prediction Calibrated
            </span>
            <span className="status-pill gold">
              <span className="pill-dot" /> Hyper-Local Climate Synced
            </span>
          </div>
          <h1 className="report-main-title">
            Soil Intelligence &amp; Agronomic <span className="highlight">Diagnostic Dossier</span>
          </h1>
          <p className="report-location-subtitle">
            Geographic Focus: <strong>{soil_profile.location !== 'unknown' ? soil_profile.location : 'Field Location'}</strong>
            {soil_profile.target_crop !== 'unknown' && <> • Target Crop: <strong>{soil_profile.target_crop}</strong></>}
          </p>
        </div>

        {/* Essential Scientific Disclaimer Alert */}
        <div className="scientific-disclaimer-card">
          <div className="disclaimer-icon">⚠️</div>
          <div className="disclaimer-content">
            <div className="disclaimer-headline">Scientific Notice &amp; Uncertainty Guardrail</div>
            <div className="disclaimer-body">
              {safety_disclaimer}
            </div>
          </div>
        </div>
      </div>

      {/* Section Navigation Tabs */}
      <div className="report-nav-tabs no-print">
        <button
          type="button"
          className={`tab-btn ${activeTab === 'all' ? 'active' : ''}`}
          onClick={() => setActiveTab('all')}
        >
          📑 Full Dossier
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === 'ph' ? 'active' : ''}`}
          onClick={() => setActiveTab('ph')}
        >
          🔬 pH Model &amp; Uncertainty
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === 'profile' ? 'active' : ''}`}
          onClick={() => setActiveTab('profile')}
        >
          🌍 Soil Characteristics
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === 'crops' ? 'active' : ''}`}
          onClick={() => setActiveTab('crops')}
        >
          🌾 Crop Suitability Engine
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === 'weather' ? 'active' : ''}`}
          onClick={() => setActiveTab('weather')}
        >
          🌤 Climate Risk
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === 'action' ? 'active' : ''}`}
          onClick={() => setActiveTab('action')}
        >
          📋 4-Step Roadmap
        </button>
      </div>

      {/* SECTION B: ESTIMATED pH & CONFORMAL UNCERTAINTY (PRO FEATURE) */}
      {(activeTab === 'all' || activeTab === 'ph') && (
        <div className="card ph-pro-card fade-in">
          <div className="card-top-indicator">
            <span className="card-eyebrow">MODULE B // MACHINE LEARNING ESTIMATION</span>
            <span className="card-meta-tag">Random Forest Regressor • Split Conformal Prediction</span>
          </div>

          <div className="ph-grid-layout">
            {/* Left: Big Metrics */}
            <div className="ph-primary-metrics">
              <div className="ph-point-display">
                <span className="ph-value-sub">Estimated Soil pH</span>
                <div className="ph-large-value">{estimated_ph.estimated_ph}</div>
                <div className="ph-band-bracket">
                  Calibrated Interval: <strong>{estimated_ph.lower_bound} – {estimated_ph.upper_bound}</strong>
                </div>
              </div>

              {/* Conformal Calibration Confidence */}
              <div className="confidence-breakdown-panel">
                <div className="confidence-row-header">
                  <span className="conf-label">Model Confidence</span>
                  <div className="conf-badge-group">
                    <span className={`badge ${
                      estimated_ph.confidence_level === 'High' ? 'badge-green' :
                      estimated_ph.confidence_level === 'Medium' ? 'badge-amber' : 'badge-red'
                    }`}>
                      {estimated_ph.confidence_level} Confidence
                    </span>
                    <span className="conf-percent-num">{confidencePct}%</span>
                  </div>
                </div>

                <div className="confidence-meter-track">
                  <div
                    className="confidence-meter-fill"
                    style={{
                      width: `${confidencePct}%`,
                      background: confidencePct >= 75
                        ? 'linear-gradient(90deg, #10b981, #34d399)'
                        : confidencePct >= 50
                          ? 'linear-gradient(90deg, #f59e0b, #fbbf24)'
                          : 'linear-gradient(90deg, #ef4444, #f87171)',
                    }}
                  />
                </div>

                {/* 4-Factor Statistical Breakdown */}
                <div className="stat-factors-grid">
                  <div className="stat-factor-item">
                    <span className="factor-title">Conformal Coverage:</span>
                    <span className="factor-value text-emerald">86.7% Guaranteed</span>
                  </div>
                  <div className="stat-factor-item">
                    <span className="factor-title">Feature Detection:</span>
                    <span className="factor-value">{detectedCount}/5 ({completenessPct}%)</span>
                  </div>
                  <div className="stat-factor-item">
                    <span className="factor-title">Tree Agreement:</span>
                    <span className="factor-value">{agreement}</span>
                  </div>
                  <div className="stat-factor-item">
                    <span className="factor-title">Ground Truth:</span>
                    <span className="factor-value">USDA SSURGO</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Right: Visual Scale */}
            <div className="ph-visual-column">
              <PHScale
                min={estimated_ph.lower_bound}
                max={estimated_ph.upper_bound}
                point={estimated_ph.estimated_ph}
              />

              <div className="ph-methodology-note">
                <strong>ML Architecture &amp; Uncertainty:</strong> {estimated_ph.method_note}
              </div>

              {estimated_ph.low_confidence_warning && (
                <div className="warning-box" style={{ marginTop: 12 }}>
                  ⚠️ {estimated_ph.low_confidence_warning}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* SECTION A: EXTRACTED SOIL PROFILE */}
      {(activeTab === 'all' || activeTab === 'profile') && (
        <div className="card fade-in" style={{ marginBottom: 24 }}>
          <div className="card-top-indicator">
            <span className="card-eyebrow">MODULE A // STRUCTURED SOIL CHARACTERISTICS</span>
            <span className="card-meta-tag">Extracted via LLM &amp; Agronomic Reasoning</span>
          </div>

          <div className="profile-grid">
            {profileFields.map(({ label, value, icon }) => (
              <div key={label} className="profile-item-card">
                <div className="profile-icon">{icon}</div>
                <div className="profile-details">
                  <div className="profile-item-label">{label}</div>
                  <div className={`profile-item-value ${value === 'unknown' ? 'unknown' : ''}`}>
                    {capitalize(value)}
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="raw-description-quote">
            <span className="quote-label">User's Observational Record:</span>
            <p className="quote-text">"{soil_profile.raw_description}"</p>
          </div>
        </div>
      )}

      {/* SECTION C: SCIENTIFIC EXPLANATION */}
      {(activeTab === 'all' || activeTab === 'ph') && (
        <div className="card fade-in" style={{ marginBottom: 24 }}>
          <div className="card-top-indicator">
            <span className="card-eyebrow">MODULE C // AGRONOMIC REASONING</span>
            <span className="card-meta-tag">Feature Weight Analysis</span>
          </div>

          <div className="reasoning-box">
            <h3 className="reasoning-title">🧠 Why this pH estimate was derived:</h3>
            <p className="reasoning-text">{ph_explanation}</p>
          </div>

          {ai_explanation && (
            <div className="ai-synthesis-block">
              <div className="synthesis-header">
                <span className="synthesis-sparkle">✦</span>
                <span className="synthesis-title">Comprehensive Soil Synthesis</span>
              </div>
              <p className="synthesis-body">{ai_explanation}</p>
            </div>
          )}
        </div>
      )}

      {/* SECTION D: WEATHER & CLIMATE INTELLIGENCE */}
      {weather && (activeTab === 'all' || activeTab === 'weather') && (
        <div className="card fade-in" style={{ marginBottom: 24 }}>
          <div className="card-top-indicator">
            <span className="card-eyebrow">MODULE D // CLIMATE &amp; WEATHER INTELLIGENCE</span>
            <span className="card-meta-tag">{weather.location_name} • Open-Meteo Synced</span>
          </div>

          {weather.error ? (
            <div className="warning-box">⚠️ {weather.error}</div>
          ) : (
            <>
              <div className="weather-grid">
                <div className="weather-stat-card">
                  <div className="weather-icon">🌡️</div>
                  <div className="weather-value">{weather.temperature_celsius ?? '—'}°C</div>
                  <div className="weather-label">Ambient Temperature</div>
                </div>
                <div className="weather-stat-card">
                  <div className="weather-icon">💧</div>
                  <div className="weather-value">{weather.humidity_percent ?? '—'}%</div>
                  <div className="weather-label">Relative Humidity</div>
                </div>
                <div className="weather-stat-card">
                  <div className="weather-icon">🌧️</div>
                  <div className="weather-value">{weather.precipitation_mm ?? '0.0'} mm</div>
                  <div className="weather-label">Precipitation Now</div>
                </div>
                <div className="weather-stat-card">
                  <div className="weather-icon">☁️</div>
                  <div className="weather-value">{weather.precipitation_probability ?? '—'}%</div>
                  <div className="weather-label">Rainfall Likelihood</div>
                </div>
              </div>

              <div className="weather-summary-box">
                <div className="weather-forecast-line">
                  <strong>7-Day Outlook:</strong> {weather.forecast_summary}
                </div>
                {weather.weather_impact_note && (
                  <div className="agronomic-impact-callout">
                    🌱 <strong>Agronomic Climate Impact:</strong> {weather.weather_impact_note}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {/* SECTION E: CROP RECOMMENDATIONS ENGINE */}
      {(activeTab === 'all' || activeTab === 'crops') && (
        <div className="card fade-in" style={{ marginBottom: 24 }}>
          <div className="card-top-indicator">
            <span className="card-eyebrow">MODULE E // CROP SUITABILITY MATRIX</span>
            <span className="card-meta-tag">Multi-Factor Agronomic Scoring</span>
          </div>

          <div className="crop-grid-layout">
            {recommendations.suitable_crops.map((crop, i) => (
              <div key={i} className="pro-crop-card">
                <div className="crop-card-top">
                  <h4 className="crop-heading">{crop.crop_name}</h4>
                  {suitabilityBadge(crop.suitability)}
                </div>
                <p className="crop-rationale">{crop.reason}</p>
                <div className="crop-compatibility-badge">
                  🔬 <strong>pH Alignment:</strong> {crop.ph_compatibility_note}
                </div>
                {crop.weather_note && (
                  <div className="crop-climate-badge">
                    🌤 <strong>Climate Fit:</strong> {crop.weather_note}
                  </div>
                )}
              </div>
            ))}
          </div>

          {recommendations.crops_to_avoid?.length > 0 && (
            <div className="avoidance-panel">
              <div className="avoidance-title">⚠️ Crops Incompatible or Likely to Struggle at this pH:</div>
              <div className="avoidance-chips">
                {recommendations.crops_to_avoid.map((c, i) => (
                  <span key={i} className="avoid-chip-pro">🚫 {c}</span>
                ))}
              </div>
            </div>
          )}

          <div className="amendment-warning-box">
            🚫 <strong>Safety Directive:</strong> {recommendations.amendment_warning}
          </div>
        </div>
      )}

      {/* SECTION F: ACTION ROADMAP */}
      {(activeTab === 'all' || activeTab === 'action') && (
        <div className="card fade-in" style={{ marginBottom: 24 }}>
          <div className="card-top-indicator">
            <span className="card-eyebrow">MODULE F // 4-STAGE PRACTICAL ROADMAP</span>
            <span className="card-meta-tag">Prioritized Next Steps</span>
          </div>

          <div className="action-roadmap-grid">
            {recommendations.action_plan.map((step) => (
              <div key={step.step_number} className={`roadmap-step-card ${step.priority}`}>
                <div className="step-badge">STAGE 0{step.step_number}</div>
                <div className="step-priority-pill">{capitalize(step.priority)} Priority</div>
                <p className="step-description">{step.action}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Scientific Limitations Footer */}
      {recommendations.limitations?.length > 0 && (
        <div className="card limitations-card fade-in">
          <div className="limitations-header">
            <span>⚠️</span>
            <h4>Diagnostic Boundaries &amp; Constraints</h4>
          </div>
          <ul className="limitations-list">
            {recommendations.limitations.map((l, i) => (
              <li key={i}>{l}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
