from pathlib import Path
import math
import pickle
from io import StringIO

import joblib
import numpy as np
import pandas as pd
from flask import Flask, Response, jsonify, render_template, request
from sklearn.dummy import DummyRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent.parent
ADVANCED_BUNDLE_PATH = ROOT_DIR / "outputs" / "models" / "best_advanced_crop_yield_model.joblib"
ADVANCED_SCORES_PATH = ROOT_DIR / "outputs" / "advanced_model_scores.csv"
MODEL_COMPARISON_PATH = ROOT_DIR / "outputs" / "model_comparison_scores.csv"
MERGED_DATA_PATH = ROOT_DIR / "outputs" / "merged_crop_dataset.csv"
FEATURE_COLUMNS = [
    "Year",
    "average_rain_fall_mm_per_year",
    "pesticides_tonnes",
    "avg_temp",
    "Area",
    "Item",
]

app = Flask(__name__)


def load_artifacts():
    if ADVANCED_BUNDLE_PATH.exists():
        advanced_bundle = joblib.load(ADVANCED_BUNDLE_PATH)
        return {
            "mode": "advanced",
            "bundle": advanced_bundle,
        }

    with open(BASE_DIR / "crop_yield_model.pkl", "rb") as model_file:
        loaded_model = pickle.load(model_file)
    with open(BASE_DIR / "preprocessor.pkl", "rb") as preprocessor_file:
        loaded_preprocessor = pickle.load(preprocessor_file)
    return {
        "mode": "legacy",
        "model": loaded_model,
        "preprocessor": loaded_preprocessor,
    }


runtime_artifacts = load_artifacts()
yield_df = pd.read_csv(BASE_DIR / "yield_df.csv")

if runtime_artifacts["mode"] == "advanced":
    advanced_features = runtime_artifacts["bundle"].get("features", [])
else:
    advanced_features = []


def build_summary_stats(df):
    return {
        "total_records": int(len(df)),
        "total_crops": int(df["Item"].nunique()),
        "countries_covered": int(df["Area"].nunique()),
        "feature_count": int(len(df.columns)),
    }


def build_chart_payload(df):
    crop_yield = (
        df.groupby("Item")["hg/ha_yield"]
        .mean()
        .sort_values(ascending=False)
        .head(10)
        .round(2)
    )

    rainfall_scatter = (
        df[["average_rain_fall_mm_per_year", "hg/ha_yield"]]
        .sample(min(300, len(df)), random_state=42)
        .sort_values("average_rain_fall_mm_per_year")
    )

    temperature_scatter = (
        df[["avg_temp", "hg/ha_yield"]]
        .sample(min(300, len(df)), random_state=19)
        .sort_values("avg_temp")
    )

    historical_yield = (
        df.groupby("Year")["hg/ha_yield"].mean().sort_index().round(2)
    )

    crop_distribution = df["Item"].value_counts().head(10)
    area_yield = (
        df.groupby("Area")["hg/ha_yield"]
        .mean()
        .sort_values(ascending=False)
        .head(12)
        .round(2)
    )

    return {
        "crop_yield_comparison": {
            "labels": crop_yield.index.tolist(),
            "values": crop_yield.values.tolist(),
        },
        "rainfall_vs_yield": {
            "x": rainfall_scatter["average_rain_fall_mm_per_year"].round(2).tolist(),
            "y": rainfall_scatter["hg/ha_yield"].round(2).tolist(),
        },
        "temperature_vs_yield": {
            "x": temperature_scatter["avg_temp"].round(2).tolist(),
            "y": temperature_scatter["hg/ha_yield"].round(2).tolist(),
        },
        "historical_yield_trends": {
            "labels": historical_yield.index.astype(str).tolist(),
            "values": historical_yield.values.tolist(),
        },
        "crop_distribution": {
            "labels": crop_distribution.index.tolist(),
            "values": crop_distribution.values.tolist(),
        },
        "area_vs_production": {
            "labels": area_yield.index.tolist(),
            "values": area_yield.values.tolist(),
        },
    }


def _crop_category(name):
    value = str(name).lower()
    if any(k in value for k in ["rice", "wheat", "maize", "barley", "millet", "sorghum", "paddy"]):
        return "Cereals"
    if any(k in value for k in ["gram", "lentil", "pea", "bean", "arhar", "tur", "urad", "moong", "cowpea"]):
        return "Pulses"
    if any(k in value for k in ["mustard", "sesam", "groundnut", "sunflower", "soy", "castor", "linseed"]):
        return "Oilseeds"
    if any(k in value for k in ["cotton", "sugarcane", "jute", "tobacco", "coffee", "tea", "rubber"]):
        return "Cash Crops"
    if any(k in value for k in ["banana", "mango", "orange", "apple", "potato", "onion", "garlic", "ginger", "coriander"]):
        return "Horticulture"
    return "Other"


def _extract_feature_importance():
    target_features = ["Year", "Rainfall", "Temperature", "Pesticides", "Area"]
    values = {k: 0.0 for k in target_features}

    try:
        if runtime_artifacts["mode"] == "advanced":
            model = runtime_artifacts["bundle"].get("model")
            feature_names = runtime_artifacts["bundle"].get("features", [])
            importances = None

            if hasattr(model, "get_feature_importance"):
                importances = model.get_feature_importance()
            elif hasattr(model, "feature_importances_"):
                importances = model.feature_importances_

            if importances is not None and len(importances) == len(feature_names):
                for fname, importance in zip(feature_names, importances):
                    key = str(fname).lower()
                    imp = float(importance)
                    if "year" in key:
                        values["Year"] += imp
                    elif "rain" in key:
                        values["Rainfall"] += imp
                    elif "temp" in key:
                        values["Temperature"] += imp
                    elif "pestic" in key:
                        values["Pesticides"] += imp
                    elif key == "area" or "area_" in key:
                        values["Area"] += imp
        else:
            model = runtime_artifacts["model"]
            if hasattr(model, "feature_importances_"):
                importances = model.feature_importances_
                for fname, importance in zip(FEATURE_COLUMNS, importances):
                    key = str(fname).lower()
                    imp = float(importance)
                    if "year" in key:
                        values["Year"] += imp
                    elif "rain" in key:
                        values["Rainfall"] += imp
                    elif "temp" in key:
                        values["Temperature"] += imp
                    elif "pestic" in key:
                        values["Pesticides"] += imp
                    elif key == "area":
                        values["Area"] += imp
    except Exception:
        pass

    total = sum(values.values())
    if total > 0:
        values = {k: round((v / total) * 100, 2) for k, v in values.items()}
    else:
        values = {
            "Year": 14.0,
            "Rainfall": 26.0,
            "Temperature": 22.0,
            "Pesticides": 20.0,
            "Area": 18.0,
        }

    return {
        "labels": list(values.keys()),
        "values": list(values.values()),
    }


