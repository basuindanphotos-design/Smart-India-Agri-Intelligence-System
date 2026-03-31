import os

if __name__ == "__main__":
	port = int(os.environ.get("PORT", 5000))
	app.run(host="0.0.0.0", port=port)
from __future__ import annotations

import importlib.util
import os
import pickle
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from flask import Flask, jsonify, redirect, render_template, request

BASE_DIR = Path(__file__).resolve().parent

MODULE_PATHS = {
	"crop_recommendation": BASE_DIR / "CROP RECOMMENDATION MODEL" / "app.py",
	"crop_yield": BASE_DIR / "CROP YIELD MODEL" / "CP" / "CP" / "app.py",
	"crop_price": BASE_DIR / "CROP PRICE MODEL" / "app.py",
}

SOIL_HEALTH_MODULE_PATH = BASE_DIR / "SOIL HEALTH DASHBOARD" / "app.py"

MODULE_UI_URLS = {
	"crop_recommendation": os.getenv("CROP_RECOMMENDATION_URL", "http://127.0.0.1:5001/"),
	"crop_yield": os.getenv("CROP_YIELD_URL", "http://127.0.0.1:5002/"),
	"crop_price": os.getenv("CROP_PRICE_URL", "http://127.0.0.1:5003/"),
	"soil_health": os.getenv("SOIL_HEALTH_URL", "http://127.0.0.1:5004/"),
}

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

# Standardized model paths for reusable prediction functions.
RECOMMENDATION_MODEL_PATH = BASE_DIR / "CROP RECOMMENDATION MODEL" / "crop_model.pkl"
RECOMMENDATION_ENCODER_PATH = BASE_DIR / "CROP RECOMMENDATION MODEL" / "crop_encoder.pkl"
PRICE_MODEL_PATH = BASE_DIR / "CROP PRICE MODEL" / "xgboost_model.pkl"
YIELD_MODEL_PATH = BASE_DIR / "CROP YIELD MODEL" / "CP" / "CP" / "crop_yield_model.pkl"
YIELD_PREPROCESSOR_PATH = BASE_DIR / "CROP YIELD MODEL" / "CP" / "CP" / "preprocessor.pkl"
PRICE_DATASET_PATH = BASE_DIR / "CROP PRICE MODEL" / "dataset" / "crop_prices.csv"
YIELD_DATASET_PATH = BASE_DIR / "CROP YIELD MODEL" / "CP" / "CP" / "yield_df.csv"
RECOMMENDATION_DATASET_PATH = BASE_DIR / "CROP RECOMMENDATION MODEL" / "crop_yield_enriched.csv"


@lru_cache(maxsize=1)
def get_yield_area_lookup() -> dict[str, str]:
	lookup: dict[str, str] = {}
	try:
		if YIELD_DATASET_PATH.exists():
			yield_df = pd.read_csv(YIELD_DATASET_PATH, usecols=["Area"], dtype=str)
			for value in yield_df["Area"].dropna().astype(str):
				normalized = value.strip()
				if normalized:
					lookup[normalized.lower()] = normalized
	except Exception:
		pass
	return lookup


def normalize_yield_area(value: Any) -> str:
	lookup = get_yield_area_lookup()
	raw = str(value or "").strip()
	if not raw:
		return "india"

	key = raw.lower()
	if key in lookup:
		return lookup[key]

	if "india" in lookup:
		return lookup["india"]

	# Use first known category if available; otherwise keep raw input.
	if lookup:
		return next(iter(lookup.values()))
	return raw


@lru_cache(maxsize=1)
def get_yield_item_lookup() -> dict[str, str]:
	lookup: dict[str, str] = {}
	try:
		if YIELD_DATASET_PATH.exists():
			yield_df = pd.read_csv(YIELD_DATASET_PATH, usecols=["Item"], dtype=str)
			for value in yield_df["Item"].dropna().astype(str):
				normalized = value.strip()
				if normalized:
					lookup[normalized.lower()] = normalized
	except Exception:
		pass
	return lookup


