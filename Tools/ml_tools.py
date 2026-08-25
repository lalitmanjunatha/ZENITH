import logging
from typing import Dict, Any, Optional, List
from livekit.agents import function_tool
import asyncio
import json
from pathlib import Path

logger = logging.getLogger(__name__)


@function_tool()
async def train_classification_model(
    data_path: str,
    target_column: str,
    test_size: float = 0.2,
) -> str:
    try:
        from data_processor import DataProcessor
        from ml_engine import MLEngine

        dp = DataProcessor()
        dp.load_data(data_path)
        dp.clean_data()
        X_train, X_test, y_train, y_test = dp.train_test_split(
            target_column, test_size=test_size
        )

        ml = MLEngine()
        result = ml.classify(X_train, y_train, X_test, y_test)

        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return f"❌ Classification training failed: {str(e)}"


@function_tool()
async def train_regression_model(
    data_path: str,
    target_column: str,
    test_size: float = 0.2,
) -> str:
    try:
        from data_processor import DataProcessor
        from ml_engine import MLEngine

        dp = DataProcessor()
        dp.load_data(data_path)
        dp.clean_data()
        X_train, X_test, y_train, y_test = dp.train_test_split(
            target_column, test_size=test_size
        )

        ml = MLEngine()
        result = ml.regress(X_train, y_train, X_test, y_test)

        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return f"❌ Regression training failed: {str(e)}"


@function_tool()
async def cluster_data(
    data_path: str,
    n_clusters: int = 3,
    target_column: Optional[str] = None,
) -> str:
    try:
        from data_processor import DataProcessor
        from ml_engine import MLEngine

        dp = DataProcessor()
        dp.load_data(data_path)
        dp.clean_data()

        if target_column and target_column in dp.processed_data.columns:
            features = dp.processed_data.select_dtypes(include=["number"])
            features = features.drop(columns=[target_column], errors="ignore")
        else:
            features = dp.processed_data.select_dtypes(include=["number"])

        ml = MLEngine()
        result = ml.cluster(features, n_clusters=n_clusters)

        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return f"❌ Clustering failed: {str(e)}"


@function_tool()
async def detect_anomalies(
    data_path: str,
    contamination: float = 0.1,
) -> str:
    try:
        from data_processor import DataProcessor
        from ml_engine import MLEngine

        dp = DataProcessor()
        dp.load_data(data_path)
        dp.clean_data()

        features = dp.processed_data.select_dtypes(include=["number"])
        ml = MLEngine()
        result = ml.detect_anomalies(features, contamination=contamination)

        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return f"❌ Anomaly detection failed: {str(e)}"


@function_tool()
async def analyze_data(data_path: str) -> str:
    try:
        from data_processor import DataProcessor

        dp = DataProcessor()
        dp.load_data(data_path)
        summary = dp.get_summary()

        return json.dumps(summary, indent=2, default=str)
    except Exception as e:
        return f"❌ Data analysis failed: {str(e)}"