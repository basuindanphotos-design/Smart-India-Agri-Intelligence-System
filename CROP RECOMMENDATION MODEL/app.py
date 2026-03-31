from flask import Flask, render_template, request, redirect, url_for, session, send_file, make_response
from pathlib import Path
from datetime import datetime
from functools import lru_cache, wraps
from io import StringIO
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import threading

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LinearRegression
from sklearn.metrics import (
    mean_squared_error,
    r2_score,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
)
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeRegressor
from sklearn.neighbors import KNeighborsRegressor
from sklearn.svm import SVR

# Thread pool for timeout operations
_executor = ThreadPoolExecutor(max_workers=2)

app = Flask(__name__)
app.secret_key = "crop_prediction_secret"

# Timeout wrapper for expensive operations (max 5 seconds)
def with_timeout(timeout_sec=5):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                future = _executor.submit(func, *args, **kwargs)
                return future.result(timeout=timeout_sec)
            except TimeoutError:
                print(f"Timeout: {func.__name__} took longer than {timeout_sec}s, returning empty fallback")
                return kwargs.get("fallback", [])
            except Exception as e:
                print(f"Error in {func.__name__}: {e}")
                return kwargs.get("fallback", [])
        return wrapper
    return decorator

BASE_DIR = Path(__file__).resolve().parent
DATASET_CANDIDATES = [
    BASE_DIR / "crop_yield_enriched.csv",
    BASE_DIR / "crop_yield.csv",
]
PREFERRED_DATASET = BASE_DIR / "crop_yield_enriched.csv"

# Load trained models
crop_model = joblib.load(BASE_DIR / "crop_model.pkl")
yield_model = joblib.load(BASE_DIR / "yield_model.pkl")
encoder = joblib.load(BASE_DIR / "crop_encoder.pkl")

VALID_SEASONS = {"Rabi", "Kharif", "Zaid", "Whole Year"}
VALID_CROP_TYPES = {"Annual", "Perennial", "Biennial"}
VALID_WATER_SOURCES = {"Rainfed", "Irrigated"}
VALID_CLIMATE_TYPES = {"Tropical", "Subtropical", "Temperate"}
VALID_DURATION_TYPES = {"Short-Duration", "Medium-Duration", "Long-Duration"}
VALID_FARMING_SYSTEMS = {"Plantation", "Field", "Horticulture"}
VALID_ECONOMIC_USES = {"Cash", "Food", "Fodder"}


# ---------- Data Helpers ----------
def active_dataset_path() -> Path:
    for candidate in DATASET_CANDIDATES:
        if candidate.exists():
            return candidate
    return BASE_DIR / "crop_yield.csv"


def load_dataset() -> pd.DataFrame:
    path = active_dataset_path()
    df = pd.read_csv(path)
    if "season" in df.columns:
        df["season"] = df["season"].astype(str).str.strip()
    if "crop" in df.columns:
        df["crop"] = df["crop"].astype(str).str.strip()
    if "state" in df.columns:
        df["state"] = df["state"].astype(str).str.strip()
    return df


def dataset_timestamp(path: Path) -> str:
    if not path.exists():
        return "N/A"
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")


def normalized_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    defaults = {
        "crop_type": "Annual",
        "water_source": "Irrigated",
        "climate_type": "Subtropical",
        "duration_type": "Medium-Duration",
        "farming_system": "Field",
        "economic_use": "Food",
    }
    out = df.copy()
    for col, default in defaults.items():
        if col not in out.columns:
            out[col] = default
    if "season" not in out.columns:
        out["season"] = "Whole Year"
    return out


# ---------- Domain Logic ----------
def build_farmer_recommendations(crop_name, humidity, rainfall, temperature):
    recommendations = {}
    if rainfall < 2:
        recommendations["irrigation"] = (
            "Critical: Implement drip irrigation. Apply 20-25mm every 7-10 days and monitor soil moisture at 30cm depth."
        )
    elif rainfall < 5:
        recommendations["irrigation"] = (
            "Moderate: Combine rainfall with supplementary irrigation every 15-20 days. Maintain field drainage."
        )
    else:
        recommendations["irrigation"] = (
            "Adequate rainfall: irrigate only during dry spells and avoid waterlogging through proper drainage."
        )

    if humidity < 30:
        recommendations["soil"] = (
            "Dry climate: add 25-30 tons compost/hectare and mulch to reduce evaporation."
        )
    elif humidity < 50:
        recommendations["soil"] = (
            "Moderate humidity: maintain 2-3% organic matter and run periodic soil tests for nutrient balancing."
        )
    else:
        recommendations["soil"] = (
            "High humidity: prioritize soil aeration and drainage; monitor fungal disease pressure."
        )

    if temperature > 35:
        recommendations["temperature"] = (
            "Heat stress risk: increase irrigation frequency and schedule operations during cool hours."
        )
    elif temperature < 15:
        recommendations["temperature"] = (
            "Low temperature risk: use protective measures and cold-resilient varieties."
        )
    else:
        recommendations["temperature"] = (
            f"Temperature is favorable for {crop_name}. Maintain regular monitoring and standard practices."
        )

    recommendations["fertilizer"] = (
        f"For {crop_name}: apply balanced NPK in split doses (50% basal, 25% vegetative, 25% flowering)."
    )
    return recommendations


def build_insights(crop_name, predicted_yield, production, location, humidity):
    place = location if location else "your region"
    weather_line = (
        "Moisture conditions are favorable." if humidity >= 50 else "Low humidity detected. Apply moisture-conservation practices."
    )
    return [
        {"title": "Crop Recommendation", "content": f"{crop_name} is suitable for current conditions in {place}.", "icon": "*"},
        {"title": "Production Estimate", "content": f"Estimated production: {round(production, 2)} tons.", "icon": "*"},
        {"title": "Weather Assessment", "content": weather_line, "icon": "*"},
        {"title": "Yield Forecast", "content": f"Expected yield: {round(predicted_yield, 2)} tons/hectare.", "icon": "*"},
    ]