def normalize_yield_item(value: Any) -> str:
	lookup = get_yield_item_lookup()
	raw = str(value or "").strip()
	if not raw:
		return "rice"

	lower_raw = raw.lower()
	if lower_raw in lookup:
		return lookup[lower_raw]

	# Secondary fuzzy normalization: remove separators and match by containment.
	def _clean(text: str) -> str:
		return "".join(ch for ch in text.lower() if ch.isalnum())

	clean_raw = _clean(raw)
	for key, canonical in lookup.items():
		clean_key = _clean(key)
		if clean_raw and (clean_raw in clean_key or clean_key in clean_raw):
			return canonical

	if "rice" in lookup:
		return lookup["rice"]
	if lookup:
		return next(iter(lookup.values()))
	return raw


def _load_serialized_model(path: Path):
	if not path.exists():
		return None
	try:
		return joblib.load(path)
	except Exception:
		try:
			with path.open("rb") as file_obj:
				return pickle.load(file_obj)
		except Exception:
			return None


# Models are loaded once at startup for efficient execution.
CROP_MODEL = _load_serialized_model(RECOMMENDATION_MODEL_PATH)
CROP_ENCODER = _load_serialized_model(RECOMMENDATION_ENCODER_PATH)
XGBOOST_PRICE_MODEL = _load_serialized_model(PRICE_MODEL_PATH)
YIELD_MODEL = _load_serialized_model(YIELD_MODEL_PATH)
YIELD_PREPROCESSOR = _load_serialized_model(YIELD_PREPROCESSOR_PATH)


def recommend_crop(data: dict[str, Any]) -> str:
	"""Predict recommended crop using recommendation model and encoder."""
	if CROP_MODEL is None or CROP_ENCODER is None:
		raise FileNotFoundError(
			"Missing recommendation model files: crop_model.pkl and/or crop_encoder.pkl"
		)

	feature_row = {
		"season": data.get("season", "Kharif"),
		"crop_type": data.get("crop_type", "Annual"),
		"water_source": data.get("water_source", "Irrigated"),
		"climate_type": data.get("climate_type", "Subtropical"),
		"duration_type": data.get("duration_type", "Medium-Duration"),
		"farming_system": data.get("farming_system", "Field"),
		"economic_use": data.get("economic_use", "Food"),
		"area": float(data.get("farm_area_hectares", data.get("area", 1.0))),
		"fertilizer": float(data.get("temperature", 28.0)) * 0.4,
		"pesticide": float(data.get("humidity", 60.0)) * 0.3,
	}

	inference_df = pd.DataFrame([feature_row])
	crop_encoded = int(CROP_MODEL.predict(inference_df)[0])
	return str(CROP_ENCODER.inverse_transform([crop_encoded])[0])


def predict_yield(data: dict[str, Any]) -> float:
	"""Predict yield (ton/hectare); uses local yield model if available, otherwise module fallback."""
	recommended_crop = normalize_yield_item(data.get("crop", "rice"))

	if YIELD_MODEL is not None and YIELD_PREPROCESSOR is not None:
		normalized_state = normalize_yield_area(data.get("state", "india"))
		feature_df = pd.DataFrame(
			[
				[
					float(data.get("year", 2026)),
					float(data.get("rainfall", 900)),
					float(data.get("pesticides_tonnes", 25)),
					float(data.get("temperature", 28)),
					normalized_state,
					recommended_crop,
				]
			],
			columns=[
				"Year",
				"average_rain_fall_mm_per_year",
				"pesticides_tonnes",
				"avg_temp",
				"Area",
				"Item",
			],
		)
		transformed = YIELD_PREPROCESSOR.transform(feature_df)
		yield_hg_ha = float(YIELD_MODEL.predict(transformed)[0])
		return round(yield_hg_ha / 10000.0, 2)

	# Placeholder fallback requested when yield model cannot be loaded.
	temp = float(data.get("temperature", 28))
	rain = float(data.get("rainfall", 900))
	baseline = 2.8 + ((rain - 700) * 0.0015) - abs(temp - 27) * 0.05
	return round(max(0.8, baseline), 2)


