from __future__ import annotations

from pathlib import Path
import warnings

import numpy as np
import pandas as pd

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    import seaborn as sns
except ImportError:  # pragma: no cover - fallback for lean environments
    sns = None

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


ROOT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT_DIR / "outputs"

DATASET_PATHS = {
    "dataset1": Path(r"c:\Users\basui\Downloads\Crop Yield Data India\crop_yield.csv"),
    "dataset2": Path(r"c:\Users\basui\Downloads\India Crop Yield Prediction\APY.csv"),
    "dataset3": Path(
        r"c:\Users\basui\Downloads\Indian Historical Crop Yield and Weather Data\Custom_Crops_yield_Historical_Dataset.csv"
    ),
}

FINAL_COLUMNS = [
    "State",
    "District",
    "Crop",
    "Year",
    "Season",
    "Area",
    "Production",
    "Yield",
    "Annual_Rainfall",
    "Fertilizer",
    "Pesticide",
    "Nitrogen_Requirement",
    "Phosphorus_Requirement",
    "Yield_per_Area",
    "Fertilizer_per_Area",
    "Pesticide_per_Area",
    "Temperature_C",
    "Humidity",
    "pH",
    "Wind_Speed",
    "Solar_Radiation",
]

STATE_NAME_MAP = {
    "andaman and nicobar islands": "andaman and nicobar islands",
    "andaman & nicobar island": "andaman and nicobar islands",
    "chattisgarh": "chhattisgarh",
    "nct of delhi": "delhi",
    "orissa": "odisha",
    "pondicherry": "puducherry",
    "uttaranchal": "uttarakhand",
}


def make_encoder():
    try:
        return OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:  # pragma: no cover - compatibility with older sklearn
        return OneHotEncoder(handle_unknown="ignore", sparse=False)


def normalize_text(value: object) -> str:
    if pd.isna(value):
        return "unknown"
    text = str(value).strip().lower()
    text = " ".join(text.split())
    return text if text else "unknown"


def normalize_state_name(value: object) -> str:
    normalized = normalize_text(value)
    return STATE_NAME_MAP.get(normalized, normalized)


def load_data(paths: dict[str, Path] | None = None) -> dict[str, pd.DataFrame]:
    source_paths = paths or DATASET_PATHS
    dataframes: dict[str, pd.DataFrame] = {}

    for dataset_name, file_path in source_paths.items():
        if file_path.exists():
            dataframes[dataset_name] = pd.read_csv(file_path)
        else:
            warnings.warn(
                f"{dataset_name} was not found at {file_path}. The merge will continue with remaining sources.",
                stacklevel=2,
            )
            dataframes[dataset_name] = pd.DataFrame()

    return dataframes


def standardize_columns(df: pd.DataFrame, dataset_name: str) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    standardized = df.copy()
    standardized.columns = [column.strip() for column in standardized.columns]

    rename_map = {
        "Crop_Year": "Year",
        "State Name": "State",
        "Dist Name": "District",
        "District Name": "District",
        "Area_ha": "Area",
        "Yield_kg_per_ha": "Yield",
        "Annual_Rainfall": "Annual_Rainfall",
        "Rainfall_mm": "Annual_Rainfall",
        "Fertilizer": "Fertilizer",
        "Pesticide": "Pesticide",
        "N_req_kg_per_ha": "Nitrogen_Requirement",
        "P_req_kg_per_ha": "Phosphorus_Requirement",
        "Humidity_%": "Humidity",
        "Wind_Speed_m_s": "Wind_Speed",
        "Solar_Radiation_MJ_m2_day": "Solar_Radiation",
    }
    standardized = standardized.rename(columns=rename_map)

    if dataset_name == "dataset1":
        standardized["District"] = "unknown"
    if dataset_name == "dataset3" and "Season" not in standardized.columns:
        standardized["Season"] = "unknown"
    if "Production" not in standardized.columns:
        standardized["Production"] = np.nan
    if "Fertilizer" not in standardized.columns:
        standardized["Fertilizer"] = np.nan
    if "Pesticide" not in standardized.columns:
        standardized["Pesticide"] = np.nan

    return standardized


