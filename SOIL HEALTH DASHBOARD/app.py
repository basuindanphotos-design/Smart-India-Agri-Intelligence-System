from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from flask import Flask, jsonify, render_template, request

app = Flask(__name__, template_folder="../templates", static_folder="../static")


@dataclass(frozen=True)
class ThresholdBand:
    low: float
    high: float


N_BAND = ThresholdBand(low=80.0, high=140.0)
P_BAND = ThresholdBand(low=20.0, high=60.0)
K_BAND = ThresholdBand(low=120.0, high=280.0)
PH_BAND = ThresholdBand(low=6.5, high=7.5)
MOISTURE_BAND = ThresholdBand(low=35.0, high=60.0)
ORGANIC_CARBON_BAND = ThresholdBand(low=0.5, high=0.9)
EC_BAND = ThresholdBand(low=0.2, high=1.2)


def _to_float(payload: dict[str, Any], key: str, default: float) -> float:
    value = payload.get(key, default)
    if value is None or str(value).strip() == "":
        return float(default)
    return float(value)


def _band_score(value: float, band: ThresholdBand, tolerance: float = 0.35) -> float:
    if band.low <= value <= band.high:
        return 100.0

    mid = (band.low + band.high) / 2.0
    span = max((band.high - band.low) / 2.0, 1.0)
    distance = abs(value - mid)
    normalized = min(distance / (span * (1.0 + tolerance)), 1.0)
    return max(25.0, 100.0 * (1.0 - normalized))


def _classify_level(value: float, band: ThresholdBand) -> str:
    if value < band.low:
        return "Low"
    if value > band.high:
        return "High"
    return "Optimal"


def calculate_soil_score(soil_data: dict[str, Any]) -> dict[str, Any]:
    n = _to_float(soil_data, "nitrogen", 90.0)
    p = _to_float(soil_data, "phosphorus", 30.0)
    k = _to_float(soil_data, "potassium", 170.0)
    ph = _to_float(soil_data, "ph", 6.8)
    moisture = _to_float(soil_data, "moisture", 45.0)
    organic_carbon = _to_float(soil_data, "organic_carbon", 0.65)
    ec = _to_float(soil_data, "electrical_conductivity", 0.7)

    weighted_score = (
        _band_score(n, N_BAND) * 0.2
        + _band_score(p, P_BAND) * 0.14
        + _band_score(k, K_BAND) * 0.14
        + _band_score(ph, PH_BAND) * 0.18
        + _band_score(moisture, MOISTURE_BAND) * 0.14
        + _band_score(organic_carbon, ORGANIC_CARBON_BAND) * 0.12
        + _band_score(ec, EC_BAND) * 0.08
    )

    score = round(max(0.0, min(100.0, weighted_score)), 2)
    if score >= 80:
        grade = "Excellent"
        color = "#1f8f48"
    elif score >= 50:
        grade = "Moderate"
        color = "#d2a200"
    else:
        grade = "Poor"
        color = "#d04a3c"

    return {"score": score, "grade": grade, "color": color}


def analyze_npk(soil_data: dict[str, Any]) -> dict[str, Any]:
    n = _to_float(soil_data, "nitrogen", 90.0)
    p = _to_float(soil_data, "phosphorus", 30.0)
    k = _to_float(soil_data, "potassium", 170.0)

    return {
        "nitrogen": {"value": n, "level": _classify_level(n, N_BAND)},
        "phosphorus": {"value": p, "level": _classify_level(p, P_BAND)},
        "potassium": {"value": k, "level": _classify_level(k, K_BAND)},
    }


def _ph_analysis(ph: float) -> dict[str, str]:
    if ph < PH_BAND.low:
        return {
            "category": "Acidic",
            "suggestion": "Apply agricultural lime and add compost to slowly raise soil pH.",
        }
    if ph > PH_BAND.high:
        return {
            "category": "Alkaline",
            "suggestion": "Apply organic compost and gypsum in split doses to balance pH.",
        }
    return {
        "category": "Neutral",
        "suggestion": "Maintain current pH with balanced fertilization and periodic soil testing.",
    }