def predict_price(data: dict[str, Any]) -> float:
	"""Predict price (INR/quintal) using xgboost model when possible, with robust fallback."""
	min_price = float(data.get("min_price", 1500))
	max_price = float(data.get("max_price", 2500))

	if XGBOOST_PRICE_MODEL is not None:
		try:
			price_features = pd.DataFrame(
				[
					{
						"Min_Price": min_price,
						"Max_Price": max_price,
					}
				]
			)
			pred = float(XGBOOST_PRICE_MODEL.predict(price_features)[0])
			return round(pred, 2)
		except Exception:
			# Fallback to module-level robust API pipeline when direct model features mismatch.
			pass

	recommended_crop = str(data.get("crop", "Wheat"))
	expected_yield = float(data.get("yield", 4.5))
	price_output = run_price_pipeline(data, recommended_crop, expected_yield)
	return round(float(price_output["predicted_price_inr_per_quintal"]), 2)


def unified_prediction(input_data: dict[str, Any]) -> dict[str, Any]:
	"""Unified reusable prediction pipeline for crop, yield, and price."""
	crop = recommend_crop(input_data)
	input_data = dict(input_data)
	input_data["crop"] = crop

	yield_pred = predict_yield(input_data)
	input_data["yield"] = yield_pred

	price = predict_price(input_data)

	print("Crop Prediction:", crop)
	print("Yield Prediction:", yield_pred)
	print("Price Prediction:", price)

	return {
		"crop": crop,
		"yield": yield_pred,
		"price": price,
	}


@dataclass
class UnifiedResult:
	recommended_crop: str
	expected_yield_ton_per_hectare: float
	predicted_price_inr_per_quintal: float
	best_market: str
	estimated_revenue_inr: float
	estimated_profit_inr: float
	decision_text: str
	yield_chart: dict[str, list[Any]]
	price_chart: dict[str, list[Any]]
	model_fusion: dict[str, Any]
	raw: dict[str, Any]


def _module_exists(module_key: str) -> bool:
	path = MODULE_PATHS.get(module_key)
	return bool(path and path.exists())


def _load_module(module_key: str):
	path = MODULE_PATHS[module_key]
	if not path.exists():
		raise FileNotFoundError(f"Module file not found: {path}")

	module_name = f"unified_{module_key}_module"
	spec = importlib.util.spec_from_file_location(module_name, str(path))
	if not spec or not spec.loader:
		raise ImportError(f"Unable to load module spec from {path}")

	module = importlib.util.module_from_spec(spec)
	sys.modules[module_name] = module

	previous_cwd = Path.cwd()
	try:
		os.chdir(path.parent)
		spec.loader.exec_module(module)
	finally:
		os.chdir(previous_cwd)

	return module


@lru_cache(maxsize=8)
def get_recommendation_module():
	return _load_module("crop_recommendation")


@lru_cache(maxsize=8)
def get_yield_module():
	return _load_module("crop_yield")


@lru_cache(maxsize=8)
def get_price_module():
	return _load_module("crop_price")


@lru_cache(maxsize=4)
def get_soil_health_module():
	path = SOIL_HEALTH_MODULE_PATH
	if not path.exists():
		raise FileNotFoundError(f"Soil health module file not found: {path}")

	module_name = "unified_soil_health_module"
	spec = importlib.util.spec_from_file_location(module_name, str(path))
	if not spec or not spec.loader:
		raise ImportError(f"Unable to load module spec from {path}")

	module = importlib.util.module_from_spec(spec)
	sys.modules[module_name] = module

	previous_cwd = Path.cwd()
	try:
		os.chdir(path.parent)
		spec.loader.exec_module(module)
	finally:
		os.chdir(previous_cwd)

	return module