def estimate_crop_price_per_ton(economic_use, season, climate_type, predicted_yield):
    # Heuristic pricing in INR/ton derived from crop purpose and seasonal context.
    base_price = {
        "Cash": 42000.0,
        "Food": 24000.0,
        "Fodder": 16000.0,
    }.get(economic_use, 22000.0)

    season_factor = {
        "Rabi": 1.03,
        "Kharif": 0.98,
        "Zaid": 1.06,
        "Whole Year": 1.00,
    }.get(season, 1.00)

    climate_factor = {
        "Tropical": 1.02,
        "Subtropical": 1.00,
        "Temperate": 1.04,
    }.get(climate_type, 1.00)

    # Higher projected yield often softens market price; lower yield can tighten supply.
    if predicted_yield > 8:
        yield_factor = max(0.85, 1.0 - ((predicted_yield - 8.0) * 0.004))
    else:
        yield_factor = min(1.10, 1.0 + ((8.0 - predicted_yield) * 0.006))

    return round(base_price * season_factor * climate_factor * yield_factor, 2)


def build_chart_data(predicted_yield, production, temperature, humidity, rainfall,
                     area, season, water_source, climate_type, economic_use, provided_count):
    # Suitability scores computed dynamically from actual user inputs
    temp_score = max(0.0, min(100.0, 100.0 - abs(temperature - 27.0) * 2.5))
    humid_score = max(0.0, min(100.0, 100.0 - abs(humidity - 60.0) * 1.2))
    rain_score = min(100.0, rainfall * 12.0) if rainfall > 0 else 40.0
    primary = round(temp_score * 0.45 + humid_score * 0.35 + rain_score * 0.2, 1)
    alt_a = round(primary * 0.83, 1)
    alt_b = round(primary * 0.68, 1)

    # Factor radar — 6 dimensions from actual inputs
    season_score = {"Rabi": 85, "Kharif": 90, "Zaid": 70, "Whole Year": 80}.get(season, 75)
    water_score = 90 if water_source == "Irrigated" else 65
    climate_score = {"Tropical": 85, "Subtropical": 88, "Temperate": 78}.get(climate_type, 80)
    econ_score = {"Food": 80, "Cash": 90, "Fodder": 70}.get(economic_use, 75)

    # Yield projection at 5 area scales relative to user input
    proj_areas = [round(area * m, 2) for m in [0.5, 1.0, 2.0, 3.0, 5.0]]
    proj_yields = [round(predicted_yield * a, 2) for a in proj_areas]

    # Risk scores — fully derived from real inputs
    if water_source == "Rainfed":
        water_risk = max(0.0, min(100.0, max(0.0, 5.0 - rainfall) * 15.0))
    else:
        water_risk = max(0.0, min(100.0, max(0.0, 3.0 - rainfall) * 8.0))
    if temperature > 30:
        heat_risk = max(0.0, min(100.0, (temperature - 30.0) * 6.0))
    elif temperature < 15:
        heat_risk = max(0.0, min(100.0, (15.0 - temperature) * 5.0))
    else:
        heat_risk = 10.0
    disease_risk = max(0.0, min(100.0, (humidity - 60.0) * 2.0)) if humidity > 60 else 10.0
    risk_colors = [
        "#ef4444" if v > 60 else "#f59e0b" if v > 30 else "#22c55e"
        for v in [water_risk, heat_risk, disease_risk]
    ]

    return {
        "suitability": {
            "labels": ["Recommended Crop", "Alternative A", "Alternative B"],
            "values": [primary, alt_a, alt_b],
        },
        "environment": {
            "labels": ["Temperature", "Humidity", "Rainfall"],
            "values": [round(temperature, 2), round(humidity, 2), round(rainfall, 2)],
        },
        "production": {
            "labels": ["Yield / Hectare", "Total Production"],
            "values": [round(predicted_yield, 2), round(production, 2)],
        },
        "radar": {
            "labels": ["Temperature", "Humidity", "Season", "Water", "Climate", "Economic"],
            "values": [round(temp_score, 1), round(humid_score, 1), season_score, water_score, climate_score, econ_score],
        },
        "yield_projection": {
            "labels": [f"{a} ha" for a in proj_areas],
            "values": proj_yields,
        },
        "risk": {
            "labels": ["Water Stress", "Heat Stress", "Disease Pressure"],
            "values": [round(water_risk, 1), round(heat_risk, 1), round(disease_risk, 1)],
            "colors": risk_colors,
        },
        "confidence": round((provided_count / 12) * 100, 1),
    }


def build_crop_profile(crop_name, season, duration_type, water_source, economic_use, temperature, humidity):
    duration_map = {
        "Short-Duration": "60-90 days",
        "Medium-Duration": "90-120 days",
        "Long-Duration": "120+ days",
    }
    duration_text = duration_map.get(duration_type, "varies")
    water_text = "drip or sprinkler irrigation" if water_source == "Irrigated" else "rainwater harvesting and conservation"
    sow_temp = "18-22 C" if temperature < 22 else "25-32 C" if temperature > 30 else "22-28 C"
    if humidity < 40:
        humidity_note = "Apply mulching to conserve moisture in this low-humidity environment."
    elif humidity > 70:
        humidity_note = "Ensure good air circulation to reduce disease risk in this high-humidity environment."
    else:
        humidity_note = "Humidity is within a comfortable growing range."
    profit_context = {
        "Cash": f"{crop_name} has strong commercial value. Focus on quality grading and direct market linkage.",
        "Food": f"{crop_name} supports food security. Target local and regional procurement markets.",
        "Fodder": f"{crop_name} serves livestock supply chains. Coordinate with nearby farms for volume contracts.",
    }.get(economic_use, f"{crop_name} has broad market application.")
    return {
        "steps": [
            {"icon": "🌱", "title": "Sowing",
             "text": f"Optimal sowing temperature: {sow_temp}. Sow during {season} season for best germination of {crop_name}."},
            {"icon": "💧", "title": "Water Management",
             "text": f"Apply {water_text} suited to the {duration_text} growth cycle. {humidity_note}"},
            {"icon": "🌿", "title": "Crop Care",
             "text": f"Monitor for pest and disease throughout the {duration_type} growth window. Apply balanced nutrition at each growth stage."},
            {"icon": "🌾", "title": "Harvest",
             "text": f"Expected harvest window: {duration_text} from sowing. Time operations based on maturity indicators specific to {crop_name}."},
        ],
        "market": profit_context,
        "duration": duration_text,
    }