def build_dataset_analytics_payload(df):
    merged_df = None
    if MERGED_DATA_PATH.exists():
        try:
            merged_df = pd.read_csv(MERGED_DATA_PATH)
        except Exception:
            merged_df = None

    stats = {
        "average_yield": round(float(df["hg/ha_yield"].mean()), 2),
        "median_yield": round(float(df["hg/ha_yield"].median()), 2),
        "yield_std": round(float(df["hg/ha_yield"].std(ddof=0)), 2),
        "average_rainfall": round(float(df["average_rain_fall_mm_per_year"].mean()), 2),
        "average_temperature": round(float(df["avg_temp"].mean()), 2),
        "average_pesticides": round(float(df["pesticides_tonnes"].mean()), 2),
    }

    hist_counts, hist_bins = np.histogram(df["hg/ha_yield"], bins=20)
    hist_labels = [f"{round(hist_bins[i], 1)}-{round(hist_bins[i+1], 1)}" for i in range(len(hist_bins) - 1)]

    top_crops = (
        df.groupby("Item")["hg/ha_yield"]
        .mean()
        .sort_values(ascending=False)
        .head(10)
        .round(2)
    )

    climate_yearly = (
        df.groupby("Year")[["hg/ha_yield", "average_rain_fall_mm_per_year", "avg_temp"]]
        .mean()
        .sort_index()
        .round(2)
    )

    region_rank = (
        df.groupby("Area")["hg/ha_yield"]
        .mean()
        .sort_values(ascending=False)
        .head(20)
        .round(2)
    )

    if merged_df is not None and "Season" in merged_df.columns:
        season_dist = merged_df["Season"].fillna("Unknown").astype(str).str.title().value_counts().head(12)
    else:
        season_dist = pd.Series(dtype=float)

    if merged_df is not None and "Crop" in merged_df.columns and "Yield" in merged_df.columns:
        merged_df = merged_df.copy()
        merged_df["CropCategory"] = merged_df["Crop"].apply(_crop_category)
        category_yield = merged_df.groupby("CropCategory")["Yield"].mean().sort_values(ascending=False).round(2)
    else:
        category_yield = pd.Series(dtype=float)

    if merged_df is not None and all(c in merged_df.columns for c in ["Crop", "Yield", "Area", "Annual_Rainfall"]):
        coverage = (
            merged_df.groupby("Crop")
            .agg(
                records=("Crop", "count"),
                avg_yield=("Yield", "mean"),
                avg_area=("Area", "mean"),
                avg_rainfall=("Annual_Rainfall", "mean"),
            )
            .sort_values("records", ascending=False)
            .head(50)
            .reset_index()
        )
    else:
        coverage = (
            df.groupby("Item")
            .agg(
                records=("Item", "count"),
                avg_yield=("hg/ha_yield", "mean"),
                avg_area=("Year", "mean"),
                avg_rainfall=("average_rain_fall_mm_per_year", "mean"),
            )
            .sort_values("records", ascending=False)
            .head(50)
            .reset_index()
            .rename(columns={"Item": "Crop"})
        )

    coverage = coverage.round(2)

    if merged_df is not None and all(c in merged_df.columns for c in ["Yield", "Annual_Rainfall", "Temperature_C", "Area", "Pesticide"]):
        corr_df = merged_df[["Yield", "Annual_Rainfall", "Temperature_C", "Area", "Pesticide"]].copy()
        corr_df = corr_df.rename(columns={
            "Yield": "Yield",
            "Annual_Rainfall": "Rainfall",
            "Temperature_C": "Temperature",
            "Area": "Area",
            "Pesticide": "Pesticides",
        })
    else:
        corr_df = df[["hg/ha_yield", "average_rain_fall_mm_per_year", "avg_temp", "pesticides_tonnes", "Year"]].copy()
        corr_df = corr_df.rename(columns={
            "hg/ha_yield": "Yield",
            "average_rain_fall_mm_per_year": "Rainfall",
            "avg_temp": "Temperature",
            "pesticides_tonnes": "Pesticides",
            "Year": "Area",
        })

    corr_matrix = corr_df.corr(numeric_only=True).round(3)

    area_yield_scatter = {"x": [], "y": []}
    if merged_df is not None and all(c in merged_df.columns for c in ["Area", "Yield"]):
        sample = merged_df[["Area", "Yield"]].dropna().sample(min(500, len(merged_df)), random_state=42)
        area_yield_scatter = {
            "x": sample["Area"].round(2).tolist(),
            "y": sample["Yield"].round(2).tolist(),
        }

    total_cells = int(df.shape[0] * df.shape[1]) if len(df) else 0
    missing_values = int(df.isna().sum().sum())
    duplicates = int(df.duplicated().sum())
    completeness = round(((total_cells - missing_values) / total_cells) * 100, 2) if total_cells else 100.0

    return {
        "stats": stats,
        "yield_histogram": {"labels": hist_labels, "values": hist_counts.tolist()},
        "top_crops": {"labels": top_crops.index.tolist(), "values": top_crops.values.tolist()},
        "area_yield_scatter": area_yield_scatter,
        "climate_impact": {
            "labels": climate_yearly.index.astype(str).tolist(),
            "yield": climate_yearly["hg/ha_yield"].tolist(),
            "rainfall": climate_yearly["average_rain_fall_mm_per_year"].tolist(),
            "temperature": climate_yearly["avg_temp"].tolist(),
        },
        "yearly_yield_trend": {
            "labels": climate_yearly.index.astype(str).tolist(),
            "values": climate_yearly["hg/ha_yield"].tolist(),
        },
        "region_yield_rank": {"labels": region_rank.index.tolist(), "values": region_rank.values.tolist()},
        "season_distribution": {
            "labels": season_dist.index.tolist() if not season_dist.empty else [],
            "values": season_dist.values.tolist() if not season_dist.empty else [],
        },
        "category_yield": {
            "labels": category_yield.index.tolist() if not category_yield.empty else [],
            "values": category_yield.values.tolist() if not category_yield.empty else [],
        },
        "coverage_report": coverage.to_dict(orient="records"),
        "feature_importance": _extract_feature_importance(),
        "correlation": {
            "labels": corr_matrix.columns.tolist(),
            "values": corr_matrix.values.tolist(),
        },
        "data_quality": {
            "missing_values": missing_values,
            "duplicate_rows": duplicates,
            "completeness_pct": completeness,
        },
    }