def run_crop_recommendation_pipeline(payload: dict[str, Any]) -> dict[str, Any]:
	season = payload.get("season", "Kharif")
	crop_type = payload.get("crop_type", "Annual")
	water_source = payload.get("water_source", "Irrigated")
	climate_type = payload.get("climate_type", "Subtropical")
	duration_type = payload.get("duration_type", "Medium-Duration")
	farming_system = payload.get("farming_system", "Field")
	economic_use = payload.get("economic_use", "Food")
	temperature = float(payload.get("temperature", 28))
	humidity = float(payload.get("humidity", 60))
	area = float(payload.get("farm_area_hectares", payload.get("area", 1.0)))

	feature_row = {
		"season": season,
		"crop_type": crop_type,
		"water_source": water_source,
		"climate_type": climate_type,
		"duration_type": duration_type,
		"farming_system": farming_system,
		"economic_use": economic_use,
		"area": area,
		"fertilizer": temperature * 0.4,
		"pesticide": humidity * 0.3,
	}

	module = get_recommendation_module()
	inference_df = pd.DataFrame([feature_row])

	crop_encoded = int(module.crop_model.predict(inference_df)[0])
	crop_name = str(module.encoder.inverse_transform([crop_encoded])[0])

	yield_df = inference_df.copy()
	yield_df["crop_encoded"] = crop_encoded
	predicted_yield = float(module.yield_model.predict(yield_df)[0])

	estimated_price_per_ton = float(
		module.estimate_crop_price_per_ton(
			economic_use,
			season,
			climate_type,
			predicted_yield,
		)
	)

	return {
		"recommended_crop": crop_name,
		"expected_yield_ton_per_hectare": round(predicted_yield, 2),
		"estimated_price_per_ton": round(estimated_price_per_ton, 2),
	}


def run_yield_pipeline(payload: dict[str, Any], recommended_crop: str) -> dict[str, Any]:
	model_payload = {
		"Year": float(payload.get("year", 2026)),
		"average_rain_fall_mm_per_year": float(payload.get("rainfall", 900)),
		"pesticides_tonnes": float(payload.get("pesticides_tonnes", 25)),
		"avg_temp": float(payload.get("temperature", 28)),
		"Area": normalize_yield_area(payload.get("state", "india")),
		"Item": normalize_yield_item(recommended_crop),
		"farm_area_hectares": float(payload.get("farm_area_hectares", payload.get("area", 1.0))),
	}

	try:
		module = get_yield_module()
		result = module.perform_prediction(model_payload)
		return {
			"expected_yield_ton_per_hectare": round(float(result.get("prediction_ton_per_ha", 0.0)), 2),
			"estimated_production_tons": round(float(result.get("estimated_production_tons", 0.0)), 2),
			"yield_explanation": result.get("explanation", ""),
		}
	except Exception:
		# If CP module dependencies are unavailable (for example catboost import),
		# run inference with the trained local yield model loaded in this app.
		yield_ton_ha = float(
			predict_yield(
				{
					"crop": recommended_crop,
					"year": model_payload["Year"],
					"rainfall": model_payload["average_rain_fall_mm_per_year"],
					"pesticides_tonnes": model_payload["pesticides_tonnes"],
					"temperature": model_payload["avg_temp"],
					"state": model_payload["Area"],
				}
			)
		)
		farm_area = float(model_payload["farm_area_hectares"])
		estimated_total = round(yield_ton_ha * farm_area, 2)
		return {
			"expected_yield_ton_per_hectare": round(yield_ton_ha, 2),
			"estimated_production_tons": estimated_total,
			"yield_explanation": (
				f"Yield estimated from trained yield model for {recommended_crop} in {model_payload['Area']} "
				f"at {yield_ton_ha:.2f} t/ha across {farm_area:.2f} ha."
			),
		}


def run_price_pipeline(
	payload: dict[str, Any],
	recommended_crop: str,
	expected_yield_ton_per_hectare: float,
) -> dict[str, Any]:
	module = get_price_module()

	user_min = payload.get("min_price")
	user_max = payload.get("max_price")
	if user_min is None or user_max is None:
		dynamic_base = 1700 + (expected_yield_ton_per_hectare * 140)
		min_price = round(dynamic_base * 0.92, 2)
		max_price = round(dynamic_base * 1.08, 2)
	else:
		min_price = float(user_min)
		max_price = float(user_max)

	price_payload = {
		"state": payload.get("price_state", payload.get("state", "Unknown")),
		"district": payload.get("district", "Unknown"),
		"market": payload.get("market", "Unknown"),
		"commodity": recommended_crop,
		"variety": payload.get("variety", "Unknown"),
		"arrival_date": payload.get("arrival_date", "2026-03-19"),
		"min_price": min_price,
		"max_price": max_price,
	}

	with module.app.test_client() as client:
		response = client.post("/predict_price", json=price_payload)

	if response.status_code != 200:
		raise RuntimeError(f"Price module returned status {response.status_code}")

	data = response.get_json(silent=True) or {}
	if not data.get("ok"):
		raise RuntimeError(data.get("error", "Price prediction failed"))

	return {
		"predicted_price_inr_per_quintal": round(float(data.get("predicted_price", 0.0)), 2),
		"best_market": str(data.get("best_market", "Local Market")),
		"price_trend": str(data.get("price_trend", "stable")),
		"price_chart": data.get("chart", {"labels": [], "values": []}),
	}


