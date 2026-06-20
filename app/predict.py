import numpy as np
import pandas as pd
import pickle
import catboost
import os

# Import the single source of truth for resource rules
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
                    # Use the EXACT feature order/list the model was trained on
                    self.feature_order = loaded_data.get("features")
                elif isinstance(loaded_data, list):
                    self.models = loaded_data
                else:
                    self.models = [loaded_data]

            # Fallback: pull feature order directly from the model itself
            if not self.feature_order and self.models:
                self.feature_order = self.models[0].feature_names_

            print(
                f"Successfully loaded {len(self.models)} CatBoost ensemble "
                f"iterations. Expected features: {self.feature_order}"
            )
        except Exception as e:
            print(f"Critical Error: Model pipeline failed to load: {e}")
            self.models = []

    def predict_and_allocate(
        self,
        input_data: dict,
        requires_road_closure: bool = False,
        police_station: str = "Unknown",
    ) -> dict:
        """Runs incoming request logs through the CatBoost model architecture

        and couples predictions directly to the unified expert allocation
        engine, constrained by the responding station's jurisdiction
        capacity.
        """
        if not self.models:
            fallback_duration = (
                135.0 if input_data.get("priority") == "High" else 45.0
            )
            return {
                "predicted_duration_minutes": fallback_duration,
                "allocated_resources": calculate_resources(
                    duration_mins=fallback_duration,
                    priority=input_data.get("priority", "Medium"),
                    event_cause=input_data.get("event_cause", "unknown"),
                    requires_road_closure=requires_road_closure,
                    corridor=input_data.get("corridor", "Non-corridor"),
                    police_station=police_station,
                ),
            }

        # 1. Parse the incoming timestamp to build temporal features
        try:
            ts = pd.to_datetime(input_data.get("start_datetime"))
            hour_val = ts.hour
            day_val = ts.dayofweek
        except Exception:
            hour_val = 12
            day_val = 0

        # 2. Build ONLY the features the model was actually trained on.
        #    event_type is intentionally excluded - it was never part of
        #    training (confirmed via payload['features']).
        full_row = {
            "event_cause": str(input_data.get("event_cause", "unknown")),
            "corridor": str(input_data.get("corridor", "Non-corridor")),
            "priority": str(input_data.get("priority", "Low")),
            "hour_of_day": hour_val,
            "day_of_week": day_val,
        }

        # Use the model's own training order to be 100% safe
        ordered_cols = self.feature_order or list(full_row.keys())
        X_live = pd.DataFrame([{col: full_row[col] for col in ordered_cols}])

        # 3. Direct CatBoost to treat text features as string categories explicitly
        categorical_features = [
            c for c in ["event_cause", "corridor", "priority"] if c in ordered_cols
        ]
        for col in categorical_features:
            X_live[col] = X_live[col].astype(str)

        # 4. Initialize CatBoost Pool mapping framework
        eval_pool = catboost.Pool(
            data=X_live, cat_features=categorical_features
        )

        # 5. Run prediction iterations over the multi-seed ensemble
        log_preds = np.zeros(len(X_live))
        for model in self.models:
            log_preds += model.predict(eval_pool) / len(self.models)

        predicted_duration = float(np.expm1(log_preds)[0])
        predicted_duration = max(0.0, predicted_duration)

        # 6. Allocate resource parameters using the centralized rule-engine script,
        #    constrained to the responding station's jurisdiction capacity
        allocated_resources = calculate_resources(
            duration_mins=predicted_duration,
            priority=str(input_data.get("priority", "Medium")),
            event_cause=str(input_data.get("event_cause", "unknown")),
            requires_road_closure=requires_road_closure,
            corridor=str(input_data.get("corridor", "Non-corridor")),
            police_station=police_station,
        )

        return {
            "predicted_duration_minutes": round(predicted_duration, 2),
            "allocated_resources": allocated_resources,
        }