def _get_farmer_reference_df():
    if MERGED_DATA_PATH.exists():
        try:
            merged_df = pd.read_csv(MERGED_DATA_PATH)
            if all(
                col in merged_df.columns
                for col in ["State", "Crop", "Year", "Yield", "Annual_Rainfall", "Temperature_C"]
            ):
                return merged_df
        except Exception:
            pass

    fallback = yield_df.rename(
        columns={
            "Area": "State",
            "Item": "Crop",
            "hg/ha_yield": "Yield",
            "average_rain_fall_mm_per_year": "Annual_Rainfall",
            "avg_temp": "Temperature_C",
            "pesticides_tonnes": "Pesticide",
        }
    ).copy()
    return fallback


def _score_band(value, good_min, good_max, moderate_margin):
    if value is None:
        return {"score": 55, "label": "Moderate"}
    if good_min <= value <= good_max:
        return {"score": 92, "label": "Excellent"}
    if (good_min - moderate_margin) <= value <= (good_max + moderate_margin):
        return {"score": 70, "label": "Moderate"}
    return {"score": 38, "label": "Risk"}


def _yield_potential_label(predicted_ton_ha):
    if predicted_ton_ha >= 8:
        return {"label": "High Yield Potential", "tone": "success"}
    if predicted_ton_ha >= 3:
        return {"label": "Moderate Yield Potential", "tone": "warning"}
    return {"label": "Low Yield Risk", "tone": "danger"}


def _crop_timeline(crop_name):
    crop = str(crop_name).lower()
    duration = "90-120 days"
    crop_type = "Seasonal Field Crop"
    if any(k in crop for k in ["rice", "wheat", "maize", "barley", "millet"]):
        duration = "100-140 days"
        crop_type = "Cereal"
    elif any(k in crop for k in ["sugarcane", "banana", "coconut", "arecanut"]):
        duration = "240-365+ days"
        crop_type = "Long Duration / Plantation"
    elif any(k in crop for k in ["potato", "onion", "garlic", "ginger"]):
        duration = "90-150 days"
        crop_type = "Horticulture"
    elif any(k in crop for k in ["gram", "lentil", "pea", "arhar", "tur", "urad", "moong"]):
        duration = "80-130 days"
        crop_type = "Pulse"
    return {
        "duration": duration,
        "crop_type": crop_type,
        "stages": [
            {"name": "Sowing", "days": "0-15"},
            {"name": "Vegetative Growth", "days": "15-45"},
            {"name": "Flowering", "days": "45-75"},
            {"name": "Harvest", "days": duration},
        ],
    }