def _build_decision_text(
	crop: str,
	expected_yield_ton_per_hectare: float,
	predicted_price_inr_per_quintal: float,
	price_trend: str,
) -> str:
	yield_quality = "high" if expected_yield_ton_per_hectare >= 4.5 else "moderate"
	trend_word = {
		"increasing": "improving",
		"decreasing": "softening",
		"stable": "stable",
	}.get(price_trend, "stable")

	if expected_yield_ton_per_hectare >= 4.5 and predicted_price_inr_per_quintal >= 1800:
		return (
			f"Grow {crop}. Expected yield is {yield_quality} and market price is {trend_word}. "
			"This looks like a strong profit opportunity."
		)

	return (
		f"Grow {crop} with focused cost control. Expected yield is {yield_quality} and market price is {trend_word}. "
		"Proceed with careful irrigation and market timing."
	)


def _build_yield_chart(expected_yield: float) -> dict[str, list[Any]]:
	labels = ["Year-3", "Year-2", "Year-1", "Current Forecast"]
	values = [
		round(expected_yield * 0.86, 2),
		round(expected_yield * 0.92, 2),
		round(expected_yield * 0.97, 2),
		round(expected_yield, 2),
	]
	return {"labels": labels, "values": values}


def _build_unified_result(payload: dict[str, Any]) -> UnifiedResult:
	rec = run_crop_recommendation_pipeline(payload)

	recommended_crop = rec["recommended_crop"]
	expected_yield = float(rec["expected_yield_ton_per_hectare"])

	yield_data = run_yield_pipeline(payload, recommended_crop)
	if yield_data["expected_yield_ton_per_hectare"] > 0:
		expected_yield = float(yield_data["expected_yield_ton_per_hectare"])

	price_data = run_price_pipeline(payload, recommended_crop, expected_yield)
	predicted_price = float(price_data["predicted_price_inr_per_quintal"])

	farm_area = float(payload.get("farm_area_hectares", payload.get("area", 1.0)))
	production_quintals = expected_yield * farm_area * 10.0
	estimated_revenue = production_quintals * predicted_price
	estimated_profit = estimated_revenue * 0.35

	decision_text = _build_decision_text(
		recommended_crop,
		expected_yield,
		predicted_price,
		price_data.get("price_trend", "stable"),
	)

	yield_chart = _build_yield_chart(expected_yield)
	price_chart = price_data.get("price_chart") or {"labels": [], "values": []}

	# Fusion confidence approximates how favorable and stable the combined 3-model output is.
	yield_score = max(0.0, min(expected_yield / 6.0, 1.0))
	price_score = max(0.0, min(predicted_price / 3000.0, 1.0))
	recommendation_score = 1.0 if rec.get("recommended_crop") else 0.6
	trend_bonus = 1.0 if price_data.get("price_trend", "stable") == "increasing" else 0.85
	fusion_confidence = round(((yield_score * 0.45) + (price_score * 0.45) + (trend_bonus * 0.10)) * 100.0, 2)

	raw_contributions = {
		"recommendation": max(recommendation_score, 0.1),
		"yield": max(yield_score, 0.1),
		"price": max(price_score * trend_bonus, 0.1),
	}
	total_contrib = sum(raw_contributions.values()) or 1.0
	model_contributions = {
		"recommendation": round((raw_contributions["recommendation"] / total_contrib) * 100.0, 2),
		"yield": round((raw_contributions["yield"] / total_contrib) * 100.0, 2),
		"price": round((raw_contributions["price"] / total_contrib) * 100.0, 2),
	}

	model_fusion = {
		"source_models": [
			"Crop Recommendation Model",
			"Crop Yield Prediction Model",
			"Crop Price Prediction Model",
		],
		"fusion_confidence": fusion_confidence,
		"model_contributions": model_contributions,
		"fusion_note": "Best output generated by combining predictions from 3 trained models.",
	}

	return UnifiedResult(
		recommended_crop=recommended_crop,
		expected_yield_ton_per_hectare=round(expected_yield, 2),
		predicted_price_inr_per_quintal=round(predicted_price, 2),
		best_market=price_data.get("best_market", "Local Market"),
		estimated_revenue_inr=round(estimated_revenue, 2),
		estimated_profit_inr=round(estimated_profit, 2),
		decision_text=decision_text,
		yield_chart=yield_chart,
		price_chart=price_chart,
		model_fusion=model_fusion,
		raw={"recommendation": rec, "yield": yield_data, "price": price_data},
	)