def clean_data(df: pd.DataFrame, dataset_name: str) -> pd.DataFrame:
    standardized = standardize_columns(df, dataset_name)
    if standardized.empty:
        return standardized

    cleaned = standardized.copy()

    for column in ["Crop", "District", "Season"]:
        if column in cleaned.columns:
            cleaned[column] = cleaned[column].apply(normalize_text)
    if "State" in cleaned.columns:
        cleaned["State"] = cleaned["State"].apply(normalize_state_name)

    numeric_columns = [
        "Year",
        "Area",
        "Production",
        "Yield",
        "Annual_Rainfall",
        "Fertilizer",
        "Pesticide",
        "Nitrogen_Requirement",
        "Phosphorus_Requirement",
        "Temperature_C",
        "Humidity",
        "pH",
        "Wind_Speed",
        "Solar_Radiation",
    ]
    for column in numeric_columns:
        if column in cleaned.columns:
            cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")

    # Dataset 3 yield is provided as kilograms per hectare; convert to tonnes per hectare.
    if dataset_name == "dataset3" and "Yield" in cleaned.columns:
        cleaned["Yield"] = cleaned["Yield"] / 1000.0

    categorical_columns = [column for column in ["State", "District", "Crop", "Season"] if column in cleaned.columns]
    for column in categorical_columns:
        cleaned[column] = cleaned[column].replace({"nan": "unknown", "": "unknown"}).fillna("unknown")

    return cleaned


def aggregate_dataset3_state_level(dataset3: pd.DataFrame) -> pd.DataFrame:
    if dataset3.empty:
        return dataset3.copy()

    aggregation = {
        "Annual_Rainfall": "median",
        "Nitrogen_Requirement": "median",
        "Phosphorus_Requirement": "median",
        "Temperature_C": "median",
        "Humidity": "median",
        "pH": "median",
        "Wind_Speed": "median",
        "Solar_Radiation": "median",
        "Area": "median",
        "Yield": "median",
    }
    available_aggregation = {
        key: value for key, value in aggregation.items() if key in dataset3.columns
    }
    return (
        dataset3.groupby(["State", "Crop", "Year"], dropna=False)
        .agg(available_aggregation)
        .reset_index()
    )


def coalesce_columns(merged_df: pd.DataFrame) -> pd.DataFrame:
    resolved = merged_df.copy()
    suffix_pairs = [
        ("_left", "_right"),
        ("_left", "_d3"),
        ("_left", "_state"),
        ("_right", "_d3"),
        ("_right", "_state"),
        ("_d3", "_state"),
    ]

    for left_suffix, right_suffix in suffix_pairs:
        left_columns = [column for column in resolved.columns if column.endswith(left_suffix)]
        for left_column in left_columns:
            base_name = left_column[: -len(left_suffix)]
            right_column = f"{base_name}{right_suffix}"
            if right_column in resolved.columns:
                resolved[base_name] = resolved[left_column].combine_first(resolved[right_column])
                resolved = resolved.drop(columns=[left_column, right_column])

    return resolved


def merge_datasets(dataset1: pd.DataFrame, dataset2: pd.DataFrame, dataset3: pd.DataFrame) -> pd.DataFrame:
    if dataset1.empty and dataset2.empty and dataset3.empty:
        raise ValueError("No source data available to merge.")

    if dataset1.empty:
        merged_12 = dataset2.copy()
    elif dataset2.empty:
        merged_12 = dataset1.copy()
    else:
        first_merge_keys = ["State", "Crop", "Year", "Season"]
        merged_12 = pd.merge(
            dataset1,
            dataset2,
            on=first_merge_keys,
            how="outer",
            suffixes=("_left", "_right"),
        )
        merged_12 = coalesce_columns(merged_12)

    if dataset3.empty:
        merged = merged_12.copy()
    else:
        district_merge_keys = [
            key for key in ["State", "District", "Crop", "Year"] if key in merged_12.columns and key in dataset3.columns
        ]
        merged = pd.merge(
            merged_12,
            dataset3,
            on=district_merge_keys,
            how="left",
            suffixes=("_left", "_d3"),
        )
        merged = coalesce_columns(merged)

        state_level_dataset3 = aggregate_dataset3_state_level(dataset3)
        state_level_keys = ["State", "Crop", "Year"]
        merged = pd.merge(
            merged,
            state_level_dataset3,
            on=state_level_keys,
            how="left",
            suffixes=("_left", "_state"),
        )
        merged = coalesce_columns(merged)

    for column in FINAL_COLUMNS:
        if column not in merged.columns:
            merged[column] = np.nan if column not in {"State", "District", "Crop", "Season"} else "unknown"

    merged = merged[FINAL_COLUMNS].copy()

    categorical_columns = ["State", "District", "Crop", "Season"]
    numeric_columns = [column for column in FINAL_COLUMNS if column not in categorical_columns]

    for column in categorical_columns:
        merged[column] = merged[column].fillna("unknown").apply(normalize_text)

    for column in numeric_columns:
        merged[column] = pd.to_numeric(merged[column], errors="coerce")

    merged = merged.drop_duplicates(subset=["State", "District", "Crop", "Year", "Season"], keep="first")
    return merged


