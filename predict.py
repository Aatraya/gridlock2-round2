import numpy as np
import pandas as pd
import pickle
import traceback
import catboost

def calculate_resources(duration: float, priority: str, cause: str) -> dict:
    """
    Expert System Rule Engine
    Translates prediction and context into manpower and hardware numbers.
    """
    resources = {"cops": 2, "barricades": 4, "cranes": 0}
    
    normalized_cause = str(cause).lower().strip()
    normalized_priority = str(priority).capitalize().strip()
    
    if duration > 120 and normalized_priority == 'High':
        resources["cops"] = 5
        resources["barricades"] = 20
        if any(keyword in normalized_cause for keyword in ['breakdown', 'accident', 'tree_fall']):
            resources["cranes"] = 1
            
    elif duration > 60 or normalized_priority in ['High', 'Medium']:
        resources["cops"] = 3
        resources["barricades"] = 10
        if 'breakdown' in normalized_cause or 'accident' in normalized_cause:
            resources["cranes"] = 1
            
    elif normalized_cause == 'rally':
        resources["cops"] = 8
        resources["barricades"] = 30
        resources["cranes"] = 0
        
    return resources

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
            print(f"Successfully loaded {len(self.models)} CatBoost ensemble iterations.")
        except Exception as e:
            print(f"Critical Error: Model pipeline failed to load: {e}")
            self.models = []

    def predict_and_allocate(self, input_data: dict) -> dict:
        """
        Runs incoming request logs through Aryan's CatBoost model architecture.
        """
        if not self.models:
            fallback_duration = 135.0 if input_data.get("priority") == "High" else 45.0
            return {
                "predicted_duration_minutes": fallback_duration,
                "allocated_resources": calculate_resources(
                    fallback_duration, 
                    input_data.get('priority', 'Medium'), 
                    input_data.get('event_cause', 'unknown')
                )
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
        X_live = pd.DataFrame([{
            "event_type": str(input_data.get("event_type", "unplanned")),
            "event_cause": str(input_data.get("event_cause", "unknown")),
            "corridor": str(input_data.get("corridor", "Non-corridor")),
            "hour_of_day": hour_val,
            "day_of_week": day_val,
            "priority": str(input_data.get("priority", "Low"))
        }])
        
        # 3. Direct CatBoost to treat text features as string categories
        categorical_features = ["event_type", "event_cause", "corridor", "priority"]
        for col in categorical_features:
            X_live[col] = X_live[col].astype(str)

        # 4. Initialize CatBoost Pool mapping framework
        eval_pool = catboost.Pool(data=X_live, cat_features=categorical_features)
        
        # 5. Run prediction iterations
        log_preds = np.zeros(len(X_live))
        for model in self.models:
            log_preds += model.predict(eval_pool) / len(self.models)
            
        predicted_duration = float(np.expm1(log_preds)[0])
        predicted_duration = max(0.0, predicted_duration)
        
        allocated_resources = calculate_resources(
            duration=predicted_duration,
            priority=input_data.get('priority', 'Medium'),
            cause=input_data.get('event_cause', 'unknown')
        )
        
        return {
            "predicted_duration_minutes": round(predicted_duration, 2),
            "allocated_resources": allocated_resources
        }