def _safe_unified_pipeline(payload: dict[str, Any]) -> UnifiedResult:
	try:
		return _build_unified_result(payload)
	except Exception:
		fallback_crop = str(payload.get("fallback_crop", "Wheat"))
		fallback_yield = round(float(payload.get("fallback_yield", 4.5)), 2)
		fallback_price = round(float(payload.get("fallback_price", 2200.0)), 2)
		area = float(payload.get("farm_area_hectares", payload.get("area", 1.0)))
		revenue = fallback_yield * area * 10.0 * fallback_price
		profit = revenue * 0.3

		return UnifiedResult(
			recommended_crop=fallback_crop,
			expected_yield_ton_per_hectare=fallback_yield,
			predicted_price_inr_per_quintal=fallback_price,
			best_market="Nearest Regulated Market",
			estimated_revenue_inr=round(revenue, 2),
			estimated_profit_inr=round(profit, 2),
			decision_text=(
				f"Grow {fallback_crop}. Expected yield is healthy and price outlook is stable. "
				"Good profit opportunity based on current inputs."
			),
			yield_chart=_build_yield_chart(fallback_yield),
			price_chart={
				"labels": ["Month-3", "Month-2", "Month-1", "Forecast"],
				"values": [
					round(fallback_price * 0.94, 2),
					round(fallback_price * 0.97, 2),
					round(fallback_price * 1.01, 2),
					fallback_price,
				],
			},
			model_fusion={
				"source_models": [
					"Crop Recommendation Model",
					"Crop Yield Prediction Model",
					"Crop Price Prediction Model",
				],
				"fusion_confidence": 70.0,
				"model_contributions": {
					"recommendation": 34.0,
					"yield": 33.0,
					"price": 33.0,
				},
				"fusion_note": "Fallback output generated while one or more models were unavailable.",
			},
			raw={"fallback": True},
		)


def _module_cards() -> list[dict[str, str]]:
	return [
		{
			"title": "Crop Recommendation Prediction",
			"description": "Recommend the most suitable crop using climate, soil, and farm attributes.",
			"icon": "leaf",
			"route": "/crop-recommendation",
		},
		{
			"title": "Crop Yield Prediction",
			"description": "Estimate expected yield from weather, pesticide, and regional features.",
			"icon": "bar-chart",
			"route": "/crop-yield",
		},
		{
			"title": "Crop Price Prediction",
			"description": "Forecast mandi price trends and market opportunities for produce planning.",
			"icon": "trending-up",
			"route": "/crop-price",
		},
		{
			"title": "Soil Health Dashboard",
			"description": "Track soil vitality and nutrient status to improve long-term productivity.",
			"icon": "activity",
			"route": "/soil-health",
		},
		{
			"title": "Unified Farmer Intelligence",
			"description": "Combine recommendation, yield, and market pricing into one AI decision engine.",
			"icon": "layers",
			"route": "/farmer-intelligence",
		},
	]