def _moisture_analysis(moisture: float) -> dict[str, str]:
    if moisture < MOISTURE_BAND.low:
        return {
            "status": "Irrigation Needed",
            "advice": "Soil moisture is low. Start irrigation and use mulching to reduce evaporation.",
        }
    if moisture > MOISTURE_BAND.high:
        return {
            "status": "Excess Moisture",
            "advice": "Moisture is high. Improve drainage to prevent root stress and fungal pressure.",
        }
    return {
        "status": "Sufficient",
        "advice": "Moisture level is sufficient. Continue scheduled irrigation monitoring.",
    }


def recommend_crops(soil_data: dict[str, Any]) -> list[str]:
    ph = _to_float(soil_data, "ph", 6.8)
    moisture = _to_float(soil_data, "moisture", 45.0)
    n = _to_float(soil_data, "nitrogen", 90.0)

    crops: list[str] = []

    if 6.2 <= ph <= 7.4 and moisture >= 40:
        crops.extend(["Rice", "Wheat", "Maize"])
    if ph < 6.5:
        crops.extend(["Potato", "Tea", "Pineapple"])
    if ph > 7.5:
        crops.extend(["Barley", "Cotton", "Mustard"])
    if n < N_BAND.low:
        crops.extend(["Pulses", "Groundnut"])

    if not crops:
        crops = ["Millets", "Sorghum", "Soybean"]

    unique = []
    seen = set()
    for crop in crops:
        if crop not in seen:
            seen.add(crop)
            unique.append(crop)
    return unique[:6]


def generate_soil_advice(soil_data: dict[str, Any], npk: dict[str, Any]) -> list[str]:
    advice: list[str] = []

    if npk["nitrogen"]["level"] == "Low":
        advice.append("Low nitrogen detected: Apply urea, farmyard manure, or compost in split doses.")
    elif npk["nitrogen"]["level"] == "High":
        advice.append("Nitrogen is high: Reduce N fertilizer input to avoid lodging and nutrient imbalance.")

    if npk["phosphorus"]["level"] == "Low":
        advice.append("Low phosphorus: Apply SSP or DAP near root zone for better uptake.")
    elif npk["phosphorus"]["level"] == "High":
        advice.append("Phosphorus is high: Pause P-heavy fertilizers for this cycle.")

    if npk["potassium"]["level"] == "Low":
        advice.append("Low potassium: Apply MOP and crop residue mulch to improve potassium reserves.")
    elif npk["potassium"]["level"] == "High":
        advice.append("High potassium: Reduce K fertilizer and monitor magnesium balance.")

    organic_carbon = _to_float(soil_data, "organic_carbon", 0.65)
    if organic_carbon < ORGANIC_CARBON_BAND.low:
        advice.append("Organic carbon is low: Add green manure, biochar, and compost for better soil structure.")

    ec = _to_float(soil_data, "electrical_conductivity", 0.7)
    if ec > EC_BAND.high:
        advice.append("Electrical conductivity is high: Leach salts with quality irrigation water and improve drainage.")

    if not advice:
        advice.append("Soil nutrients are balanced. Maintain current nutrient and irrigation schedule.")

    return advice


def _build_alerts(soil_data: dict[str, Any], npk: dict[str, Any], ph_meta: dict[str, str], moisture_meta: dict[str, str]) -> list[dict[str, str]]:
    alerts: list[dict[str, str]] = []

    for nutrient in ("nitrogen", "phosphorus", "potassium"):
        level = npk[nutrient]["level"]
        if level != "Optimal":
            severity = "warning" if level == "Low" else "caution"
            alerts.append(
                {
                    "title": f"{nutrient.title()} {level}",
                    "message": f"{nutrient.title()} level is {level.lower()}. Adjust fertilizer strategy.",
                    "severity": severity,
                }
            )

    if ph_meta["category"] != "Neutral":
        alerts.append(
            {
                "title": f"Soil pH {ph_meta['category']}",
                "message": ph_meta["suggestion"],
                "severity": "warning",
            }
        )

    if moisture_meta["status"] != "Sufficient":
        alerts.append(
            {
                "title": moisture_meta["status"],
                "message": moisture_meta["advice"],
                "severity": "warning",
            }
        )

    return alerts[:5]