def build_textual_analysis(crop_name, temperature, humidity, rainfall, season, water_source,
                           climate_type, economic_use, predicted_yield, area, provided_count):
    risks = []
    if temperature > 35:
        risks.append("heat stress (temperature above 35 C)")
    if temperature < 12:
        risks.append("frost or cold shock risk")
    if humidity > 75 and water_source == "Irrigated":
        risks.append("elevated fungal disease pressure from high humidity")
    if rainfall < 1 and water_source == "Rainfed":
        risks.append("severe water deficit under rainfed conditions")
    risk_text = (
        f"Risk factors identified: {', '.join(risks)}. Implement targeted mitigation strategies to safeguard yield."
        if risks else
        f"No critical risk factors detected for {crop_name} under current input conditions. Maintain standard agronomic practices."
    )
    season_ctx = {
        "Rabi": "Rabi crops typically reach market March-May with stable demand.",
        "Kharif": "Kharif crops arrive in market October-December with competitive seasonal pricing.",
        "Zaid": "Zaid crops fill summer demand gaps and often command premium prices.",
        "Whole Year": "Year-round crops provide steady supply, reducing seasonal price volatility.",
    }.get(season, "Crop marketing windows vary by region.")
    scale = "large-scale" if area > 50 else "medium-scale" if area > 10 else "small-scale"
    market_text = (
        f"{crop_name} is a {economic_use.lower()} crop. {season_ctx} "
        f"With {area} hectares under cultivation, estimated gross yield is "
        f"{round(predicted_yield * area, 2)} tons, positioning this as a {scale} operation."
    )
    climate_text = {
        "Tropical": f"Tropical climate provides consistent warmth and moisture supporting robust growth of {crop_name}.",
        "Subtropical": f"Subtropical conditions offer a productive balance of warmth and seasonality ideal for {crop_name}.",
        "Temperate": f"Temperate climate creates precise seasonal windows that {crop_name} thrives in with well-timed field operations.",
    }.get(climate_type, f"Climate conditions have been factored into the AI recommendation for {crop_name}.")
    conf_pct = round((provided_count / 12) * 100)
    if conf_pct >= 80:
        conf_text = f"High confidence ({conf_pct}%): {provided_count} of 12 input factors provided, yielding a robust and precise recommendation."
    elif conf_pct >= 50:
        conf_text = f"Moderate confidence ({conf_pct}%): {provided_count} of 12 factors provided. Adding more details will improve accuracy."
    else:
        conf_text = f"Limited confidence ({conf_pct}%): only {provided_count} factor(s) provided. More inputs will significantly sharpen this recommendation."
    return {
        "risk": risk_text,
        "market": market_text,
        "climate": climate_text,
        "confidence": conf_text,
    }


def build_pictorial_cards(crop_name, temperature, humidity, rainfall, water_source,
                          climate_type, duration_type, economic_use, predicted_yield, area, provided_count):
    water_level = "High" if (water_source == "Irrigated" and rainfall < 2) else "Moderate" if rainfall < 5 else "Low"
    water_icon = "💧💧💧" if water_level == "High" else "💧💧" if water_level == "Moderate" else "💧"
    climate_ok = (
        (climate_type == "Tropical" and temperature > 22) or
        (climate_type == "Subtropical" and 12 < temperature < 38) or
        (climate_type == "Temperate" and temperature < 28)
    )
    climate_label = "Excellent Match" if climate_ok else "Partial Match"
    duration_label = {
        "Short-Duration": "60-90 days",
        "Medium-Duration": "90-120 days",
        "Long-Duration": "120+ days",
    }.get(duration_type, "Varies")
    yield_rating = "High" if predicted_yield > 20 else "Moderate" if predicted_yield > 8 else "Standard"
    yield_icon = "📈📈📈" if yield_rating == "High" else "📈📈" if yield_rating == "Moderate" else "📈"
    econ_icon = {"Cash": "💰", "Food": "🌾", "Fodder": "🐄"}.get(economic_use, "🌱")
    conf = round((provided_count / 12) * 100)
    return [
        {"icon": water_icon, "title": "Water Need", "value": water_level,
         "desc": f"{water_source} | {rainfall} mm rainfall"},
        {"icon": "🌡", "title": "Climate Match", "value": climate_label,
         "desc": f"{climate_type} | {temperature} C"},
        {"icon": "⏱", "title": "Harvest Timeline", "value": duration_label,
         "desc": f"{duration_type} lifecycle"},
        {"icon": yield_icon, "title": "Yield Rating", "value": yield_rating,
         "desc": f"{round(predicted_yield, 2)} tons/ha predicted"},
        {"icon": econ_icon, "title": "Crop Category", "value": economic_use,
         "desc": f"Economic class for {crop_name}"},
        {"icon": "🎯", "title": "Prediction Confidence", "value": f"{conf}%",
         "desc": f"{provided_count} of 12 factors provided"},
    ]


def build_global_dashboard_payload(df: pd.DataFrame):
    records = int(len(df))
    crops = int(df["crop"].nunique()) if "crop" in df.columns else 0
    seasons = int(df["season"].nunique()) if "season" in df.columns else 0
    climate_types = int(df["climate_type"].nunique()) if "climate_type" in df.columns else 0

    profile_combinations = 0
    profile_cols = [
        c
        for c in ["crop_type", "water_source", "climate_type", "duration_type", "farming_system", "economic_use"]
        if c in df.columns
    ]
    if profile_cols:
        profile_combinations = int(df[profile_cols].drop_duplicates().shape[0])

    season_distribution = []
    if "season" in df.columns:
        season_distribution = (
            df["season"].value_counts().rename_axis("season").reset_index(name="count").to_dict("records")
        )

    crop_type_yield = []
    if {"crop_type", "yield"}.issubset(df.columns):
        crop_type_yield = (
            df.groupby("crop_type", as_index=False)["yield"].mean().sort_values("yield", ascending=False).to_dict("records")
        )

    top_crop_yield = []
    if {"crop", "yield"}.issubset(df.columns):
        top_crop_yield = (
            df.groupby("crop", as_index=False)["yield"].mean().sort_values("yield", ascending=False).head(10).to_dict("records")
        )

    economic_use_share = []
    if "economic_use" in df.columns:
        economic_use_share = (
            df["economic_use"].value_counts().rename_axis("economic_use").reset_index(name="count").to_dict("records")
        )

    top_area_crops = []
    if {"crop", "area"}.issubset(df.columns):
        top_area_crops = (
            df.groupby("crop", as_index=False)["area"].mean().sort_values("area", ascending=False).head(10).to_dict("records")
        )

    yield_spread = []
    if {"crop", "yield"}.issubset(df.columns):
        spread_df = df.groupby("crop", as_index=False)["yield"].agg(["min", "max"]).reset_index()
        spread_df["spread"] = spread_df["max"] - spread_df["min"]
        spread_df = spread_df.sort_values("spread", ascending=False).head(10)
        yield_spread = spread_df[["crop", "spread"]].to_dict("records")

    coverage_rows = []
    if {"crop", "yield", "area"}.issubset(df.columns):
        coverage = (
            df.groupby("crop", as_index=False)
            .agg(records=("crop", "count"), avg_yield=("yield", "mean"), avg_area=("area", "mean"))
            .sort_values("records", ascending=False)
        )
        coverage["avg_yield"] = coverage["avg_yield"].round(3)
        coverage["avg_area"] = coverage["avg_area"].round(2)
        coverage_rows = coverage.head(30).to_dict("records")

    return {
        "records": records,
        "crops": crops,
        "seasons": seasons,
        "climate_types": climate_types,
        "profile_combinations": profile_combinations,
        "season_distribution": season_distribution,
        "crop_type_yield": crop_type_yield,
        "top_crop_yield": top_crop_yield,
        "economic_use_share": economic_use_share,
        "top_area_crops": top_area_crops,
        "yield_spread": yield_spread,
        "coverage_rows": coverage_rows,
    }


