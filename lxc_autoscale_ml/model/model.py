from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import logging
import numpy as np
import pandas as pd

def train_anomaly_models(df, config):
    # Select only numeric features for training, excluding non-relevant columns
    features_to_use = df.select_dtypes(include=[np.number]).columns.difference(['container_id', 'timestamp'])
    X_train = df[features_to_use]

    logging.info(f"Features used for training: {list(features_to_use)}")

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

    logging.debug(f"Features used for prediction: {latest_metrics_df.columns.tolist()}")

    try:
        anomaly_score = model.decision_function(latest_metrics_df)
        # Convert anomaly_score to a scalar if it's an array
        anomaly_score = anomaly_score.item() if isinstance(anomaly_score, np.ndarray) else anomaly_score
        # Normalize the anomaly score to a confidence level (0 to 100%)
        confidence = (1 - anomaly_score) * 100  # Inverse because lower scores mean more abnormal
        logging.debug(f"Anomaly score: {anomaly_score}, Confidence: {confidence:.2f}%")
        prediction = model.predict(latest_metrics_df)
        prediction = prediction.item() if isinstance(prediction, np.ndarray) else prediction
        return prediction, confidence
    except Exception as e:
        logging.error(f"Error during prediction with IsolationForest: {e}")
        return None, 0
