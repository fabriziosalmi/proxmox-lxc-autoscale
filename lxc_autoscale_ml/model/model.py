from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import logging
import numpy as np


def train_anomaly_models(df, config):
    # Select only numeric features for training, excluding non-relevant columns
    features_to_use = df.select_dtypes(include=[np.number]).columns.difference(['container_id', 'timestamp'])
    X_train = df[features_to_use]

    model = IsolationForest(
        contamination=config.get('model', {}).get('contamination', 0.05),
        n_estimators=config.get('model', {}).get('n_estimators', 100),
        max_samples=config.get('model', {}).get('max_samples', 64),
        random_state=config.get('model', {}).get('random_state', 42)
    )

    try:
        pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('IsolationForest', model)
        ])
        pipeline.fit(X_train)
        logging.info("IsolationForest model training completed.")
        return pipeline, features_to_use  # Return both the model and the feature set used
    except Exception as e:
        logging.error(f"Error during model training: {e}")
        return None, None

def predict_anomalies(model, latest_metrics, features_to_use, config):
    # Ensure only the relevant features are used for prediction
    latest_metrics_df = latest_metrics[features_to_use].to_frame().T

    try:
        prediction = model.predict(latest_metrics_df)
        return prediction[0]
    except Exception as e:
        logging.error(f"Error during prediction with IsolationForest: {e}")
        return None