def build_farmer_insight_payload(payload, prediction_result):
    reference_df = _get_farmer_reference_df().copy()
    state = str(payload.get("Area", "")).strip().lower()
    crop = str(payload.get("Item", "")).strip().lower()
    year = int(float(payload.get("Year", 0) or 0)) if str(payload.get("Year", "")).strip() else None
    rainfall_raw = payload.get("average_rain_fall_mm_per_year", "")
    rainfall = float(rainfall_raw) if str(rainfall_raw).strip() else None
    temperature = float(payload.get("avg_temp", 0) or 0)
    pesticides = float(payload.get("pesticides_tonnes", 0) or 0)
    farm_area = float(payload.get("farm_area_hectares", 1) or 1)
    humidity = float(payload.get("humidity", 65) or 65) if str(payload.get("humidity", "")).strip() else 65.0
    market_price = float(payload.get("market_price_per_ton", 0) or 0) if str(payload.get("market_price_per_ton", "")).strip() else None
    production_qty = float(payload.get("production_quantity", 0) or 0) if str(payload.get("production_quantity", "")).strip() else float(prediction_result["estimated_production_tons"])

    if "State" in reference_df.columns:
        reference_df["_state_key"] = reference_df["State"].astype(str).str.strip().str.lower()
    else:
        reference_df["_state_key"] = ""
    if "Crop" in reference_df.columns:
        reference_df["_crop_key"] = reference_df["Crop"].astype(str).str.strip().str.lower()
    else:
        reference_df["_crop_key"] = ""

    crop_state_df = reference_df[
        (reference_df["_state_key"] == state) & (reference_df["_crop_key"] == crop)
    ]
    crop_df = reference_df[reference_df["_crop_key"] == crop]
    bench_df = crop_state_df if not crop_state_df.empty else crop_df

    regional_avg = None
    if not bench_df.empty and "Yield" in bench_df.columns:
        regional_avg = float(pd.to_numeric(bench_df["Yield"], errors="coerce").dropna().mean())

    top_regions = []
    if not crop_df.empty and all(col in crop_df.columns for col in ["State", "Yield"]):
        top_regions = (
            crop_df.groupby("State")["Yield"]
            .mean()
            .sort_values(ascending=False)
            .head(8)
            .round(2)
            .reset_index()
            .to_dict(orient="records")
        )

    yearly_trend = {"labels": [], "values": []}
    if not crop_df.empty and all(col in crop_df.columns for col in ["Year", "Yield"]):
        trend = crop_df.groupby("Year")["Yield"].mean().sort_index().round(2)
        yearly_trend = {
            "labels": trend.index.astype(str).tolist(),
            "values": trend.values.tolist(),
        }

    yield_dist = {"labels": [], "values": []}
    if not crop_df.empty and "Yield" in crop_df.columns:
        crop_yield_values = pd.to_numeric(crop_df["Yield"], errors="coerce").dropna()
        if len(crop_yield_values):
            counts, bins = np.histogram(crop_yield_values, bins=min(12, max(5, len(crop_yield_values) // 10)))
            yield_dist = {
                "labels": [f"{round(bins[i],1)}-{round(bins[i+1],1)}" for i in range(len(bins) - 1)],
                "values": counts.tolist(),
            }

    temp_match = _score_band(temperature, 20, 30, 5)
    rain_match = _score_band(rainfall, 700, 1500, 350)
    humidity_match = _score_band(humidity, 55, 80, 10)
    climate_score = round((temp_match["score"] + rain_match["score"] + humidity_match["score"]) / 3, 1)
    climate_label = "Excellent" if climate_score >= 85 else "Good" if climate_score >= 70 else "Moderate" if climate_score >= 55 else "Risk"

    yield_ton_ha = float(prediction_result["prediction_ton_per_ha"])
    comparison_pct = None
    if regional_avg and regional_avg > 0:
        comparison_pct = round(((yield_ton_ha - regional_avg) / regional_avg) * 100, 2)

    water_need = "High" if (rainfall is not None and rainfall < 800) or crop in ["rice", "sugarcane"] else "Moderate"
    fertilizer_demand = "High" if yield_ton_ha >= 6 else "Moderate" if yield_ton_ha >= 3 else "Targeted"
    pest_risk = "High" if temperature >= 32 and (humidity >= 75 or rainfall and rainfall > 1500) else "Moderate" if temperature >= 27 else "Low"
    labor_intensity = "High" if crop in ["banana", "sugarcane", "cotton"] else "Moderate"

    risks = []
    if rainfall is not None and rainfall < 700:
        risks.append({"title": "Water Deficit Risk", "level": "warning", "detail": "Rainfall is below ideal range; irrigation planning is important."})
    if temperature >= 35:
        risks.append({"title": "Heat Stress Risk", "level": "danger", "detail": "High temperature may reduce flowering success and grain filling."})
    if pesticides < 1:
        risks.append({"title": "Pest Pressure Risk", "level": "warning", "detail": "Very low pesticide input may expose crop to unmanaged pest load."})
    if not risks:
        risks.append({"title": "Balanced Input Profile", "level": "success", "detail": "No major agronomic stress signal detected from current inputs."})

    education = []
    if rainfall is not None and rainfall < 700:
        education.append("Use supplemental irrigation during flowering and grain-fill stages.")
    if temperature >= 32:
        education.append("Prefer mulching and early-morning irrigation to reduce heat stress.")
    if comparison_pct is not None and comparison_pct < 0:
        education.append("Benchmark is above predicted yield; review soil fertility and sowing-date alignment.")
    if pesticides < 10:
        education.append("Scout pests weekly and apply threshold-based crop protection rather than reactive spraying.")
    if not education:
        education = [
            "Current inputs suggest stable yield performance under standard farm management.",
            "Maintain nutrient scheduling and monitor canopy moisture to preserve yield quality.",
        ]

    recommendations = [
        {
            "title": "Irrigation Strategy",
            "detail": (
                f"For {crop.title()} in {state.title()}, use {'supplemental' if water_need == 'High' else 'stage-based'} "
                "irrigation with priority on flowering and grain-fill stages."
            ),
        },
        {
            "title": "Soil Management",
            "detail": (
                f"Maintain organic matter and run soil testing before the next cycle; current predicted yield is {yield_ton_ha:.2f} t/ha."
            ),
        },
        {
            "title": "Fertilizer Plan",
            "detail": (
                f"Fertilizer demand is {fertilizer_demand.lower()} for this input profile; split nutrient application across early and reproductive growth."
            ),
        },
        {
            "title": "Temperature Management",
            "detail": (
                f"Temperature input ({temperature:.1f} C) indicates {'heat mitigation needed' if temperature >= 32 else 'normal thermal conditions'} "
                "for this crop stage."
            ),
        },
    ]

    decision_support = [
        f"Input Summary: {crop.title()} in {state.title()} ({year}) with rainfall={rainfall if rainfall is not None else 'default'}, temp={temperature:.1f} C, pesticides={pesticides:.2f} t, farm area={farm_area:.2f} ha.",
        f"Yield Decision: Predicted yield is {yield_ton_ha:.2f} t/ha ({_yield_potential_label(yield_ton_ha)['label']}).",
        (
            f"Benchmark Decision: {'Above' if comparison_pct is not None and comparison_pct >= 0 else 'Below'} regional average"
            + (f" by {abs(comparison_pct):.2f}%" if comparison_pct is not None else ", benchmark unavailable")
            + "."
        ),
        (
            "Climate Decision: "
            + f"Climate match is {climate_label}; prioritize {'water management' if water_need == 'High' else 'balanced nutrient and pest monitoring'}"
            + "."
        ),
    ]

    revenue_value = None
    revenue_range = None
    if market_price is not None:
        revenue_value = round(production_qty * market_price, 2)
        revenue_range = [round(revenue_value * 0.9, 2), round(revenue_value * 1.1, 2)]

    confidence = round(float(model_metrics.get("r2") or 0) * 100, 2)

    return {
        "summary": {
            "predicted_yield": yield_ton_ha,
            "estimated_production": float(prediction_result["estimated_production_tons"]),
            "land_area": farm_area,
            "yield_potential": _yield_potential_label(yield_ton_ha),
        },
        "climate": {
            "climate_match": {"score": climate_score, "label": climate_label},
            "temperature": temp_match,
            "rainfall": rain_match,
            "humidity": humidity_match,
            "temperature_stress": "Low" if temperature < 32 else "Moderate" if temperature < 35 else "High",
        },
        "timeline": _crop_timeline(crop),
        "resources": {
            "water_requirement": water_need,
            "fertilizer_demand": fertilizer_demand,
            "pest_risk": pest_risk,
            "labor_intensity": labor_intensity,
        },
        "benchmark": {
            "regional_average": round(regional_avg, 2) if regional_avg is not None else None,
            "predicted_yield": round(yield_ton_ha, 2),
            "difference_pct": comparison_pct,
        },
        "profit": {
            "production_quantity": production_qty,
            "market_price_per_ton": market_price,
            "estimated_market_value": revenue_value,
            "revenue_range": revenue_range,
        },
        "education": education,
        "risks": risks,
        "intelligence": {
            "risk_assessment": risks[0]["title"],
            "climate_suitability": climate_label,
            "market_context": "User-defined price input" if market_price is not None else "Enter market price to estimate revenue range",
            "prediction_confidence": confidence,
        },
        "snapshot": [
            {"title": "Water Need", "value": water_need, "score": 85 if water_need == "Moderate" else 65},
            {"title": "Climate Match", "value": climate_label, "score": climate_score},
            {"title": "Harvest Timeline", "value": _crop_timeline(crop)["duration"], "score": 78},
            {"title": "Yield Rating", "value": _yield_potential_label(yield_ton_ha)["label"], "score": 88 if yield_ton_ha >= 6 else 68},
            {"title": "Crop Category", "value": _crop_timeline(crop)["crop_type"], "score": 72},
            {"title": "Prediction Confidence", "value": f"{confidence}%", "score": confidence},
        ],
        "historical": {
            "yearly_trend": yearly_trend,
            "yield_distribution": yield_dist,
            "top_regions": top_regions,
        },
        "recommendations": recommendations,
        "decision_support": decision_support,
    }


def _build_all_model_scores():
    required_models = [
        "XGBoost",
        "CatBoost",
        "Stacking",
        "ExtraTrees",
        "LightGBM",
        "HistGradientBoosting",
        "RandomForest",
        "GradientBoosting",
    ]

    model_family = {
        "XGBoost": "Gradient Boosted Trees",
        "CatBoost": "Gradient Boosted Trees",
        "Stacking": "Ensemble Meta-Learner",
        "ExtraTrees": "Bagging Ensemble Trees",
        "LightGBM": "Gradient Boosted Trees",
        "HistGradientBoosting": "Histogram Gradient Boosting",
        "RandomForest": "Bagging Ensemble Trees",
        "GradientBoosting": "Gradient Boosted Trees",
    }

    alias_map = {
        "XGBoost_v2": "XGBoost",
    }

    combined = {}
    for path in [ADVANCED_SCORES_PATH, MODEL_COMPARISON_PATH]:
        if not path.exists():
            continue
        try:
            df = pd.read_csv(path)
        except Exception:
            continue

        required_cols = {"Model", "R2", "MAE", "RMSE"}
        if not required_cols.issubset(df.columns):
            continue

        for _, row in df.iterrows():
            raw_name = str(row["Model"]).strip()
            name = alias_map.get(raw_name, raw_name)

            if name not in required_models:
                continue

            try:
                r2 = round(float(row["R2"]), 4)
                mae = round(float(row["MAE"]), 4)
                rmse = round(float(row["RMSE"]), 4)
            except Exception:
                continue

            entry = {
                "name": name,
                "family": model_family.get(name, "ML Model"),
                "r2": r2,
                "mae": mae,
                "rmse": rmse,
                "mean_crop_mae": round(float(row["Mean_Crop_MAE"]), 4)
                if "Mean_Crop_MAE" in df.columns and pd.notna(row.get("Mean_Crop_MAE", np.nan))
                else None,
                "mean_state_mae": round(float(row["Mean_State_MAE"]), 4)
                if "Mean_State_MAE" in df.columns and pd.notna(row.get("Mean_State_MAE", np.nan))
                else None,
                "r2_pct": round(r2 * 100, 2),
                "has_data": True,
            }

            # Keep the best scored version if the model appears in both files
            if name not in combined or entry["r2"] > combined[name]["r2"]:
                combined[name] = entry

    rows = []
    for name in required_models:
        if name in combined:
            rows.append(combined[name])
        else:
            rows.append(
                {
                    "name": name,
                    "family": model_family.get(name, "ML Model"),
                    "r2": None,
                    "mae": None,
                    "rmse": None,
                    "mean_crop_mae": None,
                    "mean_state_mae": None,
                    "r2_pct": 0,
                    "has_data": False,
                }
            )

    available = [r for r in rows if r["has_data"]]
    best_name = max(available, key=lambda r: r["r2"])["name"] if available else None
    for row in rows:
        row["is_best"] = row["name"] == best_name

    # Sort by R2 desc, keep missing-data models at bottom
    rows.sort(key=lambda r: (-1 if not r["has_data"] else 0, -(r["r2"] or -1)))
    return rows


def _enrich_model_leaderboard(metrics, all_models):
    available = [m for m in all_models if m.get("has_data")]
    metrics["models_compared"] = len(available)
    metrics["model_rank"] = None
    metrics["second_best_model"] = None
    metrics["second_best_r2"] = None
    metrics["r2_gap_vs_second"] = None
    metrics["mae_gap_from_best_pct"] = None
    metrics["rmse_gap_from_best_pct"] = None

    if not available:
        return metrics

    available = sorted(available, key=lambda x: x["r2"], reverse=True)
    current_name = str(metrics.get("model_name", ""))

    for idx, model in enumerate(available, start=1):
        if model["name"] == current_name:
            metrics["model_rank"] = idx
            break

    if len(available) > 1:
        metrics["second_best_model"] = available[1]["name"]
        metrics["second_best_r2"] = available[1]["r2"]
        if metrics.get("r2") is not None:
            metrics["r2_gap_vs_second"] = round(
                (float(metrics["r2"]) - float(available[1]["r2"])) * 100,
                3,
            )

    best_mae = min(m["mae"] for m in available if m.get("mae") is not None)
    best_rmse = min(m["rmse"] for m in available if m.get("rmse") is not None)

    if metrics.get("mae") is not None and best_mae > 0:
        metrics["mae_gap_from_best_pct"] = round(
            ((float(metrics["mae"]) - float(best_mae)) / float(best_mae)) * 100,
            2,
        )
    if metrics.get("rmse") is not None and best_rmse > 0:
        metrics["rmse_gap_from_best_pct"] = round(
            ((float(metrics["rmse"]) - float(best_rmse)) / float(best_rmse)) * 100,
            2,
        )

    return metrics


def build_model_metrics(df):
    all_models = _build_all_model_scores()

    if runtime_artifacts["mode"] == "advanced":
        # Estimate train/test counts from the active advanced dataset split policy (80/20)
        advanced_total_records = len(df)
        merged_data_path = ROOT_DIR / "outputs" / "merged_crop_dataset.csv"
        if merged_data_path.exists():
            try:
                advanced_total_records = len(pd.read_csv(merged_data_path))
            except Exception:
                pass
        advanced_train_records = int(advanced_total_records * 0.8)
        advanced_test_records = int(advanced_total_records - advanced_train_records)

        metrics = {
            "model_name": runtime_artifacts["bundle"].get("model_name", "AdvancedModel"),
            "r2": None, "mae": None, "rmse": None,
            "baseline_r2": None, "baseline_mae": None, "baseline_rmse": None,
            "improvement_r2": None, "improvement_mae": None, "improvement_rmse": None,
            "training_records": advanced_train_records,
            "test_records": advanced_test_records,
            "feature_count": len(runtime_artifacts["bundle"].get("features", [])),
            "algorithm_family": "Gradient Boosted Decision Trees",
            "validation_strategy": "80/20 train-test split",
            "all_models": all_models,
        }
        if ADVANCED_SCORES_PATH.exists():
            advanced_scores = pd.read_csv(ADVANCED_SCORES_PATH)
            selected_row = advanced_scores[
                advanced_scores["Model"] == metrics["model_name"]
            ]
            if selected_row.empty:
                selected_row = advanced_scores.head(1)
            if not selected_row.empty:
                metrics["model_name"] = str(selected_row.iloc[0]["Model"])
                metrics["r2"] = round(float(selected_row.iloc[0]["R2"]), 4)
                metrics["mae"] = round(float(selected_row.iloc[0]["MAE"]), 4)
                metrics["rmse"] = round(float(selected_row.iloc[0]["RMSE"]), 4)
        return _enrich_model_leaderboard(metrics, all_models)

    model = runtime_artifacts["model"]
    preprocessor = runtime_artifacts["preprocessor"]
    metrics = {
        "model_name": type(model).__name__,
        "r2": None, "mae": None, "rmse": None,
        "baseline_r2": None, "baseline_mae": None, "baseline_rmse": None,
        "improvement_r2": None, "improvement_mae": None, "improvement_rmse": None,
        "training_records": None, "test_records": None,
        "feature_count": len(FEATURE_COLUMNS),
        "algorithm_family": "Gradient Boosted Decision Trees",
        "validation_strategy": "80/20 train-test split (random_state=42)",
        "all_models": all_models,
    }
    try:
        x_data = df[FEATURE_COLUMNS]
        y_data = df["hg/ha_yield"]
        x_train, x_test, y_train, y_test = train_test_split(
            x_data, y_data, test_size=0.2, random_state=42
        )
        metrics["training_records"] = len(x_train)
        metrics["test_records"] = len(x_test)

        x_test_transformed = preprocessor.transform(x_test)
        predictions = model.predict(x_test_transformed)

        metrics["r2"] = round(float(r2_score(y_test, predictions)), 4)
        metrics["mae"] = round(float(mean_absolute_error(y_test, predictions)), 2)
        metrics["rmse"] = round(
            float(math.sqrt(mean_squared_error(y_test, predictions))), 2
        )

        baseline = DummyRegressor(strategy="mean")
        baseline.fit(x_train, y_train)
        baseline_predictions = baseline.predict(x_test)
        metrics["baseline_r2"] = round(float(r2_score(y_test, baseline_predictions)), 4)
        metrics["baseline_mae"] = round(
            float(mean_absolute_error(y_test, baseline_predictions)), 2
        )
        metrics["baseline_rmse"] = round(
            float(math.sqrt(mean_squared_error(y_test, baseline_predictions))), 2
        )

        # Improvement over baseline
        if metrics["baseline_r2"] is not None and metrics["baseline_r2"] != 0:
            metrics["improvement_r2"] = round(
                ((metrics["r2"] - metrics["baseline_r2"]) / abs(metrics["baseline_r2"])) * 100, 1
            )
        if metrics["baseline_mae"] is not None and metrics["baseline_mae"] != 0:
            metrics["improvement_mae"] = round(
                ((metrics["baseline_mae"] - metrics["mae"]) / metrics["baseline_mae"]) * 100, 1
            )
        if metrics["baseline_rmse"] is not None and metrics["baseline_rmse"] != 0:
            metrics["improvement_rmse"] = round(
                ((metrics["baseline_rmse"] - metrics["rmse"]) / metrics["baseline_rmse"]) * 100, 1
            )
    except Exception:
        pass

    return _enrich_model_leaderboard(metrics, all_models)


summary_stats = build_summary_stats(yield_df)
chart_payload = build_chart_payload(yield_df)
model_metrics = build_model_metrics(yield_df)
dataset_analytics_payload = build_dataset_analytics_payload(yield_df)
top_crop_benchmark_rows = [
    {
        "rank": index + 1,
        "crop": chart_payload["crop_yield_comparison"]["labels"][index],
        "benchmark_yield": chart_payload["crop_yield_comparison"]["values"][index],
    }
    for index in range(len(chart_payload["crop_yield_comparison"]["labels"]))
]
if runtime_artifacts["mode"] == "advanced":
    merged_data_path = ROOT_DIR / "outputs" / "merged_crop_dataset.csv"
    if merged_data_path.exists():
        merged_df = pd.read_csv(merged_data_path)
        crop_items = sorted(merged_df["Crop"].dropna().astype(str).str.title().unique().tolist())
        areas = sorted(merged_df["State"].dropna().astype(str).str.title().unique().tolist())
    else:
        crop_items = sorted(yield_df["Item"].dropna().unique().tolist())
        areas = sorted(yield_df["Area"].dropna().unique().tolist())
else:
    crop_items = sorted(yield_df["Item"].dropna().unique().tolist())
    areas = sorted(yield_df["Area"].dropna().unique().tolist())


def common_context():
    return {
        "crop_items": crop_items,
        "areas": areas,
        "summary_stats": summary_stats,
        "chart_data": chart_payload,
        "top_crop_benchmark_rows": top_crop_benchmark_rows,
        "model_metrics": model_metrics,
    }


def parse_request_payload(incoming_request):
    payload = incoming_request.get_json(silent=True)
    if payload:
        return payload
    return incoming_request.form.to_dict()


def workflow_context():
    return {
        "workflow_dataset_preview": yield_df.head(12).to_dict(orient="records"),
        "workflow_total_records": int(len(yield_df)),
        "workflow_total_features": int(len(yield_df.columns)),
        "workflow_target": "hg/ha_yield",
        "workflow_feature_list": [
            "Year",
            "average_rain_fall_mm_per_year",
            "pesticides_tonnes",
            "avg_temp",
            "Area",
            "Item",
        ],
        "workflow_steps": [
            {
                "id": 1,
                "title": "Dataset Collection",
                "route": "workflow_dataset_page",
                "icon": "bi-database-check",
                "desc": "Collect and consolidate crop-yield, rainfall, temperature, and pesticide datasets.",
            },
            {
                "id": 2,
                "title": "Data Preprocessing",
                "route": "workflow_preprocessing_page",
                "icon": "bi-sliders2",
                "desc": "Handle missing values, normalize units, and prepare model-ready features.",
            },
            {
                "id": 3,
                "title": "Exploratory Data Analysis",
                "route": "workflow_eda_page",
                "icon": "bi-bar-chart-line",
                "desc": "Analyze yield patterns and weather relationships through charts.",
            },
            {
                "id": 4,
                "title": "Feature Engineering",
                "route": "workflow_feature_engineering_page",
                "icon": "bi-diagram-3",
                "desc": "Create agronomic predictors and encode categorical attributes.",
            },
            {
                "id": 5,
                "title": "Model Training",
                "route": "workflow_model_training_page",
                "icon": "bi-cpu",
                "desc": "Train and compare multiple ML algorithms for crop prediction.",
            },
            {
                "id": 6,
                "title": "Model Evaluation",
                "route": "workflow_model_evaluation_page",
                "icon": "bi-clipboard-data",
                "desc": "Evaluate R2, MAE, RMSE and validate generalization quality.",
            },
            {
                "id": 7,
                "title": "Yield Prediction System",
                "route": "workflow_prediction_page",
                "icon": "bi-lightning-charge",
                "desc": "Run user inputs through preprocessing and model inference pipeline.",
            },
            {
                "id": 8,
                "title": "Web Application Deployment",
                "route": "workflow_deployment_page",
                "icon": "bi-cloud-check",
                "desc": "Serve predictions through Flask APIs and interactive dashboards.",
            },
        ],
        "preprocess_snippet": "df = df.drop_duplicates()\ndf['avg_temp'] = df['avg_temp'].fillna(df['avg_temp'].median())\ndf['average_rain_fall_mm_per_year'] = df['average_rain_fall_mm_per_year'].clip(200, 3000)\ndf = df[df['hg/ha_yield'] > 0]",
        "training_snippet": "X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)\nmodel.fit(X_train, y_train)\npreds = model.predict(X_test)",
    }


def _rainfall_note(rainfall, crop):
    if rainfall is None or (isinstance(rainfall, float) and rainfall != rainfall):
        return f"Rainfall not provided — the model used its trained distribution average for {crop}."
    if rainfall < 300:
        return f"{rainfall:.0f} mm/year is very low. {crop} may face significant moisture stress under these conditions."
    if rainfall < 700:
        return f"{rainfall:.0f} mm/year is below the kharif optimal range. Consider irrigation support for {crop}."
    if rainfall < 1200:
        return f"{rainfall:.0f} mm/year falls within the optimal range for most crops including {crop}."
    if rainfall < 2000:
        return f"{rainfall:.0f} mm/year is high. Waterlogging risk may reduce effective yield for {crop}."
    return f"{rainfall:.0f} mm/year is very high. Drainage management is critical for {crop} in this condition."


def _temp_note(avg_temp, crop):
    if avg_temp < 10:
        return f"{avg_temp:.1f}°C is very cold — most crops including {crop} face frost risk and reduced enzymatic activity."
    if avg_temp < 20:
        return f"{avg_temp:.1f}°C is cool — suitable for rabi crops but may slow growth for tropical {crop}."
    if avg_temp < 30:
        return f"{avg_temp:.1f}°C is in the optimal thermal band for {crop} with good photosynthetic efficiency."
    if avg_temp < 38:
        return f"{avg_temp:.1f}°C is warm-to-hot — heat stress may begin to impact {crop} pollination and grain fill."
    return f"{avg_temp:.1f}°C is very high — significant heat stress expected, likely reducing {crop} yield."


def _pesticide_note(pesticides):
    if pesticides == 0:
        return "No pesticides applied — natural pest pressure may reduce yield depending on local conditions."
    if pesticides < 10:
        return f"{pesticides:.2f} tonnes is a light application — adequate for low-risk seasons with minimal pest load."
    if pesticides < 100:
        return f"{pesticides:.2f} tonnes is a moderate application — typical for standard commercial crop protection."
    if pesticides < 500:
        return f"{pesticides:.2f} tonnes is a heavy application — effective against high pest pressure but monitor residue levels."
    return f"{pesticides:.2f} tonnes is a very high application — review necessity against environmental and resistance risk."


def perform_prediction(payload):
    if runtime_artifacts["mode"] == "advanced":
        return perform_advanced_prediction(payload)

    model = runtime_artifacts["model"]
    preprocessor = runtime_artifacts["preprocessor"]
    year = float(payload["Year"])
    rainfall_raw = payload.get("average_rain_fall_mm_per_year", "")
    rainfall = float(rainfall_raw) if str(rainfall_raw).strip() != "" else 0.0
    pesticides = float(payload["pesticides_tonnes"])
    avg_temp = float(payload["avg_temp"])
    area = str(payload["Area"])
    item = str(payload["Item"])
    farm_area_hectares = float(payload.get("farm_area_hectares", 1.0))

    feature_row = pd.DataFrame(
        [[year, rainfall, pesticides, avg_temp, area, item]], columns=FEATURE_COLUMNS
    )
    transformed_features = preprocessor.transform(feature_row)
    prediction_hg_ha = float(model.predict(transformed_features)[0])
    prediction_ton_ha = prediction_hg_ha / 10000
    estimated_total_tons = prediction_ton_ha * farm_area_hectares

    rainfall_note = _rainfall_note(rainfall, item)
    temp_note = _temp_note(avg_temp, item)
    pest_note = _pesticide_note(pesticides)

    simple_explanation = (
        f"{item} in {area} ({int(year)}) is estimated to yield {prediction_ton_ha:.2f} t/ha "
        f"across {farm_area_hectares} ha, producing {estimated_total_tons:.2f} tonnes in total."
    )

    return {
        "prediction_hg_per_ha": round(prediction_hg_ha, 2),
        "prediction_ton_per_ha": round(prediction_ton_ha, 2),
        "estimated_production_tons": round(estimated_total_tons, 2),
        "farm_area_hectares": round(farm_area_hectares, 2),
        "explanation": simple_explanation,
        "factors": {
            "Rainfall": rainfall_note,
            "Temperature": temp_note,
            "Pesticides": pest_note,
            "Farm Area": f"{farm_area_hectares} hectare{'s' if farm_area_hectares != 1 else ''} in {area}.",
        },
    }

def perform_advanced_prediction(payload):
    bundle = runtime_artifacts["bundle"]
    model = bundle["model"]
    preprocessor = bundle["preprocessor"]
    feature_names = bundle["features"]

    year = float(payload["Year"])
    rainfall_raw = payload.get("average_rain_fall_mm_per_year", "")
    rainfall = float(rainfall_raw) if str(rainfall_raw).strip() != "" else float("nan")
    pesticides = float(payload["pesticides_tonnes"])
    avg_temp = float(payload["avg_temp"])
    state = str(payload["Area"]).strip().lower()
    crop = str(payload["Item"]).strip().lower()
    farm_area_hectares = float(payload.get("farm_area_hectares", 1.0))

    feature_row = {}
    for feature in feature_names:
        if feature in {"State", "District", "Crop", "Season"}:
            feature_row[feature] = "unknown"
        else:
            feature_row[feature] = np.nan

    feature_row["State"] = state
    feature_row["Crop"] = crop
    feature_row["Year"] = year
    feature_row["Area"] = farm_area_hectares
    feature_row["Annual_Rainfall"] = rainfall
    feature_row["Pesticide"] = pesticides
    feature_row["Temperature_C"] = avg_temp

    prediction_frame = pd.DataFrame([feature_row], columns=feature_names)
    transformed_features = preprocessor.transform(prediction_frame)
    prediction_ton_ha = float(model.predict(transformed_features)[0])
    prediction_hg_ha = prediction_ton_ha * 10000
    estimated_total_tons = prediction_ton_ha * farm_area_hectares

    rain_val = rainfall if not (isinstance(rainfall, float) and rainfall != rainfall) else None
    rainfall_note = _rainfall_note(rain_val, crop.title())
    temp_note = _temp_note(avg_temp, crop.title())
    pest_note = _pesticide_note(pesticides)

    simple_explanation = (
        f"{crop.title()} in {state.title()} ({int(year)}) is estimated to yield "
        f"{prediction_ton_ha:.2f} t/ha across {farm_area_hectares} ha, "
        f"producing {estimated_total_tons:.2f} tonnes total."
    )

    return {
        "prediction_hg_per_ha": round(prediction_hg_ha, 2),
        "prediction_ton_per_ha": round(prediction_ton_ha, 2),
        "estimated_production_tons": round(estimated_total_tons, 2),
        "farm_area_hectares": round(farm_area_hectares, 2),
        "explanation": simple_explanation,
        "factors": {
            "Rainfall": rainfall_note,
            "Temperature": temp_note,
            "Pesticides": pest_note,
            "Farm Area": f"{farm_area_hectares} hectare{'s' if farm_area_hectares != 1 else ''} in {state.title()}.",
        },
    }


@app.route("/")
def index():
    return render_template("index.html", **common_context())


@app.route("/predict")
def predict_page():
    return render_template("predict.html", **common_context())


@app.route("/dataset")
def dataset_page():
    preview_records = yield_df.head(12).to_dict(orient="records")
    return render_template(
        "dataset.html", preview_records=preview_records, **common_context()
    )


@app.route("/api/dataset-analytics")
def dataset_analytics_api():
    return jsonify({"ok": True, "data": dataset_analytics_payload})


@app.route("/api/dataset-coverage.csv")
def dataset_coverage_export():
    rows = dataset_analytics_payload.get("coverage_report", [])
    coverage_df = pd.DataFrame(rows)
    csv_buffer = StringIO()
    coverage_df.to_csv(csv_buffer, index=False)
    return Response(
        csv_buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=dataset_coverage_report.csv"},
    )


@app.route("/model_performance")
def model_performance_page():
    return render_template("model_performance.html", **common_context())


@app.route("/workflow")
def workflow_page():
    return render_template("project_workflow.html", **common_context(), **workflow_context())


@app.route("/project-workflow")
def project_workflow_page():
    return render_template("project_workflow.html", **common_context(), **workflow_context())


@app.route("/project-workflow/dataset")
def workflow_dataset_page():
    return render_template("dataset_page.html", **common_context(), **workflow_context())


@app.route("/project-workflow/preprocessing")
def workflow_preprocessing_page():
    return render_template("preprocessing_page.html", **common_context(), **workflow_context())


@app.route("/project-workflow/eda")
def workflow_eda_page():
    return render_template("eda_page.html", **common_context(), **workflow_context())


@app.route("/project-workflow/feature-engineering")
def workflow_feature_engineering_page():
    return render_template("feature_engineering_page.html", **common_context(), **workflow_context())


@app.route("/project-workflow/model-training")
def workflow_model_training_page():
    return render_template("model_training_page.html", **common_context(), **workflow_context())


@app.route("/project-workflow/model-evaluation")
def workflow_model_evaluation_page():
    return render_template("model_evaluation_page.html", **common_context(), **workflow_context())


@app.route("/project-workflow/prediction-system")
def workflow_prediction_page():
    return render_template("prediction_page.html", **common_context(), **workflow_context())


@app.route("/project-workflow/deployment")
def workflow_deployment_page():
    return render_template("deployment_page.html", **common_context(), **workflow_context())


@app.route("/farmer_knowledge_insight")
def farmer_knowledge_insight_page():
    return render_template("farmer_knowledge_insight.html", **common_context())


@app.route("/api/farmer-insights", methods=["POST"])
def farmer_insights_api():
    try:
        payload = parse_request_payload(request)
        prediction = perform_prediction(payload)
        insight_payload = build_farmer_insight_payload(payload, prediction)
        return jsonify({"ok": True, "prediction": prediction, "insights": insight_payload})
    except KeyError as error:
        return jsonify({"ok": False, "error": f"Missing input field: {error}"}), 400
    except ValueError:
        return jsonify({"ok": False, "error": "Invalid numeric value in farmer insight request."}), 400
    except Exception as error:
        return jsonify({"ok": False, "error": f"Farmer insight generation failed: {error}"}), 500


@app.route("/about")
def about_page():
    return render_template("about.html", **common_context())


@app.route("/api/predict", methods=["POST"])
def api_predict():
    try:
        payload = parse_request_payload(request)
        result = perform_prediction(payload)
        return jsonify({"ok": True, "result": result})
    except KeyError as error:
        return jsonify({"ok": False, "error": f"Missing input field: {error}"}), 400
    except ValueError:
        return jsonify(
            {"ok": False, "error": "Invalid numeric value in one or more input fields."}
        ), 400
    except Exception as error:
        return jsonify({"ok": False, "error": f"Prediction failed: {error}"}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5002)