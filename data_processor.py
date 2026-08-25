import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import json
import logging

logger = logging.getLogger(__name__)


class DataProcessor:
    def __init__(self):
        self.data = None
        self.processed_data = None
        self.features = None
        self.target = None
        self.metadata = {}

    def load_data(self, file_path: str) -> pd.DataFrame:
        path = Path(file_path)
        ext = path.suffix.lower()

        if ext == ".csv":
            self.data = pd.read_csv(file_path, low_memory=False)
        elif ext in (".xlsx", ".xls"):
            self.data = pd.read_excel(file_path, engine="openpyxl")
        elif ext == ".json":
            self.data = pd.read_json(file_path)
        elif ext == ".parquet":
            self.data = pd.read_parquet(file_path)
        else:
            raise ValueError(f"Unsupported file type: {ext}")

        self.metadata["source"] = str(file_path)
        self.metadata["rows"] = len(self.data)
        self.metadata["columns"] = list(self.data.columns)
        self.metadata["dtypes"] = {col: str(dtype) for col, dtype in self.data.dtypes.items()}

        logger.info(f"Loaded {len(self.data)} rows, {len(self.data.columns)} columns from {file_path}")
        return self.data

    def clean_data(self, drop_duplicates: bool = True, missing_strategy: str = "median") -> pd.DataFrame:
        if self.data is None:
            raise ValueError("No data loaded. Call load_data() first.")

        df = self.data.copy()

        if drop_duplicates:
            before = len(df)
            df = df.drop_duplicates()
            self.metadata["duplicates_removed"] = before - len(df)

        numeric_cols = df.select_dtypes(include=[np.number]).columns
        categorical_cols = df.select_dtypes(include=["object", "category"]).columns

        if missing_strategy == "median":
            for col in numeric_cols:
                df[col] = df[col].fillna(df[col].median())
        elif missing_strategy == "mean":
            for col in numeric_cols:
                df[col] = df[col].fillna(df[col].mean())
        elif missing_strategy == "drop":
            df = df.dropna()
        elif missing_strategy == "mode":
            for col in categorical_cols:
                df[col] = df[col].fillna(df[col].mode()[0] if not df[col].mode().empty else "Unknown")
            for col in numeric_cols:
                df[col] = df[col].fillna(df[col].median())

        for col in categorical_cols:
            df[col] = df[col].fillna("Unknown")

        self.processed_data = df
        self.metadata["missing_values_after"] = int(df.isnull().sum().sum())
        return df

    def detect_column_types(self) -> Dict[str, List[str]]:
        if self.processed_data is None:
            self.clean_data()

        df = self.processed_data
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        categorical_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
        datetime_cols = []

        for col in df.columns:
            if df[col].dtype == "object":
                try:
                    pd.to_datetime(df[col], errors="raise")
                    datetime_cols.append(col)
                except Exception:
                    pass

        return {
            "numeric": numeric_cols,
            "categorical": categorical_cols,
            "datetime": datetime_cols,
            "text": [c for c in categorical_cols if c not in datetime_cols],
        }

    def engineer_features(self, target_column: Optional[str] = None) -> pd.DataFrame:
        if self.processed_data is None:
            self.clean_data()

        df = self.processed_data.copy()
        numeric_cols = df.select_dtypes(include=[np.number]).columns

        if target_column and target_column in df.columns:
            self.target = df[target_column]
            feature_cols = [c for c in numeric_cols if c != target_column]
        else:
            feature_cols = list(numeric_cols)

        for col in feature_cols:
            df[f"{col}_log"] = np.log1p(df[col].abs())
            df[f"{col}_squared"] = df[col] ** 2
            df[f"{col}_rank"] = df[col].rank()

        if len(feature_cols) >= 2:
            for i, col1 in enumerate(feature_cols[:5]):
                for col2 in feature_cols[i + 1:i + 3]:
                    df[f"{col1}_x_{col2}"] = df[col1] * df[col2]
                    if df[col2].std() > 0:
                        df[f"{col1}_per_{col2}"] = df[col1] / df[col2].replace(0, np.nan)

        self.features = df[feature_cols]
        self.metadata["feature_count"] = len(feature_cols)
        self.metadata["engineered_features"] = len(df.columns) - len(feature_cols)
        return df

    def get_summary(self) -> Dict[str, Any]:
        if self.processed_data is None:
            self.clean_data()

        df = self.processed_data
        column_types = self.detect_column_types()

        return {
            "shape": df.shape,
            "columns": list(df.columns),
            "column_types": column_types,
            "missing_values": int(df.isnull().sum().sum()),
            "missing_percentage": round(df.isnull().sum().sum() / (df.shape[0] * df.shape[1]) * 100, 2),
            "duplicates": self.metadata.get("duplicates_removed", 0),
            "basic_stats": df.describe().to_dict(),
            "metadata": self.metadata,
        }

    def train_test_split(
        self, target_column: str, test_size: float = 0.2, random_state: int = 42
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
        from sklearn.model_selection import train_test_split as sklearn_split

        if self.features is None:
            self.engineer_features(target_column=target_column)

        X = self.features.fillna(0)
        y = self.target if self.target is not None else self.processed_data[target_column]

        X_train, X_test, y_train, y_test = sklearn_split(
            X, y, test_size=test_size, random_state=random_state
        )

        return X_train, X_test, y_train, y_test

    def save_processed(self, output_path: str = None) -> str:
        if self.processed_data is None:
            raise ValueError("No processed data to save.")

        data_dir = Path("data")
        data_dir.mkdir(parents=True, exist_ok=True)

        if output_path is None:
            output_path = str(data_dir / "processed_data.csv")

        path = Path(output_path)
        if not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)

        ext = path.suffix.lower()

        if ext == ".csv":
            self.processed_data.to_csv(output_path, index=False)
        elif ext in (".xlsx", ".xls"):
            self.processed_data.to_excel(output_path, index=False)
        elif ext == ".json":
            self.processed_data.to_json(output_path, orient="records", indent=2)
        else:
            self.processed_data.to_csv(output_path, index=False)

        return f"Saved processed data to {output_path}"