@lru_cache(maxsize=4)
def compute_model_metrics(dataset_path: str, mtime: float):
    df = load_dataset()
    df = normalized_feature_frame(df)

    required = [
        "season", "crop_type", "water_source", "climate_type", "duration_type",
        "farming_system", "economic_use", "area", "fertilizer", "pesticide", "crop", "yield"
    ]
    missing = [col for col in required if col not in df.columns]
    if missing:
        return []

    model_df = df.dropna(subset=required).copy()
    model_df = model_df[model_df["crop"].isin(set(encoder.classes_))]
    if model_df.empty:
        return []

    model_df["crop_encoded"] = encoder.transform(model_df["crop"])

    feature_cols = [
        "season", "crop_type", "water_source", "climate_type", "duration_type",
        "farming_system", "economic_use", "area", "fertilizer", "pesticide", "crop_encoded"
    ]
    X_raw = model_df[feature_cols]
    y = model_df["yield"]

    X = pd.get_dummies(X_raw, drop_first=False)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    models = {
        "Random Forest Regressor": RandomForestRegressor(n_estimators=240, random_state=42),
        "Gradient Boosting": GradientBoostingRegressor(random_state=42),
        "Linear Regression": LinearRegression(),
        "Support Vector Regressor": SVR(kernel="rbf", C=50, gamma="scale"),
    }

    rows = []
    for name, model in models.items():
        model.fit(X_train, y_train)
        train_pred = model.predict(X_train)
        test_pred = model.predict(X_test)
        rows.append({
            "model": name,
            "train_r2": round(r2_score(y_train, train_pred), 4),
            "test_r2": round(r2_score(y_test, test_pred), 4),
            "train_rmse": round(float(np.sqrt(mean_squared_error(y_train, train_pred))), 4),
            "test_rmse": round(float(np.sqrt(mean_squared_error(y_test, test_pred))), 4),
        })

    rows.sort(key=lambda x: x["test_r2"], reverse=True)
    return rows


WORKFLOW_STEPS = [
    {
        "id": "dataset",
        "title": "Dataset Collection",
        "description": "Inspect source data, schema, samples, and target variable for the recommendation model.",
        "icon": "fa-database",
        "endpoint": "workflow_dataset",
    },
    {
        "id": "preprocessing",
        "title": "Data Preprocessing",
        "description": "Understand cleaning, missing-value handling, encoding strategy, and pipeline preparation.",
        "icon": "fa-filter",
        "endpoint": "workflow_preprocessing",
    },
    {
        "id": "eda",
        "title": "Exploratory Data Analysis",
        "description": "Visualize crop patterns, distributions, and feature relationships from the active dataset.",
        "icon": "fa-chart-column",
        "endpoint": "workflow_eda",
    },
    {
        "id": "feature_engineering",
        "title": "Feature Engineering",
        "description": "Review engineered agronomic attributes and feature importance used in model learning.",
        "icon": "fa-gears",
        "endpoint": "workflow_feature_engineering",
    },
    {
        "id": "model_training",
        "title": "Model Training",
        "description": "Compare training performance of multiple ML algorithms on recommendation data.",
        "icon": "fa-brain",
        "endpoint": "workflow_model_training",
    },
    {
        "id": "model_evaluation",
        "title": "Model Evaluation",
        "description": "Track evaluation metrics and confusion matrix to validate recommendation quality.",
        "icon": "fa-list-check",
        "endpoint": "workflow_model_evaluation",
    },
    {
        "id": "prediction_system",
        "title": "Crop Recommendation Prediction",
        "description": "See how user inputs travel through preprocessing, model inference, and output generation.",
        "icon": "fa-seedling",
        "endpoint": "workflow_prediction_system",
    },
    {
        "id": "deployment",
        "title": "Deployment & Web Application",
        "description": "Understand Flask integration, route architecture, and production-facing workflow delivery.",
        "icon": "fa-server",
        "endpoint": "workflow_deployment",
    },
]


def build_workflow_nav(current_id):
    ids = [s["id"] for s in WORKFLOW_STEPS]
    index = ids.index(current_id)
    prev_step = WORKFLOW_STEPS[index - 1] if index > 0 else None
    next_step = WORKFLOW_STEPS[index + 1] if index < len(WORKFLOW_STEPS) - 1 else None
    return {
        "steps": WORKFLOW_STEPS,
        "step_number": index + 1,
        "step_total": len(WORKFLOW_STEPS),
        "current_id": current_id,
        "prev_step": prev_step,
        "next_step": next_step,
    }


def read_code_excerpt(file_name, max_lines=80):
    path = BASE_DIR / file_name
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    return "\n".join(lines[:max_lines])


