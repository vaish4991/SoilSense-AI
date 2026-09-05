import { useRef, useEffect } from 'react';
import { RadialBarChart, RadialBar, ResponsiveContainer } from 'recharts';
import './AnalysisReport.css';

// ── Helpers ──────────────────────────────────────────────────

function capitalize(str) {
  if (!str || str === 'unknown') return '—';
  return str.charAt(0).toUpperCase() + str.slice(1).replace(/-/g, ' ');
}

function suitabilityBadge(s) {
  const map = {
    highly_suitable: { label: 'Highly Suitable', cls: 'badge-green' },
    suitable: { label: 'Suitable', cls: 'badge-amber' },
    marginal: { label: 'Marginal', cls: 'badge-red' },
    not_recommended: { label: 'Not Recommended', cls: 'badge-red' },
  };
  const { label, cls } = map[s] || { label: s, cls: 'badge-amber' };
  return <span className={`badge ${cls}`}>{label}</span>;
}

function PHScale({ min, max }) {
  const pHToPercent = (ph) => ((ph - 0) / 14) * 100;
  const midPoint = (min + max) / 2;
  const leftPct = pHToPercent(midPoint);

  return (
    <div className="ph-scale">
      <div className="ph-scale-track">
        <div
          className="ph-indicator"
          style={{ left: `${leftPct}%` }}
          title={`pH ${midPoint.toFixed(1)}`}
        />
      </div>
      <div className="ph-scale-markers">
        {[0, 2, 4, 6, 7, 8, 10, 12, 14].map(v => (
          <span key={v}>{v}</span>
        ))}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>
        <span>← Acidic</span>
        <span>Neutral</span>
        <span>Alkaline →</span>
      </div>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────

export default function AnalysisReport({ data, onReset }) {
  const topRef = useRef(null);

  useEffect(() => {
    topRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  if (!data) return null;

  const { soil_profile, estimated_ph, ph_explanation, weather, recommendations, ai_explanation, safety_disclaimer, demo_data_used } = data;
  const confidencePct = Math.round(estimated_ph.confidence * 100);

  const profileFields = [
    { label: 'Colour', value: soil_profile.soil_color },
    { label: 'Texture', value: soil_profile.texture },
    { label: 'Drainage', value: soil_profile.drainage },
    { label: 'Moisture', value: soil_profile.moisture },
    { label: 'Organic Matter', value: soil_profile.organic_matter },
    { label: 'Compaction', value: soil_profile.soil_compaction },
    { label: 'Water Retention', value: soil_profile.water_retention },
    { label: 'Surface Deposits', value: soil_profile.surface_deposits },
    { label: 'Organisms Noted', value: soil_profile.vegetation_observed },
    { label: 'Location', value: soil_profile.location },
    { label: 'Target Crop', value: soil_profile.target_crop },
  ];

  return (
    <div className="report fade-in" ref={topRef}>
      {/* Header */}
      <div className="report-header">
        <div>
          <div className="section-label">SoilSense AI Report</div>
          <h2 className="report-title">Soil <span>Intelligence</span> Report</h2>
        </div>
        <button className="back-btn" onClick={onReset}>
          ← New Analysis
        </button>
      </div>

      {/* Demo banner */}
      {demo_data_used && (
        <div className="demo-banner">
          🧪 <strong>Synthetic Dataset:</strong> ML trained on agronomically-grounded synthetic data. Replace with real field measurements for production use.
        </div>
      )}

      {/* Safety disclaimer */}
      <div className="disclaimer" style={{ marginBottom: 24 }}>
        ⚠️ {safety_disclaimer}
      </div>

      {/* A. SOIL PROFILE */}
      <div className="card fade-in" style={{ marginBottom: 20 }}>
        <div className="section-title">🌍 A — Soil Profile</div>
        <p className="section-subtitle">Extracted from your natural-language description</p>
        <div className="profile-grid">
          {profileFields.map(({ label, value }) => (
            <div key={label} className="profile-item">
              <div className="profile-item-label">{label}</div>
              <div className={`profile-item-value ${value === 'unknown' ? 'unknown' : ''}`}>
                {capitalize(value)}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* B. ESTIMATED pH */}
      <div className="card ph-card fade-in" style={{ marginBottom: 20 }}>
        <div className="ph-disclaimer-badge">🔬 AI Estimate — Not a Lab Measurement</div>

        <div className="grid-2" style={{ alignItems: 'start' }}>
          <div>
            <div className="section-label">Estimated pH Range</div>
            <div className="ph-range">{estimated_ph.min} – {estimated_ph.max}</div>
            <div className="ph-label">Midpoint: {estimated_ph.midpoint}</div>

            <div className="ph-confidence">
              <div className="ph-confidence-header">
                <span className="ph-confidence-label">Model Confidence</span>
                <span className="ph-confidence-value">{confidencePct}%</span>
              </div>
              <div className="progress-track">
                <div
                  className="progress-fill"
                  style={{
                    width: `${confidencePct}%`,
                    background: confidencePct > 65
                      ? 'linear-gradient(90deg, #4a7c59, #6aaa7a)'
                      : confidencePct > 40
                        ? 'linear-gradient(90deg, #c97b2a, #e8a840)'
                        : 'linear-gradient(90deg, #ef4444, #f87171)',
                  }}
                />
              </div>
            </div>

            <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>
              {estimated_ph.method_note}
            </p>
          </div>

          <div>
            <PHScale min={estimated_ph.min} max={estimated_ph.max} />
          </div>
        </div>

        {estimated_ph.low_confidence_warning && (
          <div className="warning-box">
            ⚠️ {estimated_ph.low_confidence_warning}
          </div>
        )}
      </div>

      {/* C. WHY THIS RESULT */}
      <div className="card fade-in" style={{ marginBottom: 20 }}>
        <div className="section-title">🧠 C — Why This Result?</div>
        <p className="section-subtitle">Features that influenced the ML model's pH prediction</p>
        <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.7 }}>
          {ph_explanation}
        </p>
      </div>

      {/* D. WEATHER */}
      {weather && (
        <div className="card fade-in" style={{ marginBottom: 20 }}>
          <div className="section-title">🌤 D — Weather: {weather.location_name}</div>

          {weather.error ? (
            <div className="warning-box" style={{ marginTop: 12 }}>
              ⚠️ {weather.error}
            </div>
          ) : (
            <>
              <div className="weather-grid">
                {weather.temperature_celsius !== null && (
                  <div className="weather-stat">
                    <div className="weather-stat-icon">🌡️</div>
                    <div className="weather-stat-value">{weather.temperature_celsius}°C</div>
                    <div className="weather-stat-label">Temperature</div>
                  </div>
                )}
                {weather.humidity_percent !== null && (
                  <div className="weather-stat">
                    <div className="weather-stat-icon">💧</div>
                    <div className="weather-stat-value">{weather.humidity_percent}%</div>
                    <div className="weather-stat-label">Humidity</div>
                  </div>
                )}
                {weather.precipitation_mm !== null && (
                  <div className="weather-stat">
                    <div className="weather-stat-icon">🌧</div>
                    <div className="weather-stat-value">{weather.precipitation_mm} mm</div>
                    <div className="weather-stat-label">Precip. now</div>
                  </div>
                )}
                {weather.precipitation_probability !== null && (
                  <div className="weather-stat">
                    <div className="weather-stat-icon">☁️</div>
                    <div className="weather-stat-value">{weather.precipitation_probability}%</div>
                    <div className="weather-stat-label">Rain chance</div>
                  </div>
                )}
              </div>

              <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '12px 0 0' }}>
                {weather.forecast_summary}
              </p>

              {weather.weather_impact_note && (
                <div className="weather-impact">
                  🌱 <strong>Agronomic Impact:</strong> {weather.weather_impact_note}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* E. CROP RECOMMENDATIONS */}
      <div className="card fade-in" style={{ marginBottom: 20 }}>
        <div className="section-title">🌾 E — Crop Recommendations</div>
        <p className="section-subtitle">Based on estimated pH, soil texture, drainage, and weather</p>

        <div className="crop-list">
          {recommendations.suitable_crops.map((crop, i) => (
            <div key={i} className="crop-card">
              <div className="crop-header">
                <span className="crop-name">{crop.crop_name}</span>
                {suitabilityBadge(crop.suitability)}
              </div>
              <p className="crop-reason">{crop.reason}</p>
              <p className="crop-ph-note">🔬 {crop.ph_compatibility_note}</p>
              {crop.weather_note && (
                <p className="crop-weather-note">🌤 {crop.weather_note}</p>
              )}
            </div>
          ))}
        </div>

        {recommendations.crops_to_avoid?.length > 0 && (
          <div style={{ marginTop: 20 }}>
            <div className="section-label">Crops likely to struggle at this pH</div>
            <div className="crops-to-avoid">
              {recommendations.crops_to_avoid.map((c, i) => (
                <span key={i} className="avoid-chip">{c}</span>
              ))}
            </div>
          </div>
        )}

        <div className="disclaimer" style={{ marginTop: 16 }}>
          🚫 {recommendations.amendment_warning}
        </div>
      </div>

      {/* F. ACTION PLAN */}
      <div className="card fade-in" style={{ marginBottom: 20 }}>
        <div className="section-title">📋 F — Action Plan</div>
        <div className="action-steps">
          {recommendations.action_plan.map((step) => (
            <div key={step.step_number} className="action-step">
              <div className={`step-number ${step.priority}`}>{step.step_number}</div>
              <p className="step-text">{step.action}</p>
            </div>
          ))}
        </div>
      </div>

      {/* AI Explanation */}
      {ai_explanation && (
        <div className="card fade-in" style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
            <div className="section-title">✦ AI Explanation</div>
            <span className="ai-chip">Gemini / GPT</span>
          </div>
          <p className="explanation-text">{ai_explanation}</p>
        </div>
      )}

      {/* Limitations */}
      {recommendations.limitations?.length > 0 && (
        <div className="card fade-in">
          <div className="section-title">⚠️ Limitations</div>
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
