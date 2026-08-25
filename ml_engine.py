import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import json
import pickle
import os

logger = logging.getLogger(__name__)

try:
    from sklearn.model_selection import (
        train_test_split,
        cross_val_score,
        GridSearchCV,
    )
    from sklearn.preprocessing import LabelEncoder, StandardScaler
    from sklearn.metrics import (
        accuracy_score,
        classification_report,
        mean_squared_error,
        r2_score,
    )
    from sklearn.ensemble import (
        RandomForestClassifier,
        RandomForestRegressor,
        GradientBoostingClassifier,
        GradientBoostingRegressor,
    )
    from sklearn.linear_model import LogisticRegression, LinearRegression, Ridge, Lasso
    from sklearn.svm import SVC, SVR
    from sklearn.cluster import KMeans, DBSCAN
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler as SklearnStandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn not installed. ML features unavailable.")

try:
    from sklearn.ensemble import IsolationForest
    ISOLATION_FOREST_AVAILABLE = True
except ImportError:
    ISOLATION_FOREST_AVAILABLE = False


class MLEngine:
    def __init__(self, models_dir: str = "zenith_knowledge/models"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.models: Dict[str, Any] = {}
        self.scalers: Dict[str, Any] = {}
        self.encoders: Dict[str, Any] = {}
        self.training_history: Dict[str, Dict[str, Any]] = {}

    def classify(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        model_type: str = "auto",
    ) -> Dict[str, Any]:
        if not SKLEARN_AVAILABLE:
            return {"error": "scikit-learn not installed"}

        y_train_encoded = y_train.astype(str)
        le = LabelEncoder()
        y_train_encoded = le.fit_transform(y_train_encoded)
        y_test_encoded = le.transform(y_test.astype(str))

        scaler = SklearnStandardScaler()
        X_train_scaled = scaler.fit_transform(X_train.fillna(0))
        X_test_scaled = scaler.transform(X_test.fillna(0))

        models = self._get_classification_models(model_type)
        best_model = None
        best_score = 0
        best_name = ""
        results = {}

        for name, model in models.items():
            try:
                model.fit(X_train_scaled, y_train_encoded)
                y_pred = model.predict(X_test_scaled)
                score = accuracy_score(y_test_encoded, y_pred)
                results[name] = {
                    "accuracy": round(score, 4),
                    "report": classification_report(
                        y_test_encoded, y_pred, output_dict=True
                    ),
                }

                if score > best_score:
                    best_score = score
                    best_model = model
                    best_name = name
            except Exception as e:
                results[name] = {"error": str(e)}

        if best_model is not None:
            self.models["classifier"] = best_model
            self.scalers["classifier"] = scaler
            self.encoders["classifier"] = le
            self.training_history["classifier"] = {
                "model": best_name,
                "accuracy": best_score,
                "train_size": len(X_train),
                "test_size": len(X_test),
            }

        return {
            "best_model": best_name,
            "best_accuracy": round(best_score, 4),
            "all_results": results,
            "training_history": self.training_history["classifier"],
        }

    def regress(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        model_type: str = "auto",
    ) -> Dict[str, Any]:
        if not SKLEARN_AVAILABLE:
            return {"error": "scikit-learn not installed"}

        scaler = SklearnStandardScaler()
        X_train_scaled = scaler.fit_transform(X_train.fillna(0))
        X_test_scaled = scaler.transform(X_test.fillna(0))

        models = self._get_regression_models(model_type)
        best_model = None
        best_score = float("inf")
        best_name = ""
        results = {}

        for name, model in models.items():
            try:
                model.fit(X_train_scaled, y_train)
                y_pred = model.predict(X_test_scaled)
                rmse = mean_squared_error(y_test, y_pred, squared=False)
                r2 = r2_score(y_test, y_pred)
                results[name] = {
                    "rmse": round(rmse, 4),
                    "r2_score": round(r2, 4),
                }

                if rmse < best_score:
                    best_score = rmse
                    best_model = model
                    best_name = name
            except Exception as e:
                results[name] = {"error": str(e)}

        if best_model is not None:
            self.models["regressor"] = best_model
            self.scalers["regressor"] = scaler
            self.training_history["regressor"] = {
                "model": best_name,
                "rmse": round(best_score, 4),
                "r2_score": round(
                    r2_score(y_test, best_model.predict(X_test_scaled)), 4
                ),
                "train_size": len(X_train),
                "test_size": len(X_test),
            }

        return {
            "best_model": best_name,
            "best_rmse": round(best_score, 4),
            "all_results": results,
            "training_history": self.training_history["regressor"],
        }

    def cluster(
        self, X: pd.DataFrame, n_clusters: int = 3, method: str = "kmeans"
    ) -> Dict[str, Any]:
        if not SKLEARN_AVAILABLE:
            return {"error": "scikit-learn not installed"}

        scaler = SklearnStandardScaler()
        X_scaled = scaler.fit_transform(X.fillna(0))

        if method == "kmeans":
            model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        elif method == "dbscan":
            model = DBSCAN(eps=0.5, min_samples=5)
        else:
            model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)

        labels = model.fit_predict(X_scaled)

        unique_labels = np.unique(labels)
        cluster_sizes = {int(label): int(np.sum(labels == label)) for label in unique_labels}

        result = {
            "method": method,
            "n_clusters": len(unique_labels),
            "cluster_sizes": cluster_sizes,
            "labels": labels.tolist(),
            "inertia": model.inertia_ if hasattr(model, "inertia_") else None,
        }

        if hasattr(model, "labels_"):
            self.models["clusterer"] = model
        self.scalers["clusterer"] = scaler

        return result

    def detect_anomalies(
        self, X: pd.DataFrame, contamination: float = 0.1
    ) -> Dict[str, Any]:
        if not SKLEARN_AVAILABLE or not ISOLATION_FOREST_AVAILABLE:
            return {"error": "scikit-learn not installed"}

        scaler = SklearnStandardScaler()
        X_scaled = scaler.fit_transform(X.fillna(0))

        model = IsolationForest(contamination=contamination, random_state=42)
        labels = model.fit_predict(X_scaled)

        anomaly_indices = np.where(labels == -1)[0]
        normal_indices = np.where(labels == 1)[0]

        result = {
            "total_records": len(X),
            "anomalies_detected": len(anomaly_indices),
            "normal_records": len(normal_indices),
            "anomaly_percentage": round(len(anomaly_indices) / len(X) * 100, 2),
            "anomaly_indices": anomaly_indices.tolist(),
            "anomaly_scores": model.score_samples(X_scaled).tolist(),
        }

        self.models["anomaly_detector"] = model
        self.scalers["anomaly_detector"] = scaler

        return result

    def reduce_dimensions(
        self, X: pd.DataFrame, n_components: int = 2, method: str = "pca"
    ) -> Dict[str, Any]:
        if not SKLEARN_AVAILABLE:
            return {"error": "scikit-learn not installed"}

        scaler = SklearnStandardScaler()
        X_scaled = scaler.fit_transform(X.fillna(0))

        if method == "pca":
            model = PCA(n_components=n_components)
        else:
            model = PCA(n_components=n_components)

        transformed = model.fit_transform(X_scaled)

        explained_variance = (
            model.explained_variance_ratio_.tolist()
            if hasattr(model, "explained_variance_ratio_")
            else []
        )

        return {
            "method": method,
            "n_components": n_components,
            "explained_variance": explained_variance,
            "transformed_shape": transformed.shape,
            "components": transformed.tolist(),
        }

    def save_model(self, name: str, path: str = None) -> str:
        path = path or str(self.models_dir / f"{name}.pkl")
        os.makedirs(os.path.dirname(path), exist_ok=True)

        with open(path, "wb") as f:
            pickle.dump(
                {
                    "model": self.models.get(name),
                    "scaler": self.scalers.get(name),
                    "encoder": self.encoders.get(name),
                },
                f,
            )
        return path

    def load_model(self, name: str, path: str = None) -> bool:
        path = path or str(self.models_dir / f"{name}.pkl")

        if not os.path.exists(path):
            return False

        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            self.models[name] = data["model"]
            self.scalers[name] = data["scaler"]
            self.encoders[name] = data["encoder"]
            return True
        except Exception as e:
            logger.error(f"Failed to load model {name}: {e}")
            return False

    def get_models_info(self) -> Dict[str, Any]:
        return {
            "loaded_models": list(self.models.keys()),
            "training_history": self.training_history,
            "models_dir": str(self.models_dir),
        }

    def _get_classification_models(self, model_type: str) -> Dict[str, Any]:
        models = {
            "logistic_regression": LogisticRegression(max_iter=1000),
            "random_forest": RandomForestClassifier(n_estimators=100, random_state=42),
            "gradient_boosting": GradientBoostingClassifier(
                n_estimators=100, random_state=42
            ),
        }

        if model_type == "auto":
            return models
        return {model_type: models.get(model_type, models["random_forest"])}

    def _get_regression_models(self, model_type: str) -> Dict[str, Any]:
        models = {
            "linear_regression": LinearRegression(),
            "ridge": Ridge(),
            "lasso": Lasso(),
            "random_forest": RandomForestRegressor(n_estimators=100, random_state=42),
            "gradient_boosting": GradientBoostingRegressor(
                n_estimators=100, random_state=42
            ),
        }

        if model_type == "auto":
            return models
        return {model_type: models.get(model_type, models["gradient_boosting"])}