@lru_cache(maxsize=4)
def compute_feature_importance(dataset_path: str, mtime: float):
    df = load_dataset()
    required = [
        "season",
        "crop_type",
        "water_source",
        "climate_type",
        "duration_type",
        "farming_system",
        "economic_use",
        "area",
        "fertilizer",
        "pesticide",
        "yield",
    ]
    if not set(required).issubset(df.columns):
        return []

    base = df.dropna(subset=required).copy()
    if base.empty:
        return []

    X = pd.get_dummies(base[required[:-1]], drop_first=False)
    y = base["yield"]
    # Reduced from 220 to 50 estimators for faster computation
    model = RandomForestRegressor(n_estimators=50, random_state=42, n_jobs=-1)
    model.fit(X, y)
    importance = pd.DataFrame(
        {
            "feature": X.columns,
            "importance": model.feature_importances_,
        }
    ).sort_values("importance", ascending=False)
    return importance.head(15).to_dict("records")


@lru_cache(maxsize=4)
def compute_training_benchmark(dataset_path: str, mtime: float):
    df = load_dataset()
    required = [
        "season",
        "crop_type",
        "water_source",
        "climate_type",
        "duration_type",
        "farming_system",
        "economic_use",
        "area",
        "fertilizer",
        "pesticide",
        "yield",
    ]
    if not set(required).issubset(df.columns):
        return []

    base = df.dropna(subset=required).copy()
    if base.empty:
        return []

    X = pd.get_dummies(base[required[:-1]], drop_first=False)
    y = base["yield"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Reduced estimators for faster training
    models = {
        "Random Forest": RandomForestRegressor(n_estimators=50, random_state=42, n_jobs=-1),
        "Decision Tree": DecisionTreeRegressor(random_state=42),
        "Linear Regression": LinearRegression(),
    }

    rows = []
    for name, model in models.items():
        model.fit(X_train, y_train)
        pred = model.predict(X_test)
        rmse = float(np.sqrt(mean_squared_error(y_test, pred)))
        rows.append(
            {
                "model": name,
                "r2": round(float(r2_score(y_test, pred)), 4),
                "rmse": round(rmse, 4),
            }
        )
    rows.sort(key=lambda x: x["r2"], reverse=True)
    return rows


@lru_cache(maxsize=4)
def compute_workflow_evaluation(dataset_path: str, mtime: float):
    df = load_dataset()
    required = [
        "season",
        "crop_type",
        "water_source",
        "climate_type",
        "duration_type",
        "farming_system",
        "economic_use",
        "area",
        "fertilizer",
        "pesticide",
        "crop",
    ]
    if not set(required).issubset(df.columns):
        return {"metrics": {}, "labels": [], "matrix": []}

    base = df.dropna(subset=required).copy()
    if base.empty:
        return {"metrics": {}, "labels": [], "matrix": []}

    y_encoder = joblib.load(BASE_DIR / "crop_encoder.pkl")
    base = base[base["crop"].isin(set(y_encoder.classes_))]
    if base.empty:
        return {"metrics": {}, "labels": [], "matrix": []}

    y = y_encoder.transform(base["crop"])
    X = pd.get_dummies(base[required[:-1]], drop_first=False)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Reduced from 240 to 50 estimators for faster computation, added n_jobs for parallelization
    clf = RandomForestClassifier(n_estimators=50, random_state=42, n_jobs=-1)
    clf.fit(X_train, y_train)
    pred = clf.predict(X_test)

    metrics = {
        "accuracy": round(float(accuracy_score(y_test, pred)), 4),
        "precision": round(float(precision_score(y_test, pred, average="weighted", zero_division=0)), 4),
        "recall": round(float(recall_score(y_test, pred, average="weighted", zero_division=0)), 4),
        "f1": round(float(f1_score(y_test, pred, average="weighted", zero_division=0)), 4),
    }

    top_encoded = pd.Series(y_test).value_counts().head(8).index.tolist()
    cm = confusion_matrix(y_test, pred, labels=top_encoded)
    labels = [str(y_encoder.inverse_transform([i])[0]) for i in top_encoded]

    return {
        "metrics": metrics,
        "labels": labels,
        "matrix": cm.tolist(),
    }


# ---------- Core Routes ----------
@app.route("/")
def home():
    dataset = load_dataset()
    payload = build_global_dashboard_payload(dataset)
    return render_template(
        "home.html",
        stats=payload,
        dataset_path=active_dataset_path().name,
        dataset_updated=dataset_timestamp(active_dataset_path()),
    )


@app.route("/crop-predictor", methods=["GET", "POST"])
def crop_predictor():
    history = session.get("prediction_history", [])

    if request.method == "GET":
        return render_template("crop_predictor.html", history=history)

    def parse_optional_float(field_name, default_value):
        raw = (request.form.get(field_name, "") or "").strip()
        if raw == "":
            return default_value, False
        try:
            return float(raw), True
        except ValueError:
            return default_value, False

    def parse_optional_choice(field_name, valid_values, default_value):
        raw = (request.form.get(field_name, "") or "").strip()
        if raw in valid_values:
            return raw, True
        return default_value, False

    # Defaults allow prediction even when only some factors are provided.
    temperature, has_temperature = parse_optional_float("temperature", 28.0)
    humidity, has_humidity = parse_optional_float("humidity", 60.0)
    area, has_area = parse_optional_float("area", 1.0)
    rainfall, has_rainfall = parse_optional_float("rainfall", 0.0)

    season, has_season = parse_optional_choice("season", VALID_SEASONS, "Kharif")
    crop_type, has_crop_type = parse_optional_choice("crop_type", VALID_CROP_TYPES, "Annual")
    water_source, has_water_source = parse_optional_choice("water_source", VALID_WATER_SOURCES, "Irrigated")
    climate_type, has_climate_type = parse_optional_choice("climate_type", VALID_CLIMATE_TYPES, "Subtropical")
    duration_type, has_duration_type = parse_optional_choice("duration_type", VALID_DURATION_TYPES, "Medium-Duration")
    farming_system, has_farming_system = parse_optional_choice("farming_system", VALID_FARMING_SYSTEMS, "Field")
    economic_use, has_economic_use = parse_optional_choice("economic_use", VALID_ECONOMIC_USES, "Food")

    location = (request.form.get("location", "") or "").strip()
    has_location = bool(location)

    provided_count = sum(
        [
            has_temperature,
            has_humidity,
            has_area,
            has_rainfall,
            has_season,
            has_crop_type,
            has_water_source,
            has_climate_type,
            has_duration_type,
            has_farming_system,
            has_economic_use,
            has_location,
        ]
    )

    if provided_count == 0:
        return render_template(
            "crop_predictor.html",
            error="Please provide at least one factor. Single factor, combination, or all factors are supported.",
            history=history,
        )

    fertilizer = temperature * 0.4
    pesticide = humidity * 0.3

    feature_row = {
        "season": season,
        "crop_type": crop_type,
        "water_source": water_source,
        "climate_type": climate_type,
        "duration_type": duration_type,
        "farming_system": farming_system,
        "economic_use": economic_use,
        "area": area,
        "fertilizer": fertilizer,
        "pesticide": pesticide,
    }
    crop_input = pd.DataFrame([feature_row])

    crop_encoded = int(crop_model.predict(crop_input)[0])
    crop_name = encoder.inverse_transform([crop_encoded])[0]

    yield_input = crop_input.copy()
    yield_input["crop_encoded"] = crop_encoded
    predicted_yield = float(yield_model.predict(yield_input)[0])
    production = predicted_yield * area
    price_per_ton = estimate_crop_price_per_ton(
        economic_use, season, climate_type, predicted_yield
    )
    estimated_revenue = production * price_per_ton

    insights = build_insights(crop_name, predicted_yield, production, location, humidity)
    recommendations = build_farmer_recommendations(crop_name, humidity, rainfall, temperature)
    charts = build_chart_data(
        predicted_yield, production, temperature, humidity, rainfall,
        area, season, water_source, climate_type, economic_use, provided_count,
    )
    crop_profile = build_crop_profile(
        crop_name, season, duration_type, water_source, economic_use, temperature, humidity
    )
    textual = build_textual_analysis(
        crop_name, temperature, humidity, rainfall, season, water_source,
        climate_type, economic_use, predicted_yield, area, provided_count,
    )
    pictorial = build_pictorial_cards(
        crop_name, temperature, humidity, rainfall, water_source,
        climate_type, duration_type, economic_use, predicted_yield, area, provided_count,
    )

    result_payload = {
        "crop": crop_name,
        "yield": round(predicted_yield, 2),
        "production": round(production, 2),
        "price_per_ton": round(price_per_ton, 2),
        "estimated_revenue": round(estimated_revenue, 2),
        "season": season,
        "crop_type": crop_type,
        "water_source": water_source,
        "climate_type": climate_type,
        "duration_type": duration_type,
        "farming_system": farming_system,
        "economic_use": economic_use,
        "temperature": round(temperature, 2),
        "humidity": round(humidity, 2),
        "rainfall": round(rainfall, 2),
        "location": location if location else "Not provided",
        "insights": insights,
        "recommendations": recommendations,
        "charts": charts,
        "input_row": {
            "temperature": temperature,
            "humidity": humidity,
            "season": season,
            "crop_type": crop_type,
            "water_source": water_source,
            "climate_type": climate_type,
            "duration_type": duration_type,
            "farming_system": farming_system,
            "economic_use": economic_use,
            "area": area,
            "rainfall": rainfall,
            "location": location,
        },
        "provided_factors": provided_count,
        "crop_profile": crop_profile,
        "textual": textual,
        "pictorial": pictorial,
    }
    session["result"] = result_payload

    history_entry = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "crop": result_payload["crop"],
        "season": result_payload["season"],
        "temperature": result_payload["temperature"],
        "rainfall": result_payload["rainfall"],
        "farm_area": round(area, 2),
        "yield": result_payload["yield"],
        "production": result_payload["production"],
        "price_per_ton": result_payload["price_per_ton"],
        "location": result_payload["location"],
    }
    history = [history_entry] + history
    session["prediction_history"] = history[:10]
    session.modified = True

    # Attach a cache-busting query value so each prediction opens a fresh result URL.
    return redirect(url_for("prediction_result", v=int(datetime.now().timestamp() * 1000)))


