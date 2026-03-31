import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, OneHotEncoder

CROP_ATTRIBUTE_MAP = {
    "Sugarcane": {
        "crop_type": "Perennial",
        "water_source": "Irrigated",
        "climate_type": "Tropical",
        "duration_type": "Long-Duration",
        "farming_system": "Field",
        "economic_use": "Cash",
    },
    "Banana": {
        "crop_type": "Perennial",
        "water_source": "Irrigated",
        "climate_type": "Tropical",
        "duration_type": "Long-Duration",
        "farming_system": "Horticulture",
        "economic_use": "Food",
    },
    "Coconut": {
        "crop_type": "Perennial",
        "water_source": "Rainfed",
        "climate_type": "Tropical",
        "duration_type": "Long-Duration",
        "farming_system": "Plantation",
        "economic_use": "Cash",
    },
    "Coffee": {
        "crop_type": "Perennial",
        "water_source": "Rainfed",
        "climate_type": "Tropical",
        "duration_type": "Long-Duration",
        "farming_system": "Plantation",
        "economic_use": "Cash",
    },
    "Tea": {
        "crop_type": "Perennial",
        "water_source": "Rainfed",
        "climate_type": "Subtropical",
        "duration_type": "Long-Duration",
        "farming_system": "Plantation",
        "economic_use": "Cash",
    },
    "Rubber": {
        "crop_type": "Perennial",
        "water_source": "Rainfed",
        "climate_type": "Tropical",
        "duration_type": "Long-Duration",
        "farming_system": "Plantation",
        "economic_use": "Cash",
    },
    "Wheat": {
        "crop_type": "Annual",
        "water_source": "Irrigated",
        "climate_type": "Subtropical",
        "duration_type": "Medium-Duration",
        "farming_system": "Field",
        "economic_use": "Food",
    },
    "Rice": {
        "crop_type": "Annual",
        "water_source": "Irrigated",
        "climate_type": "Tropical",
        "duration_type": "Medium-Duration",
        "farming_system": "Field",
        "economic_use": "Food",
    },
    "Maize": {
        "crop_type": "Annual",
        "water_source": "Irrigated",
        "climate_type": "Subtropical",
        "duration_type": "Medium-Duration",
        "farming_system": "Field",
        "economic_use": "Food",
    },
    "Rapeseed &Mustard": {
        "crop_type": "Annual",
        "water_source": "Rainfed",
        "climate_type": "Subtropical",
        "duration_type": "Medium-Duration",
        "farming_system": "Field",
        "economic_use": "Cash",
    },
    "Sunflower": {
        "crop_type": "Annual",
        "water_source": "Rainfed",
        "climate_type": "Subtropical",
        "duration_type": "Medium-Duration",
        "farming_system": "Field",
        "economic_use": "Cash",
    },
    "Groundnut": {
        "crop_type": "Annual",
        "water_source": "Rainfed",
        "climate_type": "Tropical",
        "duration_type": "Medium-Duration",
        "farming_system": "Field",
        "economic_use": "Cash",
    },
    "Bajra": {
        "crop_type": "Annual",
        "water_source": "Rainfed",
        "climate_type": "Subtropical",
        "duration_type": "Short-Duration",
        "farming_system": "Field",
        "economic_use": "Food",
    },
    "Jowar": {
        "crop_type": "Annual",
        "water_source": "Rainfed",
        "climate_type": "Subtropical",
        "duration_type": "Short-Duration",
        "farming_system": "Field",
        "economic_use": "Food",
    },
    "Moong(Green Gram)": {
        "crop_type": "Annual",
        "water_source": "Rainfed",
        "climate_type": "Tropical",
        "duration_type": "Short-Duration",
        "farming_system": "Field",
        "economic_use": "Food",
    },
    "Urad": {
        "crop_type": "Annual",
        "water_source": "Rainfed",
        "climate_type": "Tropical",
        "duration_type": "Short-Duration",
        "farming_system": "Field",
        "economic_use": "Food",
    },
    "Onion": {
        "crop_type": "Biennial",
        "water_source": "Irrigated",
        "climate_type": "Subtropical",
        "duration_type": "Medium-Duration",
        "farming_system": "Horticulture",
        "economic_use": "Food",
    },
    "Potato": {
        "crop_type": "Annual",
        "water_source": "Irrigated",
        "climate_type": "Temperate",
        "duration_type": "Short-Duration",
        "farming_system": "Horticulture",
        "economic_use": "Food",
    },
    "Sweet potato": {
        "crop_type": "Annual",
        "water_source": "Irrigated",
        "climate_type": "Subtropical",
        "duration_type": "Short-Duration",
        "farming_system": "Horticulture",
        "economic_use": "Food",
    },
    "Cotton(lint)": {
        "crop_type": "Annual",
        "water_source": "Irrigated",
        "climate_type": "Subtropical",
        "duration_type": "Long-Duration",
        "farming_system": "Field",
        "economic_use": "Cash",
    },
    "Tobacco": {
        "crop_type": "Annual",
        "water_source": "Irrigated",
        "climate_type": "Subtropical",
        "duration_type": "Long-Duration",
        "farming_system": "Field",
        "economic_use": "Cash",
    },
}