def impute_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    imputed = df.copy()
    categorical_columns = ["State", "District", "Crop", "Season"]
    numeric_columns = [column for column in imputed.columns if column not in categorical_columns]

    for column in categorical_columns:
        if column in imputed.columns:
            imputed[column] = imputed[column].fillna("unknown")

    for column in numeric_columns:
        if column in imputed.columns and imputed[column].isna().any():
            imputed[column] = imputed[column].fillna(imputed[column].median())

    return imputed


def remove_outliers(df: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    numeric_columns = columns or [
        "Area",
        "Production",
        "Yield",
        "Annual_Rainfall",
        "Fertilizer",
        "Pesticide",
        "Nitrogen_Requirement",
        "Phosphorus_Requirement",
        "Yield_per_Area",
    ]
    existing_numeric_columns = [column for column in numeric_columns if column in df.columns]

    filtered = df.copy()
    mask = pd.Series(True, index=filtered.index)
    for column in existing_numeric_columns:
        q1 = filtered[column].quantile(0.25)
        q3 = filtered[column].quantile(0.75)
        iqr = q3 - q1
        if pd.isna(iqr) or iqr == 0:
            continue
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        mask &= filtered[column].between(lower_bound, upper_bound, inclusive="both")

    return filtered.loc[mask].reset_index(drop=True)


def feature_engineering(df: pd.DataFrame) -> pd.DataFrame:
    engineered = df.copy()
    safe_area = engineered["Area"].replace(0, np.nan)

    engineered["Yield_per_Area"] = engineered["Production"] / safe_area
    engineered["Fertilizer_per_Area"] = engineered["Fertilizer"] / safe_area
    engineered["Pesticide_per_Area"] = engineered["Pesticide"] / safe_area

    for column in ["Yield_per_Area", "Fertilizer_per_Area", "Pesticide_per_Area"]:
        engineered[column] = engineered[column].replace([np.inf, -np.inf], np.nan)

    return engineered


def encode_features(df: pd.DataFrame) -> tuple[pd.DataFrame, ColumnTransformer]:
    training_df = df.copy()

    categorical_columns = [column for column in ["State", "District", "Crop", "Season"] if column in training_df.columns]
    numeric_candidates = [
        column
        for column in [
            "Area",
            "Production",
            "Annual_Rainfall",
            "Fertilizer",
            "Pesticide",
            "Nitrogen_Requirement",
            "Phosphorus_Requirement",
            "Yield_per_Area",
            "Fertilizer_per_Area",
            "Pesticide_per_Area",
            "Temperature_C",
            "Humidity",
            "pH",
            "Wind_Speed",
            "Solar_Radiation",
            "Year",
        ]
        if column in training_df.columns
    ]
    numeric_columns = [
        column for column in numeric_candidates if not training_df[column].isna().all()
    ]

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "categorical",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="constant", fill_value="unknown")),
                        ("encoder", make_encoder()),
                    ]
                ),
                categorical_columns,
            ),
            (
                "numeric",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                numeric_columns,
            ),
        ],
        remainder="drop",
    )

    feature_matrix = preprocessor.fit_transform(training_df)
    categorical_names = []
    if categorical_columns:
        encoder = preprocessor.named_transformers_["categorical"].named_steps["encoder"]
        categorical_names = encoder.get_feature_names_out(categorical_columns).tolist()
    encoded_columns = categorical_names + numeric_columns

    encoded_df = pd.DataFrame(feature_matrix, columns=encoded_columns, index=training_df.index)
    if "Yield" in training_df.columns:
        encoded_df["Yield"] = training_df["Yield"].values

    return encoded_df, preprocessor


def print_summary_statistics(df: pd.DataFrame) -> None:
    print("=" * 80)
    print("Merged Dataset Summary")
    print("=" * 80)
    print(f"Total rows: {len(df):,}")
    print(f"Total features: {df.shape[1]}")
    print("\nMissing values report:")
    print(df.isna().sum().sort_values(ascending=False).to_string())
    print("\nTop crops distribution:")
    print(df["Crop"].value_counts().head(10).to_string())
    print("\nTop states distribution:")
    print(df["State"].value_counts().head(10).to_string())


