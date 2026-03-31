# Smart India Agri Intelligence & Prediction System

## Complete Project Documentation (PDF-Ready)

Academic Year: 2025-26

Project Type: Integrated AI-Based Agriculture Decision Support System

---

## 1. Existing System

Before the unified system was assembled, this project existed as separate module applications and scripts across folders. Each module worked for a specific task, but there was no single end-to-end decision flow in one interface.

### 1.1 Existing Project Baseline (Before Unified Flow)

- Independent module apps were present in separate folders:
  - CROP RECOMMENDATION MODEL/app.py
  - CROP YIELD MODEL/CP/CP/app.py
  - CROP PRICE MODEL/app.py
  - SOIL HEALTH DASHBOARD/app.py
- Training scripts and notebooks existed per module, but not as one combined farmer decision experience.
- UI templates and static assets were distributed across module folders.

### 1.2 Limitations in the Baseline Project Structure

- No single route previously combined crop recommendation, yield, price, and soil outputs into one response.
- Model outputs were available per module, but not fused into one final decision text.
- Data flow and user journey were module-specific, not consolidated.
- Missing-model fallback behavior was not centrally handled until unified orchestration.

---

## 2. Project Evidence from Current Files

| File / Component                         | Evidence in Project                                                                     | Purpose in System                                                 | Current Limitation                                        |
| ---------------------------------------- | --------------------------------------------------------------------------------------- | ----------------------------------------------------------------- | --------------------------------------------------------- |
| app.py (root unified app)                | Unified routes, module loading, fallback-safe prediction pipeline                       | Combines crop + yield + price + soil into one workflow            | Still depends on availability/quality of module artifacts |
| CROP RECOMMENDATION MODEL/train_model.py | RandomForestClassifier + RandomForestRegressor with encoded features                    | Crop recommendation and yield estimation in recommendation module | Quality depends on dataset coverage and class balance     |
| CROP RECOMMENDATION MODEL/app.py         | Dashboard, predictor route, workflow/evaluation views                                   | Farmer-facing recommendation UI and model explanation             | Module UI is separate from other module UIs               |
| CROP YIELD MODEL/CP/CP/app.py            | Advanced/legacy inference modes, metrics (R2, MAE, RMSE), model leaderboard integration | Yield prediction and analytical insights                          | Uses fallback modes when advanced bundle is not available |
| CROP YIELD MODEL/predict.py              | Reusable inference function with artifact detection                                     | Programmatic yield prediction from unified app                    | Requires expected artifact paths to exist                 |
| CROP PRICE MODEL/app.py                  | RandomForestRegressor pipeline, preprocessing, trend and best-market outputs            | Price prediction and farmer-facing selling insights               | Region-specific quality depends on dataset rows           |
| SOIL HEALTH DASHBOARD/app.py             | Weighted soil score and agronomic advisory logic                                        | Soil health scoring, alerts, and recommendations                  | Rule bands are fixed and may need calibration over time   |

### 2.1 Gap Identified from Current Codebase

The codebase already had strong task-specific modules, but lacked a fully unified farmer journey. The current project resolves this by adding an integrated orchestration layer that fuses outputs into one decision package.

---

## 3. Proposed System

The proposed system is a unified AI agriculture platform that combines five modules:

- Crop Recommendation Model
- Crop Yield Prediction Model
- Crop Price Prediction Model
- Soil Health Dashboard
- Farmer Intelligence (Fusion) System

### 3.1 Key Innovation

Instead of running separate isolated tools, the system fuses model outputs into one decision layer for farmers:

- Recommended crop (what to grow)
- Expected yield (how much output)
- Predicted market price (when/where to sell)
- Soil quality insights (how to improve land health)
- Profit-oriented final advisory (decision support)

### 3.2 Deployment Style

- Flask-based web applications for each module
- Unified Flask gateway for integrated prediction and dashboarding
- HTML/CSS/JavaScript UI for farmer-facing interaction

---

## 4. Framework / Algorithm

This project uses a multi-model machine learning framework with separate pipelines per agricultural task.

### 4.1 Algorithms Used in Project

#### A) Crop Recommendation + Yield (Recommendation Module)

- RandomForestClassifier for crop label prediction
- RandomForestRegressor for yield estimation
- OneHotEncoder + ColumnTransformer for categorical feature handling
- LabelEncoder for crop label transformation

#### B) Crop Price Prediction Module

- RandomForestRegressor as primary production model inside pipeline
- OneHotEncoder + ColumnTransformer for mixed categorical/numeric inputs
- Additional comparative evaluation logic includes:
  - Linear Regression
  - SVR
  - Random Forest benchmark variants
  - XGBoost-compatible benchmark references in module scoring

#### C) Crop Yield Module

- Supports advanced bundle model (Gradient Boosted Trees family, including CatBoost/XGBoost leaderboard references)
- Legacy fallback model with saved preprocessor + trained regressor
- Baseline comparison with DummyRegressor
- Evaluation metrics: R2, MAE, RMSE

#### D) Soil Health Module