@app.route("/prediction-result")
def prediction_result():
    result = session.get("result")
    if not result:
        return redirect(url_for("crop_predictor"))
    response = make_response(render_template("prediction_result.html", result=result))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.route("/prediction-history/export")
def prediction_history_export():
    history = session.get("prediction_history", [])
    export_rows = []
    for item in history:
        export_rows.append(
            {
                "time": item.get("time", ""),
                "crop": item.get("crop", ""),
                "location": item.get("location", ""),
                "season": item.get("season", ""),
                "temperature": item.get("temperature", ""),
                "rainfall": item.get("rainfall", ""),
                "farm_area": item.get("farm_area", ""),
                "yield": item.get("yield", ""),
                "production": item.get("production", ""),
                "price_per_ton": item.get("price_per_ton", ""),
            }
        )

    csv_data = pd.DataFrame(export_rows).to_csv(index=False)
    response = make_response(csv_data)
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=prediction_history.csv"
    return response


@app.route("/prediction-history/import", methods=["POST"])
def prediction_history_import():
    upload = request.files.get("history_file")
    if not upload or upload.filename == "":
        return redirect(url_for("crop_predictor"))

    try:
        df = pd.read_csv(upload)
    except Exception:
        return redirect(url_for("crop_predictor"))

    imported = []
    for _, row in df.iterrows():
        imported.append(
            {
                "time": str(row.get("time", "")),
                "crop": str(row.get("crop", "")),
                "location": str(row.get("location", "")),
                "season": str(row.get("season", "")),
                "temperature": row.get("temperature", "-"),
                "rainfall": row.get("rainfall", "-"),
                "farm_area": row.get("farm_area", "-"),
                "yield": row.get("yield", "-"),
                "production": row.get("production", "-"),
                "price_per_ton": row.get("price_per_ton", "-"),
            }
        )

    existing = session.get("prediction_history", [])
    session["prediction_history"] = (imported + existing)[:10]
    session.modified = True
    return redirect(url_for("crop_predictor"))


@app.route("/prediction-history/clear", methods=["POST"])
def prediction_history_clear():
    session["prediction_history"] = []
    session.modified = True
    return redirect(url_for("crop_predictor"))


@app.route("/project-workflow")
def project_workflow():
    nav = build_workflow_nav("dataset")
    return render_template("project_workflow.html", workflow=nav)


