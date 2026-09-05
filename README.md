# SoilSense AI 🌱

**An AI-powered soil intelligence agent** — Razorpay AI Buildathon (Open Track)

> Describe your soil in plain language. Get ML pH estimation with honest uncertainty, live weather, and crop recommendations.

---

## ⚠️ Scientific Honesty First

This system **ESTIMATES** soil pH from observable soil characteristics. It is **NOT** a laboratory measurement. Every result is accompanied by:

- A **confidence score** derived from ensemble model spread
- A **pH range** (not a single number)
- A **safety disclaimer** reminding users to confirm with a physical soil test before applying amendments

---

## 1. Problem

Smallholder farmers and home gardeners often lack immediate access to laboratory soil testing. A simple question — "Is my soil acidic or alkaline?" — can determine the success or failure of an entire crop cycle, yet the answer requires lab equipment most users don't have.

SoilSense AI bridges this gap by:
- Understanding natural-language soil descriptions
- Extracting structured soil characteristics using LLM
- Predicting an **estimated** pH range using a trained ML model
- Integrating live weather data
- Recommending suitable crops with honest caveats

---

## 2. Architecture

```mermaid
flowchart TD
    A[User: Natural Language Description\n+ Location + Target Crop] --> B[FastAPI Backend]
    B --> C[Soil Agent Orchestrator]
    C --> D[LLM Feature Extractor\nGemini / OpenAI]
    D --> E{Enough Info?}
    E -- No --> F[Follow-up Questions → User]
    E -- Yes --> G[ML pH Estimator\nRandom Forest\nbacked/ml/predict.py]
    G --> H[Uncertainty Engine\nEnsemble Spread\n10th–90th percentile]
    H --> I[Weather Service\nOpen-Meteo API]
    I --> J[Crop Recommendation Engine\nRule-based DB + scoring]
    J --> K[LLM Explanation Layer\nExplains ML output]
    K --> L[Soil Intelligence Report]
    L --> M[React + Vite Frontend]
```

**Critical architectural separation:**
- The **LLM** handles language understanding and explanation only
- The **ML model** handles numerical pH prediction only
- These are never mixed

---

## 3. AI Agent Workflow

1. **User submits** natural-language soil description
2. **Feature Extractor** (LLM) converts text → structured JSON with controlled enum values
3. **Sufficiency Check**: If ≥3 core features (texture, drainage, colour) are known → proceed. Otherwise → ask targeted follow-up questions
4. **ML Predictor**: Random Forest (200 trees) predicts pH for each tree; 10th–90th percentile = pH range
5. **Confidence**: Derived from tree prediction spread; penalised for unknown inputs
6. **Weather**: Open-Meteo Geocoding + Forecast APIs (no key required)
7. **Recommendations**: Rule-based crop database scored by pH compatibility, texture, drainage, and weather
8. **Explanation**: LLM summarises the ML output in plain English (does NOT generate pH numbers)

---

## 4. ML Model & Uncertainty Calibration