- Rule-based weighted scoring framework (N, P, K, pH, moisture, organic carbon, electrical conductivity)
- Band-based classification and agronomic advisory generation

### 4.2 Data Preprocessing Strategy

- Missing value handling (numeric coercion + default fill strategy)
- Text normalization for state/district/market/crop names
- Categorical encoding (OneHotEncoder)
- Feature matrix preparation using ColumnTransformer
- Date decomposition into day/month/year for price time features

### 4.3 Feature Selection (Implemented Features)

- Crop Recommendation: season, crop_type, water_source, climate_type, duration_type, farming_system, economic_use, area, fertilizer proxy, pesticide proxy
- Yield: Year, rainfall, pesticides, average temperature, Area, Item
- Price: State, District, Market, Commodity, Variety, Arrival day/month/year, Min price, Max price
- Soil: Nitrogen, Phosphorus, Potassium, pH, moisture, organic carbon, EC

### 4.4 Prediction Pipeline

1. User submits agro-climatic and farm inputs.
2. Crop recommendation model predicts suitable crop.
3. Yield model predicts expected production per hectare.
4. Price model predicts modal market price and trend.
5. Soil module computes soil score and improvement plan.
6. Unified engine computes revenue/profit and final decision text.

---

## 5. Software Requirements

### 5.1 Hardware Requirements

| Component | Observed Project Need                                                                           |
| --------- | ----------------------------------------------------------------------------------------------- |
| Processor | Any modern CPU capable of running Python 3.11 and scikit-learn inference                        |
| RAM       | Sufficient memory to load pandas datasets and serialized model artifacts                        |
| Storage   | Space for datasets, model artifacts (.pkl/.joblib), and static/template files                   |
| Internet  | Optional for deployment/use-case demos; local execution works without mandatory online services |

### 5.2 Software Requirements

| Category              | Technology                                    |
| --------------------- | --------------------------------------------- |
| Programming Language  | Python (3.11+ runtime observed)               |
| Backend Framework     | Flask                                         |
| Frontend              | HTML, CSS, JavaScript, Jinja2 Templates       |
| IDE                   | Visual Studio Code                            |
| Version Control       | Git/GitHub                                    |
| Deployment Runtime    | Gunicorn, Procfile-based app start            |
| Core Python Libraries | pandas, numpy, scikit-learn, joblib           |
| Supporting Libraries  | requests, python-dotenv, Werkzeug, MarkupSafe |

---

## 6. System Architecture

The architecture follows a modular + integrated Flask design.

### 6.1 High-Level Architecture

```text
User Interface (Web Forms / Dashboard)
  |
  v
Unified Flask Gateway
  |
  v
Module Services
  - Crop Recommendation Service
  - Yield Prediction Service
  - Price Prediction Service
  - Soil Health Service
  |
  v
Model Inference Layer (Saved ML Artifacts)
  |
  v
Decision Fusion Layer (Farmer Intelligence)
  |
  v
Output Dashboard (Crop, Yield, Price, Soil, Profit Advice)
```

### 6.2 Architectural Characteristics

- Loose coupling between modules via internal API/pipeline calls
- Fallback behavior when model artifacts are missing
- Dynamic dropdown population from datasets
- Farmer-centric explainable output (advice + risk + summary lines)

---

## 7. System Models

### 7.1 Crop Recommendation Model

- Purpose: Recommend best-suited crop based on environmental and farm profile.
- Inputs: season, crop_type, water_source, climate_type, duration_type, farming_system, economic_use, area, fertilizer proxy, pesticide proxy.
- Output: Recommended crop label.
- Model family: Random Forest Classifier.

### 7.2 Crop Yield Prediction Model

- Purpose: Predict yield per hectare and estimated total production.
- Inputs: Year, rainfall, pesticides, temperature, state/area, crop item, farm area.
- Output: Yield (ton/ha and hg/ha), estimated production.
- Model family: Advanced boosted model bundle + legacy fallback model.

### 7.3 Crop Price Prediction Model

- Purpose: Forecast market modal price and selling advisory.
- Inputs: State, district, market, commodity, variety, arrival date, min/max price.
- Output: Predicted modal price, trend (increasing/stable/decreasing), best market, recommendation status.
- Model family: Random Forest regression pipeline with preprocessing.

### 7.4 Soil Health Model

- Purpose: Assess soil quality and generate nutrient/management plan.
- Inputs: Nitrogen, Phosphorus, Potassium, pH, moisture, organic carbon, EC.
- Output: Soil score, grade, alerts, suitable crops, improvement plan.
- Model family: Weighted rule-based decision engine.

### 7.5 Farmer Intelligence Fusion Model

- Purpose: Integrate crop + yield + price outputs for decision support.
- Inputs: Combined features from all modules.
- Output: Revenue estimate, profit estimate, final decision text, confidence-style fusion indicator.

---

## 8. Data Flow Model

### 8.1 End-to-End Flow

```text
User Input -> Validation and Normalization -> Model-Specific Preprocessing
-> Crop Prediction -> Yield Prediction -> Price Prediction -> Soil Analysis
-> Fusion and Decision Logic -> Dashboard Output
```