@app.route("/project-workflow/dataset")
def workflow_dataset():
    df = load_dataset()
    path = active_dataset_path()
    nav = build_workflow_nav("dataset")

    target_variable = "crop" if "crop" in df.columns else "N/A"
    preview_columns = [
        c
        for c in [
            "crop",
            "season",
            "area",
            "fertilizer",
            "pesticide",
            "yield",
            "crop_type",
            "water_source",
            "climate_type",
        ]
        if c in df.columns
    ]
    preview_rows = df[preview_columns].head(12).to_dict("records") if preview_columns else []

    expected_agri_features = [
        "nitrogen",
        "phosphorus",
        "potassium",
        "temperature",
        "humidity",
        "rainfall",
        "ph",
    ]
    lower_columns = {c.lower(): c for c in df.columns}
    available_expected = [lower_columns[x] for x in expected_agri_features if x in lower_columns]
    missing_expected = [x for x in expected_agri_features if x not in lower_columns]

    crop_distribution = []
    if "crop" in df.columns:
        crop_distribution = (
            df["crop"].value_counts().head(12).rename_axis("crop").reset_index(name="count").to_dict("records")
        )

    return render_template(
        "dataset.html",
        workflow=nav,
        dataset_file=path.name,
        updated_at=dataset_timestamp(path),
        sample_count=int(len(df)),
        feature_count=int(len(df.columns)),
        target_variable=target_variable,
        columns=preview_columns,
        preview_rows=preview_rows,
        available_expected=available_expected,
        missing_expected=missing_expected,
        crop_distribution=crop_distribution,
    )


@app.route("/project-workflow/preprocessing")
def workflow_preprocessing():
    df = load_dataset()
    nav = build_workflow_nav("preprocessing")
    before = df.isna().sum().reset_index()
    before.columns = ["column", "null_values"]

    processed = df.copy()
    for col in processed.columns:
        if processed[col].dtype.kind in "biufc":
            processed[col] = processed[col].fillna(processed[col].median())
        else:
            mode = processed[col].mode(dropna=True)
            processed[col] = processed[col].fillna(mode.iloc[0] if not mode.empty else "Unknown")

    after = processed.isna().sum().reset_index()
    after.columns = ["column", "null_values"]

    code_excerpt = read_code_excerpt("train_model.py", max_lines=120)

    return render_template(
        "preprocessing.html",
        workflow=nav,
        before_rows=before.to_dict("records"),
        after_rows=after.to_dict("records"),
        preview_rows=processed.head(10).to_dict("records"),
        columns=list(processed.columns),
        code_excerpt=code_excerpt,
        updated_at=dataset_timestamp(active_dataset_path()),
    )


@app.route("/project-workflow/eda")
def workflow_eda():
    df = load_dataset()
    nav = build_workflow_nav("eda")

    crop_dist = (
        df["crop"].value_counts().head(12).rename_axis("crop").reset_index(name="count").to_dict("records")
        if "crop" in df.columns
        else []
    )
    season_yield = (
        df.groupby("season", as_index=False)["yield"].mean().sort_values("yield", ascending=False).to_dict("records")
        if {"season", "yield"}.issubset(df.columns)
        else []
    )

    sample = df.head(500)
    temp_vs_crop = []
    rain_vs_crop = []
    npk_like = []
    if {"crop", "fertilizer"}.issubset(sample.columns):
        temp_vs_crop = sample[["crop", "fertilizer"]].rename(columns={"fertilizer": "value"}).to_dict("records")
    if {"crop", "pesticide"}.issubset(sample.columns):
        rain_vs_crop = sample[["crop", "pesticide"]].rename(columns={"pesticide": "value"}).to_dict("records")
    if {"crop", "area", "fertilizer", "pesticide"}.issubset(sample.columns):
        npk_like = sample[["crop", "area", "fertilizer", "pesticide"]].to_dict("records")

    return render_template(
        "eda.html",
        workflow=nav,
        crop_dist=crop_dist,
        season_yield=season_yield,
        temp_vs_crop=temp_vs_crop,
        rain_vs_crop=rain_vs_crop,
        npk_like=npk_like,
        updated_at=dataset_timestamp(active_dataset_path()),
    )


@app.route("/project-workflow/feature-engineering")
def workflow_feature_engineering():
    path = active_dataset_path()
    nav = build_workflow_nav("feature_engineering")
    
    # Compute feature importance with error handling to prevent timeout
    importance = []
    try:
        importance = compute_feature_importance(str(path), path.stat().st_mtime if path.exists() else 0)
    except Exception as e:
        print(f"Error computing feature importance: {e}")
        importance = []

    # Compute engineered summary with error handling
    engineered_summary = []
    try:
        df = load_dataset()
        engineered_cols = [
            c
            for c in ["crop_type", "water_source", "climate_type", "duration_type", "farming_system", "economic_use"]
            if c in df.columns
        ]
        for col in engineered_cols:
            engineered_summary.append(
                {"feature": col, "unique_values": int(df[col].nunique()), "examples": ", ".join(df[col].dropna().astype(str).unique()[:4])}
            )
    except Exception as e:
        print(f"Error computing engineered summary: {e}")
        engineered_summary = []

    return render_template(
        "feature_engineering.html",
        workflow=nav,
        importance=importance,
        engineered_summary=engineered_summary,
        updated_at=dataset_timestamp(path),
    )


@app.route("/project-workflow/model-training")
def workflow_model_training():
    path = active_dataset_path()
    nav = build_workflow_nav("model_training")
    
    # Compute training benchmarks with error handling to prevent timeout
    benchmarks = []
    try:
        benchmarks = compute_training_benchmark(str(path), path.stat().st_mtime if path.exists() else 0)
    except Exception as e:
        print(f"Error computing training benchmarks: {e}")
        benchmarks = []
    
    # Read season model script with error handling
    season_model_script = ""
    try:
        season_model_script = read_code_excerpt("train_season_model.py", max_lines=80)
    except Exception as e:
        print(f"Error reading season model script: {e}")
        season_model_script = ""

    return render_template(
        "model_training.html",
        workflow=nav,
        benchmarks=benchmarks,
        season_model_script=season_model_script,
        updated_at=dataset_timestamp(path),
    )


@app.route("/project-workflow/model-evaluation")
def workflow_model_evaluation():
    path = active_dataset_path()
    nav = build_workflow_nav("model_evaluation")
    
    # Compute evaluation metrics with error handling to prevent timeout
    eval_payload = {"metrics": {}, "labels": [], "matrix": []}
    try:
        eval_payload = compute_workflow_evaluation(str(path), path.stat().st_mtime if path.exists() else 0)
    except Exception as e:
        print(f"Error computing workflow evaluation: {e}")
        eval_payload = {"metrics": {}, "labels": [], "matrix": []}
    
    # Get best model with error handling
    best_model = "Random Forest"
    try:
        best_model_rows = compute_training_benchmark(str(path), path.stat().st_mtime if path.exists() else 0)
        best_model = best_model_rows[0]["model"] if best_model_rows else "Random Forest"
    except Exception as e:
        print(f"Error determining best model: {e}")
        best_model = "Random Forest"

    return render_template(
        "model_evaluation.html",
        workflow=nav,
        metrics=eval_payload.get("metrics", {}),
        cm_labels=eval_payload.get("labels", []),
        cm_matrix=eval_payload.get("matrix", []),
        best_model=best_model,
        updated_at=dataset_timestamp(path),
    )


