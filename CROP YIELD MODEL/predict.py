from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
LEGACY_DIR = BASE_DIR / "CP" / "CP"
ADVANCED_BUNDLE_PATH = BASE_DIR / "outputs" / "models" / "best_advanced_crop_yield_model.joblib"
LEGACY_MODEL_PATH = LEGACY_DIR / "crop_yield_model.pkl"
LEGACY_PREPROCESSOR_PATH = LEGACY_DIR / "preprocessor.pkl"

_RUNTIME: dict[str, Any] = {"mode": None, "bundle": None, "model": None, "preprocessor": None}


class YieldPredictionError(RuntimeError):
    """Raised when crop yield prediction cannot be completed."""


def _load_runtime() -> dict[str, Any]:
    if _RUNTIME["mode"] is not None:
        return _RUNTIME

    if ADVANCED_BUNDLE_PATH.exists():
        bundle = joblib.load(ADVANCED_BUNDLE_PATH)
        _RUNTIME.update({"mode": "advanced", "bundle": bundle})
        return _RUNTIME

    if LEGACY_MODEL_PATH.exists() and LEGACY_PREPROCESSOR_PATH.exists():
        model = joblib.load(LEGACY_MODEL_PATH)
        preprocessor = joblib.load(LEGACY_PREPROCESSOR_PATH)
        _RUNTIME.update(
            {
                "mode": "legacy",
                "model": model,
                "preprocessor": preprocessor,
            }
        )
        return _RUNTIME

    raise YieldPredictionError(
        "No yield model artifacts found. Expected one of: "
        f"{ADVANCED_BUNDLE_PATH} or ({LEGACY_MODEL_PATH} and {LEGACY_PREPROCESSOR_PATH})."
    )


def _to_float(payload: dict[str, Any], key: str, default: float) -> float:
    raw = payload.get(key, default)
    if raw is None or str(raw).strip() == "":
        return float(default)
    return float(raw)


def predict_yield(data: dict[str, Any]) -> dict[str, Any]:
    """
    Reusable crop yield prediction function extracted from notebook/app logic.

    Expected input keys:
    - Year
    - average_rain_fall_mm_per_year
    - pesticides_tonnes
    - avg_temp
    - Area
    - Item
    - farm_area_hectares (optional, default=1.0)

    Returns:
    - prediction_ton_per_ha
    - prediction_hg_per_ha
    - estimated_production_tons
    - mode
    """
    runtime = _load_runtime()

    year = _to_float(data, "Year", 2026)
    rainfall = _to_float(data, "average_rain_fall_mm_per_year", 900.0)
    pesticides = _to_float(data, "pesticides_tonnes", 25.0)
    avg_temp = _to_float(data, "avg_temp", 28.0)
    area = str(data.get("Area", "india")).strip() or "india"
    item = str(data.get("Item", "rice")).strip().lower() or "rice"
    farm_area_hectares = _to_float(data, "farm_area_hectares", 1.0)

    if runtime["mode"] == "advanced":
        bundle = runtime["bundle"]
        model = bundle["model"]
        preprocessor = bundle["preprocessor"]
        feature_names = bundle["features"]

        row = {}
        for feature in feature_names:
            if feature in {"State", "District", "Crop", "Season"}:
                row[feature] = "unknown"
            else:
                row[feature] = np.nan

        row["State"] = area.lower()
        row["Crop"] = item
        row["Year"] = year
        row["Area"] = farm_area_hectares
        row["Annual_Rainfall"] = rainfall
        row["Pesticide"] = pesticides
        row["Temperature_C"] = avg_temp

        frame = pd.DataFrame([row], columns=feature_names)
        transformed = preprocessor.transform(frame)
        prediction_ton_ha = float(model.predict(transformed)[0])
        prediction_hg_ha = prediction_ton_ha * 10000.0
    else:
        model = runtime["model"]
        preprocessor = runtime["preprocessor"]
        feature_columns = [
            "Year",
            "average_rain_fall_mm_per_year",
            "pesticides_tonnes",
            "avg_temp",
            "Area",
            "Item",
        ]
        frame = pd.DataFrame(
            [[year, rainfall, pesticides, avg_temp, area, item]], columns=feature_columns
        )
        transformed = preprocessor.transform(frame)
        prediction_hg_ha = float(model.predict(transformed)[0])
        prediction_ton_ha = prediction_hg_ha / 10000.0

    estimated_production_tons = prediction_ton_ha * farm_area_hectares

    return {
        "prediction_ton_per_ha": round(prediction_ton_ha, 2),
        "prediction_hg_per_ha": round(prediction_hg_ha, 2),
        "estimated_production_tons": round(estimated_production_tons, 2),
        "mode": runtime["mode"],
    }