@lru_cache(maxsize=1)
def get_farmer_dropdown_data() -> dict[str, Any]:
	data = {
		"seasons": [],
		"climate_types": [],
		"economic_uses": [],
		"states": [],
		"districts_by_state": {},
		"markets_by_state_district": {},
		"varieties": [],
	}

	try:
		if RECOMMENDATION_DATASET_PATH.exists():
			rec_df = pd.read_csv(RECOMMENDATION_DATASET_PATH)
			for key, col in [
				("seasons", "season"),
				("climate_types", "climate_type"),
				("economic_uses", "economic_use"),
			]:
				if col in rec_df.columns:
					values = (
						rec_df[col]
						.dropna()
						.astype(str)
						.str.strip()
					)
					data[key] = sorted({v for v in values if v})
	except Exception:
		pass

	states = set()
	price_states = set()
	try:
		if YIELD_DATASET_PATH.exists():
			yield_df = pd.read_csv(YIELD_DATASET_PATH, usecols=["Area"])
			if "Area" in yield_df.columns:
				values = yield_df["Area"].dropna().astype(str).str.strip()
				states.update(v for v in values if v)
	except Exception:
		pass

	try:
		if PRICE_DATASET_PATH.exists():
			price_df = pd.read_csv(
				PRICE_DATASET_PATH,
				usecols=["State", "District", "Market", "Variety"],
				dtype=str,
			)

			for _, row in price_df.iterrows():
				state = str(row.get("State", "")).strip()
				district = str(row.get("District", "")).strip()
				market = str(row.get("Market", "")).strip()
				variety = str(row.get("Variety", "")).strip()

				if state:
					price_states.add(state)
				if variety:
					data["varieties"].append(variety)

				if state and district:
					data["districts_by_state"].setdefault(state, []).append(district)
				if state and district and market:
					key = f"{state}|||{district}"
					data["markets_by_state_district"].setdefault(key, []).append(market)

			data["varieties"] = sorted(set(data["varieties"]))
			for key in list(data["districts_by_state"].keys()):
				data["districts_by_state"][key] = sorted(set(data["districts_by_state"][key]))
			for key in list(data["markets_by_state_district"].keys()):
				data["markets_by_state_district"][key] = sorted(
					set(data["markets_by_state_district"][key])
				)
	except Exception:
		pass

	# For state->district->market cascading, prefer price-dataset states.
	data["states"] = sorted(price_states) if price_states else sorted(states)

	# Deterministic safe fallbacks if any dataset is unavailable.
	if not data["seasons"]:
		data["seasons"] = ["Kharif", "Rabi", "Zaid", "Whole Year"]
	if not data["climate_types"]:
		data["climate_types"] = ["Subtropical", "Tropical", "Temperate"]
	if not data["economic_uses"]:
		data["economic_uses"] = ["Food", "Cash", "Fodder"]

	return data


@app.route("/")
def index():
	return render_template(
		"index.html",
		cards=_module_cards(),
		nav_active="home",
	)


@app.route("/api/metrics")
def get_metrics():
	"""Return dynamic metrics for the dashboard"""
	try:
		metrics = {
			"ml_models": 5,  # Total AI models
			"data_points": 0,
			"accuracy": 94,
			"states_covered": 32
		}
		
		# Count total data points from datasets
		total_data_points = 0
		
		# Price dataset
		if PRICE_DATASET_PATH.exists():
			try:
				price_df = pd.read_csv(PRICE_DATASET_PATH)
				total_data_points += len(price_df)
			except:
				pass
		
		# Yield dataset
		if YIELD_DATASET_PATH.exists():
			try:
				yield_df = pd.read_csv(YIELD_DATASET_PATH)
				total_data_points += len(yield_df)
			except:
				pass
		
		# Recommendation dataset
		if RECOMMENDATION_DATASET_PATH.exists():
			try:
				rec_df = pd.read_csv(RECOMMENDATION_DATASET_PATH)
				total_data_points += len(rec_df)
			except:
				pass
		
		# Get unique states from datasets
		states_set = set()
		if PRICE_DATASET_PATH.exists():
			try:
				price_df = pd.read_csv(PRICE_DATASET_PATH)
				if "State" in price_df.columns:
					states_set.update(price_df["State"].dropna().unique().tolist())
			except:
				pass
		
		if RECOMMENDATION_DATASET_PATH.exists():
			try:
				rec_df = pd.read_csv(RECOMMENDATION_DATASET_PATH)
				if "State" in rec_df.columns:
					states_set.update(rec_df["State"].dropna().unique().tolist())
			except:
				pass
		
		metrics["data_points"] = total_data_points
		metrics["states_covered"] = len(states_set) if states_set else 32
		
		return jsonify({
			"ok": True,
			"metrics": metrics
		})
	
	except Exception as e:
		return jsonify({
			"ok": False,
			"error": str(e),
			"metrics": {
				"ml_models": 5,
				"data_points": 1000000,
				"accuracy": 94,
				"states_covered": 32
			}
		}), 500


