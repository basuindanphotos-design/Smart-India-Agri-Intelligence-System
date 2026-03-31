import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestRegressor
import joblib

df = pd.read_csv("crop_production.csv")

df["yield"] = df["Production"] / df["Area"]

df = df[["Season","Crop","Area","yield"]].dropna()

le_crop = LabelEncoder()
le_season = LabelEncoder()

df["Crop"] = le_crop.fit_transform(df["Crop"])
df["Season"] = le_season.fit_transform(df["Season"])

X = df[["Season","Crop","Area"]]
y = df["yield"]

X_train,X_test,y_train,y_test = train_test_split(
X,y,test_size=0.2,random_state=42
)

model = RandomForestRegressor(n_estimators=200)
model.fit(X_train,y_train)

joblib.dump(model,"season_yield_model.pkl")

print("Season model trained successfully")