DEFAULT_ATTRIBUTES = {
    "crop_type": "Annual",
    "water_source": "Irrigated",
    "climate_type": "Subtropical",
    "duration_type": "Medium-Duration",
    "farming_system": "Field",
    "economic_use": "Food",
}

FEATURE_COLUMNS = [
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
]

CATEGORICAL_COLUMNS = [
    "season",
    "crop_type",
    "water_source",
    "climate_type",
    "duration_type",
    "farming_system",
    "economic_use",
]

NUMERIC_COLUMNS = ["area", "fertilizer", "pesticide"]


def assign_attributes(crop_name):
    crop_key = str(crop_name).strip()
    attributes = CROP_ATTRIBUTE_MAP.get(crop_key, DEFAULT_ATTRIBUTES)
    return pd.Series(attributes)


def build_preprocessor():
    return ColumnTransformer(
        transformers=[
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore"),
                CATEGORICAL_COLUMNS,
            ),
            ("numeric", "passthrough", NUMERIC_COLUMNS),
        ]
    )


def main():
    df = pd.read_csv("crop_yield.csv")

    df = df[["crop", "season", "area", "fertilizer", "pesticide", "yield"]].dropna()
    df["crop"] = df["crop"].astype(str).str.strip()
    df["season"] = df["season"].astype(str).str.strip()

    attribute_df = df["crop"].apply(assign_attributes)
    df = pd.concat([df, attribute_df], axis=1)

    enriched_path = "crop_yield_enriched.csv"
    df.to_csv(enriched_path, index=False)

    crop_encoder = LabelEncoder()
    df["crop_encoded"] = crop_encoder.fit_transform(df["crop"])

    X_crop = df[FEATURE_COLUMNS]
    y_crop = df["crop_encoded"]

    X_train_c, X_test_c, y_train_c, y_test_c = train_test_split(
        X_crop, y_crop, test_size=0.2, random_state=42, stratify=y_crop
    )

    crop_pipeline = Pipeline(
        steps=[
            ("preprocessor", build_preprocessor()),
            (
                "model",
                RandomForestClassifier(
                    n_estimators=300,
                    max_depth=20,
                    min_samples_leaf=2,
                    random_state=42,
                ),
            ),
        ]
    )
    crop_pipeline.fit(X_train_c, y_train_c)

    X_yield = df[FEATURE_COLUMNS + ["crop_encoded"]]
    y_yield = df["yield"]

    yield_preprocessor = ColumnTransformer(
        transformers=[
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore"),
                CATEGORICAL_COLUMNS,
            ),
            ("numeric", "passthrough", NUMERIC_COLUMNS + ["crop_encoded"]),
        ]
    )

    X_train_y, X_test_y, y_train_y, y_test_y = train_test_split(
        X_yield, y_yield, test_size=0.2, random_state=42
    )

    yield_pipeline = Pipeline(
        steps=[
            ("preprocessor", yield_preprocessor),
            (
                "model",
                RandomForestRegressor(
                    n_estimators=350,
                    max_depth=22,
                    min_samples_leaf=2,
                    random_state=42,
                ),
            ),
        ]
    )
    yield_pipeline.fit(X_train_y, y_train_y)

    joblib.dump(crop_pipeline, "crop_model.pkl")
    joblib.dump(yield_pipeline, "yield_model.pkl")
    joblib.dump(crop_encoder, "crop_encoder.pkl")

    print("Enriched dataset saved to", enriched_path)
    print("Feature-rich models trained and saved successfully.")


if __name__ == "__main__":
    main()