@app.route("/project-workflow/prediction-system")
def workflow_prediction_system():
    nav = build_workflow_nav("prediction_system")
    result = session.get("result", {})
    has_result = bool(result)

    return render_template(
        "prediction_system.html",
        workflow=nav,
        has_result=has_result,
        result=result,
        updated_at=dataset_timestamp(active_dataset_path()),
    )


@app.route("/project-workflow/deployment")
def workflow_deployment():
    nav = build_workflow_nav("deployment")
    routes = []
    for rule in app.url_map.iter_rules():
        if "static" in rule.rule:
            continue
        routes.append(
            {
                "path": rule.rule,
                "methods": ", ".join(sorted(m for m in rule.methods if m not in {"HEAD", "OPTIONS"})),
            }
        )
    routes = sorted(routes, key=lambda x: x["path"])

    return render_template(
        "deployment.html",
        workflow=nav,
        routes=routes,
    )


@app.route("/dashboard")
def dashboard():
    df = load_dataset()
    payload = build_global_dashboard_payload(df)
    return render_template(
        "dashboard_analytics.html",
        payload=payload,
        updated_at=dataset_timestamp(active_dataset_path()),
        dataset_file=active_dataset_path().name,
    )


# ---------- Dataset / Pipeline Pages ----------
@app.route("/dataset")
def dataset_explorer():
    df = load_dataset()

    query = request.args.get("q", "").strip().lower()
    sort_by = request.args.get("sort", "yield")
    order = request.args.get("order", "desc")
    page = max(int(request.args.get("page", 1)), 1)
    page_size = 20

    filtered = df.copy()
    if query:
        search_cols = [col for col in ["state", "crop", "season"] if col in filtered.columns]
        if search_cols:
            mask = pd.Series(False, index=filtered.index)
            for col in search_cols:
                mask = mask | filtered[col].astype(str).str.lower().str.contains(query, na=False)
            filtered = filtered[mask]

    if sort_by in filtered.columns:
        filtered = filtered.sort_values(sort_by, ascending=(order == "asc"))

    total_records = len(filtered)
    total_pages = max((total_records + page_size - 1) // page_size, 1)
    page = min(page, total_pages)
    start = (page - 1) * page_size
    end = start + page_size

    table_df = filtered.iloc[start:end].copy()
    records = table_df.to_dict("records")

    return render_template(
        "dataset_explorer.html",
        records=records,
        columns=list(table_df.columns),
        query=query,
        sort_by=sort_by,
        order=order,
        page=page,
        total_pages=total_pages,
        total_records=total_records,
        dataset_file=active_dataset_path().name,
        updated_at=dataset_timestamp(active_dataset_path()),
    )


@app.route("/dataset/upload", methods=["POST"])
def dataset_upload():
    upload = request.files.get("dataset_file")
    mode = request.form.get("mode", "append")

    if not upload or upload.filename == "":
        return redirect(url_for("dataset_explorer"))

    incoming = pd.read_csv(upload)
    current = load_dataset()

    if mode == "replace":
        target = incoming
    else:
        shared_cols = [c for c in current.columns if c in incoming.columns]
        if not shared_cols:
            return redirect(url_for("dataset_explorer"))
        target = pd.concat([current[shared_cols], incoming[shared_cols]], ignore_index=True)

    target.to_csv(PREFERRED_DATASET, index=False)
    compute_model_metrics.cache_clear()
    return redirect(url_for("dataset_explorer"))


@app.route("/dataset/export")
def dataset_export():
    return send_file(active_dataset_path(), as_attachment=True)


@app.route("/basic-info")
def basic_info():
    df = load_dataset()
    head_rows = df.head(10).to_dict("records")
    describe_rows = df.describe(include="all").fillna("").to_dict("index")
    info_rows = [{"column": c, "non_null": int(df[c].notna().sum()), "dtype": str(df[c].dtype)} for c in df.columns]

    return render_template(
        "basic_info.html",
        head_rows=head_rows,
        columns=list(df.columns),
        describe_rows=describe_rows,
        describe_columns=list(df.describe(include="all").fillna("").columns),
        info_rows=info_rows,
        updated_at=dataset_timestamp(active_dataset_path()),
    )


@app.route("/preprocessing")
def preprocessing():
    return redirect(url_for("workflow_preprocessing"))


@app.route("/eda")
def eda():
    return redirect(url_for("workflow_eda"))


@app.route("/eda-2")
def eda_2():
    df = load_dataset()

    scatter_x = df["area"].head(300).tolist() if "area" in df.columns else []
    scatter_y = df["yield"].head(300).tolist() if "yield" in df.columns else []

    monthly = []
    if "year" in df.columns and "yield" in df.columns:
        monthly_df = df.groupby("year", as_index=False)["yield"].mean().sort_values("year")
        monthly = monthly_df.values.tolist()

    return render_template(
        "eda2.html",
        scatter_x=scatter_x,
        scatter_y=scatter_y,
        monthly=monthly,
        updated_at=dataset_timestamp(active_dataset_path()),
    )


@app.route("/model-data")
def model_data():
    path = active_dataset_path()
    metrics = compute_model_metrics(str(path), path.stat().st_mtime if path.exists() else 0)

    return render_template(
        "model_data.html",
        metrics=metrics,
        model_name="Random Forest Regressor + Feature-Rich Crop Pipeline",
        dataset_file=path.name,
        updated_at=dataset_timestamp(path),
    )


@app.route("/about")
def about():
    return render_template("about.html")


# Backward compatibility URLs
@app.route("/predict", methods=["POST"])
def predict_compat():
    return crop_predictor()


@app.route("/weather")
def weather_redirect():
    return redirect(url_for("eda"))


@app.route("/market-insights")
def market_redirect():
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.run(debug=True, port=5001)