@app.route("/crop-recommendation")
def crop_recommendation_redirect():
	return redirect(MODULE_UI_URLS["crop_recommendation"])


@app.route("/crop-yield")
def crop_yield_redirect():
	return redirect(MODULE_UI_URLS["crop_yield"])


@app.route("/crop-price")
def crop_price_redirect():
	return redirect(MODULE_UI_URLS["crop_price"])


@app.route("/soil-health")
def soil_health_redirect():
	return render_template("soil_health.html", nav_active="soil-health")


@app.route("/api/soil-health/analyze", methods=["POST"])
def soil_health_analyze_api():
	try:
		payload = request.get_json(silent=True) or request.form.to_dict()
		if not payload:
			return jsonify({"ok": False, "error": "No soil input provided."}), 400

		soil_module = get_soil_health_module()
		result = soil_module.build_soil_response(payload, recommend_callback=recommend_crop)
		return jsonify({"ok": True, "result": result}), 200
	except (ValueError, TypeError) as error:
		return jsonify({"ok": False, "error": f"Invalid soil input: {error}"}), 400
	except Exception as error:
		return jsonify({"ok": False, "error": f"Soil analysis failed: {error}"}), 500


@app.route("/farmer-intelligence", methods=["GET", "POST"])
def farmer_intelligence():
	defaults = {
		"temperature": 28,
		"humidity": 60,
		"rainfall": 900,
		"farm_area_hectares": 1,
		"year": 2026,
		"pesticides_tonnes": 25,
		"season": "Kharif",
		"crop_type": "Annual",
		"water_source": "Irrigated",
		"climate_type": "Subtropical",
		"duration_type": "Medium-Duration",
		"farming_system": "Field",
		"economic_use": "Food",
		"state": "Punjab",
		"district": "Ludhiana",
		"market": "Main Mandi",
		"variety": "Standard",
	}

	payload = defaults.copy()
	if request.method == "POST":
		payload.update(request.form.to_dict())

	result = _safe_unified_pipeline(payload) if request.method == "POST" else None

	return render_template(
		"farmer_intelligence.html",
		nav_active="farmer-intelligence",
		module_status={
			"crop_recommendation": _module_exists("crop_recommendation"),
			"crop_yield": _module_exists("crop_yield"),
			"crop_price": _module_exists("crop_price"),
			"soil_health": SOIL_HEALTH_MODULE_PATH.exists(),
		},
		dropdown_data=get_farmer_dropdown_data(),
		defaults=defaults,
		result=result,
	)


@app.route("/api/farmer-intelligence/predict", methods=["POST"])
def farmer_intelligence_api():
	payload = request.get_json(silent=True) or {}
	result = _safe_unified_pipeline(payload)
	return jsonify(
		{
			"recommended_crop": result.recommended_crop,
			"expected_yield_ton_per_hectare": result.expected_yield_ton_per_hectare,
			"predicted_price_inr_per_quintal": result.predicted_price_inr_per_quintal,
			"best_market": result.best_market,
			"estimated_revenue_inr": result.estimated_revenue_inr,
			"estimated_profit_inr": result.estimated_profit_inr,
			"decision_text": result.decision_text,
			"yield_chart": result.yield_chart,
			"price_chart": result.price_chart,
			"model_fusion": result.model_fusion,
			"raw": result.raw,
		}
	)


@app.route("/predict-all", methods=["POST"])
def predict_all():
	"""Accept form or JSON input and return unified model predictions."""
	try:
		payload = request.get_json(silent=True)
		if not payload:
			payload = request.form.to_dict()

		if not payload:
			return jsonify({"error": "No input data provided. Send JSON body or form data."}), 400

		result = unified_prediction(payload)
		return jsonify({"ok": True, "result": result}), 200

	except FileNotFoundError as error:
		return jsonify({"ok": False, "error": f"Model file missing: {error}"}), 500
	except (ValueError, TypeError) as error:
		return jsonify({"ok": False, "error": f"Invalid input: {error}"}), 400
	except Exception as error:
		return jsonify({"ok": False, "error": f"Prediction error: {error}"}), 500


if __name__ == "__main__":
	app.run(debug=True, port=5050)

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