### Real-World Measured Dataset
- **Data Source**: [USDA NRCS Soil Data Access (SDA) — SSURGO Database](https://sdmdataaccess.sc.egov.usda.gov/)
- **Sample Count**: **6,000 real-world soil samples** across 6,000 unique pedon/soil components (`cokey`)
- **Target Variable**: Laboratory-measured `ph1to1h2o_r` (standard 1:1 soil:water solution pH, range: 4.0 to 9.5, mean: 5.54)
- **Zero Data Leakage**: Evaluated with strictly grouped splits on `cokey` (`GroupShuffleSplit` and `GroupKFold`). Records belonging to the same soil profile or location are NEVER shared across train, calibration, and test folds.

### Candidate Model Comparison (5-Fold Group Cross-Validation)

| Model | CV MAE (Mean ± Std) | CV RMSE (Mean ± Std) | CV R² (Mean ± Std) | Status |
|-------|---------------------|----------------------|--------------------|--------|
| **Random Forest** | **0.3727 ± 0.0116** | **0.5502 ± 0.0220** | **0.6630 ± 0.0134** | **Selected Best** |
| Extra Trees | 0.3743 ± 0.0101 | 0.5623 ± 0.0199 | 0.6480 ± 0.0085 | Runner-up |
| Gradient Boosting | 0.3858 ± 0.0123 | 0.5568 ± 0.0153 | 0.6548 ± 0.0048 | Candidate |
| Ridge (Linear Baseline)| 0.4562 ± 0.0161 | 0.6301 ± 0.0190 | 0.5579 ± 0.0125 | Baseline |

### Independent Test Set Evaluation (900 Unseen Samples)
- **Test MAE**: **0.3705** pH units
- **Test RMSE**: **0.5514**
- **Test R²**: **0.6485**
- **Empirical Conformal Coverage**: **86.67%** (target: 85.0%)
- **Average Prediction Interval Width**: **1.33 pH units**

### Uncertainty Estimation: Split Conformal Prediction
Instead of uncalibrated heuristics or hard-coded confidence, SoilSense AI implements **Split Conformal Prediction**:
1. **Calibration Set**: A held-out calibration set (900 samples, disjoint by `cokey`) is used to calculate nonconformity scores $s_i = |y_i - \hat{y}_i|$.
2. **Conformal Margin**: The calibrated margin $q_{1-\alpha} = 0.6644$ guarantees an 85% nominal prediction coverage with finite-sample correction.
3. **Adaptive Scaling**: The interval is dynamically scaled by local tree spread ($\sigma_{\text{tree}}$) and penalized by input missingness:
   $$\text{margin}(x) = q \times \left(0.80 + 0.20 \times \frac{\sigma_{\text{tree}}}{\text{median\_spread}}\right) \times (1.0 + 0.12 \times n_{\text{unknown}})$$
4. **Honest Confidence Level**:
   - `High`: Confidence $\ge 65\%$, at most 1 missing feature, and narrow interval ($\le 1.2$ pH units).
   - `Medium`: Confidence $\ge 40\%$, at most 2 missing features, and interval width $\le 1.7$ pH units.
   - `Low`: Confidence $< 40\%$, $\ge 3$ missing features, or wide interval ($> 1.7$ pH units).
   - **Constraint**: Confidence strictly decreases as information is omitted, and is never artificially inflated.

### Real-World Limitations
- Surface observations cannot detect subsoil acidity or hardpans without depth profiling.
- Local management history (recent liming, fertilizer application, irrigation salinity) can shift pH independently of native soil characteristics.
- Physical lab soil testing is always advised before applying major chemical amendments.

---

## 5. Weather Integration

- **Provider**: [Open-Meteo](https://open-meteo.com/) — free, no API key required
- **Geocoding**: Open-Meteo Geocoding API (resolves city names to lat/lon)
- **Data retrieved**: temperature, humidity, precipitation, 7-day forecast, precipitation probability
- **Integration**: Weather data actively changes crop recommendations and action plan steps

---

## 6. Failure Recovery

| Failure | Recovery |
|---------|---------|
| Weather API timeout | Analysis continues; recommendations exclude weather context |
| Invalid location | Clear error message; analysis continues without weather |
| LLM API failure | Rule-based fallback explanation generated |
| ML model not found | Automatic training on startup; rule-based fallback if training fails |
| Malformed LLM JSON | All enum fields default to "unknown"; analysis still runs |
| Low confidence | Warning message shown; user directed to physical soil test |
| Missing description | Frontend validation + 422 from backend |
| Network timeout | User-friendly error with specific remediation steps |

---

## 7. Setup Instructions

### Prerequisites
- Python 3.10+
- Node.js 18+
- A Gemini API key (get free at [aistudio.google.com](https://aistudio.google.com)) and/or OpenAI API key

### 1. Clone and configure
```bash
git clone <repo>
cd soilsense-ai
cp .env.example .env
# Edit .env and add your API key(s)
```

### 2. Backend setup
```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Train the ML model (also runs automatically on first server start)
python -m backend.ml.train
```

### 3. Frontend setup
```bash
cd frontend
npm install
```

### 4. Run

**Terminal 1 — Backend:**
```bash
# From project root
source .venv/bin/activate
python backend/main.py
# Server starts at http://localhost:8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
# App opens at http://localhost:5173
```

---

## 8. Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | ✅ (or OpenAI) | Google Gemini API key |
| `OPENAI_API_KEY` | ✅ (or Gemini) | OpenAI API key (fallback) |
| `BACKEND_HOST` | No | Default: `0.0.0.0` |
| `BACKEND_PORT` | No | Default: `8000` |
| `CORS_ORIGINS` | No | Default: `http://localhost:5173` |
| `LOG_LEVEL` | No | Default: `INFO` |

---

## 9. API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Service health + model status |
| POST | `/api/analyze-soil` | Full soil analysis pipeline |
| POST | `/api/soil/follow-up` | Check if more info is needed |
| POST | `/api/chat` | Multi-turn conversational Q&A |
| GET | `/docs` | Interactive Swagger UI |

### Example Request
```json
POST /api/analyze-soil
{
  "description": "My soil is dark brown, sticky when wet, forms hard clumps when dry. Water drains very slowly. I can see earthworms. I want to grow tomatoes.",
  "location": "Pune, India",
  "target_crop": "Tomato"
}
```

### Example Response (abbreviated)
```json
{
  "soil_profile": {
    "texture": "clay",
    "drainage": "poor",
    "moisture": "wet",
    "organic_matter": "high",
    "soil_color": "dark brown"
  },
  "estimated_ph": {
    "min": 6.1,
    "max": 6.9,
    "midpoint": 6.50,
    "confidence": 0.72
  },
  "weather": { "temperature_celsius": 28.0, "precipitation_probability": 45.0 },
  "recommendations": {
    "suitable_crops": [{"crop_name": "Tomato", "suitability": "suitable", ...}],
    "action_plan": [{"action": "Confirm pH with soil test...", "priority": "high"}]
  },
  "safety_disclaimer": "This is an AI-based estimate..."
}
```

---

## 10. Running Tests

```bash
source .venv/bin/activate
python -m pytest backend/tests/ -v
```

Expected: **18 tests pass**

---

## 11. Limitations

- ML trained on synthetic data — real-world accuracy may differ
- pH estimation from visual/tactile soil characteristics has inherent uncertainty
- Weather recommendations use 7-day forecast, which may not match actual conditions
- Crop database covers ~14 common crops; regional varieties are not included
- No user data is persisted (stateless MVP)

---

## 12. Future Improvements

- [ ] Integrate real soil datasets (USDA NRCS, ISCN, SoilGrids)
- [ ] Upload soil photos for colour analysis via computer vision
- [ ] User accounts and historical soil tracking
- [ ] Soil map overlay (SoilGrids API)
- [ ] Regional crop variety database
- [ ] Offline mode with ONNX model
- [ ] Multi-language support
- [ ] Raspi/IoT integration for physical sensor fusion

---

## Built for Razorpay AI Buildathon — Open Track

This project demonstrates genuine AI judgment:
- LLM for language understanding (not for number generation)
- ML model for numerical prediction
- Honest uncertainty quantification
- Real weather integration
- Graceful failure recovery

The system is designed to be genuinely useful to a real farmer — not a demo chatbot.