def plot_visualizations(df: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    plotting_df = df.copy()

    if sns is not None:
        sns.set_theme(style="whitegrid")

    plt.figure(figsize=(12, 6))
    crop_counts = plotting_df["Crop"].value_counts().head(12)
    if sns is not None:
        sns.barplot(x=crop_counts.values, y=crop_counts.index, palette="Greens_r")
    else:
        plt.barh(crop_counts.index, crop_counts.values, color="#2e8b57")
    plt.title("Top Crop Distribution")
    plt.xlabel("Count")
    plt.ylabel("Crop")
    plt.tight_layout()
    plt.savefig(output_dir / "crop_distribution.png", dpi=200)
    plt.close()

    plt.figure(figsize=(10, 6))
    if sns is not None:
        sns.histplot(plotting_df["Yield"], bins=40, kde=True, color="#2e8b57")
    else:
        plt.hist(plotting_df["Yield"], bins=40, color="#2e8b57", alpha=0.8)
    plt.title("Yield Distribution")
    plt.xlabel("Yield (tonnes per hectare)")
    plt.ylabel("Frequency")
    plt.tight_layout()
    plt.savefig(output_dir / "yield_distribution.png", dpi=200)
    plt.close()

    rainfall_plot_df = plotting_df[["Annual_Rainfall", "Yield"]].dropna()
    if not rainfall_plot_df.empty:
        sample_df = rainfall_plot_df.sample(min(3000, len(rainfall_plot_df)), random_state=42)
        plt.figure(figsize=(10, 6))
        if sns is not None:
            sns.scatterplot(data=sample_df, x="Annual_Rainfall", y="Yield", alpha=0.5, s=35)
        else:
            plt.scatter(sample_df["Annual_Rainfall"], sample_df["Yield"], alpha=0.5, s=20)
        plt.title("Rainfall vs Yield")
        plt.xlabel("Annual Rainfall")
        plt.ylabel("Yield (tonnes per hectare)")
        plt.tight_layout()
        plt.savefig(output_dir / "rainfall_vs_yield.png", dpi=200)
        plt.close()

    area_plot_df = plotting_df[["Area", "Production"]].dropna()
    if not area_plot_df.empty:
        sample_df = area_plot_df.sample(min(3000, len(area_plot_df)), random_state=42)
        plt.figure(figsize=(10, 6))
        if sns is not None:
            sns.scatterplot(data=sample_df, x="Area", y="Production", alpha=0.5, s=35)
        else:
            plt.scatter(sample_df["Area"], sample_df["Production"], alpha=0.5, s=20)
        plt.title("Area vs Production")
        plt.xlabel("Area (hectares)")
        plt.ylabel("Production")
        plt.tight_layout()
        plt.savefig(output_dir / "area_vs_production.png", dpi=200)
        plt.close()


def save_dataset(df: pd.DataFrame, encoded_df: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_dir / "merged_crop_dataset.csv", index=False)
    encoded_df.to_csv(output_dir / "merged_crop_dataset_ml_ready.csv", index=False)


def build_training_dataset() -> tuple[pd.DataFrame, pd.DataFrame]:
    raw_data = load_data()
    dataset1 = clean_data(raw_data["dataset1"], "dataset1")
    dataset2 = clean_data(raw_data["dataset2"], "dataset2")
    dataset3 = clean_data(raw_data["dataset3"], "dataset3")

    merged_df = merge_datasets(dataset1, dataset2, dataset3)
    merged_df = impute_missing_values(merged_df)
    merged_df = feature_engineering(merged_df)
    merged_df = impute_missing_values(merged_df)
    merged_df = remove_outliers(merged_df)

    for column in FINAL_COLUMNS:
        if column not in merged_df.columns:
            merged_df[column] = np.nan

    ordered_columns = [column for column in FINAL_COLUMNS if column in merged_df.columns]
    merged_df = merged_df[ordered_columns]
    encoded_df, _ = encode_features(merged_df)

    return merged_df, encoded_df


def main() -> None:
    merged_df, encoded_df = build_training_dataset()
    save_dataset(merged_df, encoded_df, OUTPUT_DIR)
    plot_visualizations(merged_df, OUTPUT_DIR)
    print_summary_statistics(merged_df)

    print("\nSaved files:")
    print(f"- {OUTPUT_DIR / 'merged_crop_dataset.csv'}")
    print(f"- {OUTPUT_DIR / 'merged_crop_dataset_ml_ready.csv'}")
    print(f"- {OUTPUT_DIR / 'crop_distribution.png'}")
    print(f"- {OUTPUT_DIR / 'yield_distribution.png'}")
    print(f"- {OUTPUT_DIR / 'rainfall_vs_yield.png'}")
    print(f"- {OUTPUT_DIR / 'area_vs_production.png'}")


if __name__ == "__main__":
    main()