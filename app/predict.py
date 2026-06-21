import numpy as np
import pandas as pd
import pickle
import catboost
import os
from datetime import datetime, timezone

from app.resources import calculate_resources


class ProductionPredictor:

    def __init__(self, model_pipeline_path="catboost_ensemble.pkl"):
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        absolute_model_path = os.path.join(BASE_DIR, model_pipeline_path)

        self.models = []
        self.feature_order = None

        try:
            with open(absolute_model_path, "rb") as f:
                loaded_data = pickle.load(f)
                if isinstance(loaded_data, dict) and "models" in loaded_data:
                    self.models = loaded_data["models"]
                    self.feature_order = loaded_data.get("features")
                elif isinstance(loaded_data, list):
                    self.models = loaded_data
                else:
                    self.models = [loaded_data]

            if not self.feature_order and self.models:
                self.feature_order = self.models[0].feature_names_

            print(f"Successfully loaded {len(self.models)} CatBoost ensemble iterations.")
            print(f"Expected features: {self.feature_order}")
        except Exception as e:
            print(f"Model load failed: {e}")
            self.models = []

    def predict_and_allocate(self, input_data: dict, police_station: str):
        if not self.models:
            return 45.0, "Medium", calculate_resources(45.0, "Medium", "accident", police_station)

        dt = datetime.fromisoformat(
            input_data.get("timestamp", datetime.now(timezone.utc).isoformat())
        )
        hour_val = dt.hour
        day_of_week = dt.weekday()

        requires_road_closure = (
            1
            if input_data.get("requires_road_closure") or input_data.get("priority") == "High"
            else 0
        )

        row_dict = {
            "event_cause": input_data.get("event_cause", "accident"),
            "priority": input_data.get("priority", "Medium"),
            "corridor": input_data.get("corridor", "Non-corridor"),
            "latitude": float(input_data.get("latitude", 12.9716)),
            "longitude": float(input_data.get("longitude", 77.5946)),
            "hour": hour_val,
            "day_of_week": day_of_week,
            "requires_road_closure": requires_road_closure,
        }

        X_live = pd.DataFrame([row_dict])

        if self.feature_order:
            for col in self.feature_order:
                if col not in X_live.columns:
                    X_live[col] = 0
            X_live = X_live[self.feature_order]

        cat_features = ["event_cause", "priority", "corridor"]
        cat_features = [c for c in cat_features if c in X_live.columns]

        for c in cat_features:
            X_live[c] = X_live[c].astype(str)

        eval_pool = catboost.Pool(data=X_live, cat_features=cat_features)

        log_preds = np.zeros(len(X_live))
        for model in self.models:
            log_preds += model.predict(eval_pool) / len(self.models)

        base_duration = max(30.0, float(np.expm1(log_preds)[0]))

        final_duration = base_duration
        if input_data.get("priority") == "High":
            final_duration *= 1.4
        if input_data.get("requires_road_closure") or input_data.get("priority") == "High":
            final_duration *= 1.25
        if input_data.get("event_cause") in [
            "public_event",
            "procession",
            "protest",
            "vip_movement",
            "water_logging",
        ]:
            final_duration *= 1.45
        if hour_val in [7, 8, 9, 17, 18, 19, 20]:
            final_duration *= 1.25

        final_duration = round(min(final_duration, 480), 1)

        if final_duration > 120 or input_data.get("priority") == "High":
            severity = "High"
        elif final_duration > 60:
            severity = "Medium"
        else:
            severity = "Low"

        allocated_resources = calculate_resources(
            duration_mins=final_duration,
            priority=input_data.get("priority", "Medium"),
            event_cause=input_data.get("event_cause", "accident"),
            police_station=police_station,
            corridor=input_data.get("corridor", "Non-corridor"),
        )

        return final_duration, severity, allocated_resources