def _build_improvement_plan(soil_data: dict[str, Any], npk: dict[str, Any], moisture_meta: dict[str, str], ph_meta: dict[str, str]) -> list[str]:
    plan: list[str] = []

    plan.append("Fertilizer Plan: Use soil-test-based NPK application with split dosing across growth stages.")

    if _to_float(soil_data, "organic_carbon", 0.65) < ORGANIC_CARBON_BAND.low:
        plan.append("Organic Improvement: Add compost/vermicompost and include legume cover crops.")
    else:
        plan.append("Organic Improvement: Maintain residue incorporation and periodic compost support.")

    plan.append(f"Water Management: {moisture_meta['advice']}")
    plan.append(f"Soil Treatment: {ph_meta['suggestion']}")

    return plan


def build_soil_response(payload: dict[str, Any], recommend_callback: Callable[[dict[str, Any]], str] | None = None) -> dict[str, Any]:
    npk = analyze_npk(payload)
    score_meta = calculate_soil_score(payload)

    ph_value = _to_float(payload, "ph", 6.8)
    ph_meta = _ph_analysis(ph_value)

    moisture_value = _to_float(payload, "moisture", 45.0)
    moisture_meta = _moisture_analysis(moisture_value)

    crops = recommend_crops(payload)
    advice = generate_soil_advice(payload, npk)
    alerts = _build_alerts(payload, npk, ph_meta, moisture_meta)
    plan = _build_improvement_plan(payload, npk, moisture_meta, ph_meta)

    recommendation_input = {
        "temperature": float(payload.get("temperature", 28.0)),
        "humidity": float(payload.get("humidity", 60.0)),
        "season": payload.get("season", "Kharif"),
        "crop_type": payload.get("crop_type", "Annual"),
        "water_source": "Irrigated" if moisture_value >= 35 else "Rainfed",
        "climate_type": payload.get("climate_type", "Subtropical"),
        "duration_type": payload.get("duration_type", "Medium-Duration"),
        "farming_system": payload.get("farming_system", "Field"),
        "economic_use": payload.get("economic_use", "Food"),
        "farm_area_hectares": float(payload.get("farm_area_hectares", 1.0)),
    }

    recommended_by_ml = None
    if recommend_callback is not None:
        try:
            recommended_by_ml = recommend_callback(recommendation_input)
        except Exception:
            recommended_by_ml = None

    summary = (
        f"Soil is {score_meta['grade'].lower()} with score {score_meta['score']}. "
        f"pH is {ph_meta['category'].lower()} and moisture is {moisture_meta['status'].lower()}. "
        f"Top suitable crops: {', '.join(crops[:3])}."
    )

    return {
        "score": score_meta,
        "npk": npk,
        "ph": {"value": round(ph_value, 2), **ph_meta},
        "moisture": {"value": round(moisture_value, 2), **moisture_meta},
        "advice": advice,
        "suitable_crops": crops,
        "improvement_plan": plan,
        "alerts": alerts,
        "summary": summary,
        "crop_recommendation_input": recommendation_input,
        "crop_recommendation_from_ml": recommended_by_ml,
    }


@app.route("/soil-health")
def soil_health_page():
    return render_template("soil_health.html")


@app.route("/api/soil-health/analyze", methods=["POST"])
def soil_health_analyze_api():
    try:
        payload = request.get_json(silent=True) or request.form.to_dict()
        response = build_soil_response(payload)
        return jsonify({"ok": True, "result": response})
    except Exception as error:
        return jsonify({"ok": False, "error": f"Soil analysis failed: {error}"}), 400


if __name__ == "__main__":
    app.run(debug=True, port=5054)
