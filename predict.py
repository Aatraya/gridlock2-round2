import numpy as np
import pandas as pd
import pickle
import catboost

# Import the single source of truth for resource rules
from app.resources import calculate_resources


class ProductionPredictor:

    def __init__(self, model_pipeline_path="catboost_ensemble.pkl"):
        self.models = []
        try:
            with open(model_pipeline_path, "rb") as f:
                loaded_data = pickle.load(f)
                if isinstance(loaded_data, dict) and "models" in loaded_data:
                    self.models = loaded_data["models"]
                elif isinstance(loaded_data, list):
                    self.models = loaded_data
                else:
                    self.models = [loaded_data]
            print(
                f"Successfully loaded {len(self.models)} CatBoost ensemble iterations."
            )
        except Exception as e:
            print(f"Critical Error: Model pipeline failed to load: {e}")
            self.models = []

    def predict_and_allocate(
        self, input_data: dict, requires_road_closure: bool = False
    ) -> dict:
        """Runs incoming request logs through the CatBoost model architecture

        and couples predictions directly to the unified expert allocation
        engine.
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

        # 2. Reconstruct the exact feature column schema alignment the model demands
        X_live = pd.DataFrame(
            [
                {
                    "event_type": str(input_data.get("event_type", "unplanned")),
                    "event_cause": str(
                        input_data.get("event_cause", "unknown")
                    ),
                    "corridor": str(input_data.get("corridor", "Non-corridor")),
                    "hour_of_day": hour_val,
                    "day_of_week": day_val,
                    "priority": str(input_data.get("priority", "Low")),
                }
            ]
        )

        # 3. Direct CatBoost to treat text features as string categories explicitly
        categorical_features = [
            "event_type",
            "event_cause",
            "corridor",
            "priority",
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

        # 6. Allocate resource parameters using the centralized rule-engine script
        allocated_resources = calculate_resources(
            duration_mins=predicted_duration,
            priority=str(input_data.get("priority", "Medium")),
            event_cause=str(input_data.get("event_cause", "unknown")),
            requires_road_closure=requires_road_closure,
            corridor=str(input_data.get("corridor", "Non-corridor")),
        )

        return {
            "predicted_duration_minutes": round(predicted_duration, 2),
            "allocated_resources": allocated_resources,
        }