### 8.2 Functional Data Flow

- Input forms capture climate, soil, and market parameters.
- Backend transforms categorical/numeric fields for each model.
- Inference layer executes trained model pipelines.
- Post-processing computes indicators (trend, confidence, profitability, alerts).
- UI displays visual summaries and advisory content.

---

## 9. Diagram Descriptions (Text-Based for Drawing)

### 9.1 System Architecture Diagram (Draw This)

Draw 6 blocks vertically:

1. Farmer/User Interface
2. Flask Unified Backend
3. Module Layer (4 blocks side by side: Recommendation, Yield, Price, Soil)
4. Model Artifacts Layer (.pkl/.joblib + preprocessors)
5. Decision Fusion Engine
6. Dashboard & Recommendation Output

Connect with directional arrows from top to bottom. Add side arrows from each module into fusion engine.

### 9.2 DFD Level 0 (Context Diagram)

External Entity: Farmer/User

Process: Smart India Agri Intelligence System

Data Inflows:

- Farm and climate inputs
- Soil parameters
- Market details

Data Outflows:

- Recommended crop
- Predicted yield
- Predicted price and market advice
- Soil health report
- Final integrated decision

### 9.3 DFD Level 1 (Decomposed)

Processes:

P1: Input Collection and Validation
P2: Crop Recommendation Engine
P3: Yield Prediction Engine
P4: Price Forecasting Engine
P5: Soil Health Analysis Engine
P6: Fusion and Decision Support

Data Stores:

D1: Crop Datasets
D2: Yield Datasets
D3: Price Datasets
D4: Soil Threshold Rules
D5: Trained Model Files

### 9.4 Workflow Diagram

```text
Data Collection -> Data Preprocessing -> Feature Engineering -> Model Training
-> Model Evaluation -> Flask Integration -> API/Route Layer
-> User Dashboard -> Decision Support
```

---

## 10. Methodology

### 10.1 Step 1: Data Collection

- Collected module-specific datasets for crop recommendation, yield, and mandi price.
- Used structured CSV datasets with agronomic, climate, and market fields.

### 10.2 Step 2: Data Preprocessing

- Removed/handled null values.
- Standardized text labels (state, district, crop, market).
- Generated date-derived features for temporal price behavior.
- Encoded categorical features using OneHotEncoder/LabelEncoder.

### 10.3 Step 3: Model Training

- Trained Random Forest models for crop and price tasks.
- Used regressor/classifier pipelines for task-specific targets.
- Trained season-aware and advanced yield variants.

### 10.4 Step 4: Model Evaluation

- Evaluated with R2, RMSE, MAE for regression tasks.
- Classification metrics used where applicable: accuracy, precision, recall, F1.
- Compared multiple algorithms in workflow pages and benchmark views.

### 10.5 Step 5: Deployment

- Deployed as Flask web applications with templates and static assets.
- Built unified API endpoint for integrated multi-model prediction.
- Added dashboard-level interpretation for farmer-friendly usage.

---

## 11. Comparison: Existing vs Proposed System

| Feature           | Existing Baseline in This Project         | Proposed Unified Implementation                                |
| ----------------- | ----------------------------------------- | -------------------------------------------------------------- |
| App Structure     | Separate module apps in different folders | Root unified app orchestrates multiple modules                 |
| Prediction Flow   | Module-wise outputs only                  | Combined crop + yield + price + soil flow                      |
| User Journey      | Multiple entry points                     | Single farmer-intelligence path available                      |
| Fallback Handling | Module-specific behavior                  | Centralized safe fallback in unified pipeline                  |
| Profit Insight    | Not consistently exposed across modules   | Unified revenue and profit estimation in integrated output     |
| Data Mapping      | Module-level feature mapping              | Cross-module input normalization and routing                   |
| Explainability    | Per-module insights                       | Fused decision text with charts and model contribution context |
| Deployment View   | Individual module UIs                     | Unified gateway with links and API endpoints                   |

---

## 12. Appendix

### 12.1 Technologies Used

### Programming Language

- Python

### Frontend

- HTML
- CSS
- JavaScript
- Jinja2 templating

### Backend

- Flask

### ML/Data Libraries

- pandas
- numpy
- scikit-learn
- joblib

### Tools and Platform

- VS Code
- GitHub
- Gunicorn (deployment runtime)

### Datasets and Artifacts

- CSV-based agricultural datasets (crop, yield, price, soil inputs)
- Serialized model artifacts (.pkl, .joblib)

### 12.2 Notes for Viva/Presentation

- Emphasize integration advantage: one platform solving four farm decision problems.
- Explain farmer impact: better crop choice, better market timing, better soil management.
- Highlight technical depth: preprocessing pipelines, model benchmarking, and fallback-safe deployment.

---

## Ready-to-Export Instructions (PDF)

1. Open this Markdown file in VS Code.
2. Use Markdown Preview.
3. Export to PDF using a Markdown PDF extension or print-to-PDF.
4. Keep page size A4 and heading hierarchy intact.

---

## End of Report
