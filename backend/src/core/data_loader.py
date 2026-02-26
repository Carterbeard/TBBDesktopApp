"""Data loading and validation utilities."""

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from config.constants import COORDINATE_RANGES, REQUIRED_COLUMNS

logger = logging.getLogger(__name__)


class DataValidationError(Exception):
    """Raised when uploaded data fails validation."""


class DataLoader:
    """Loads and validates sample data from CSV/JSON/TXT files."""

    def __init__(self, file_path: Optional[Path] = None, max_file_size_mb: int = 50):
        self.file_path = Path(file_path) if file_path else None
        self.max_file_size_mb = max_file_size_mb
        self.data: Optional[pd.DataFrame] = None

    def load(self, file_path: Optional[Path] = None) -> pd.DataFrame:
        """Read input file into a DataFrame and run baseline validation."""
        resolved_path = Path(file_path) if file_path else self.file_path
        if resolved_path is None:
            raise DataValidationError("No input file path provided")

        self.file_path = resolved_path
        self._validate_file_exists()
        self._validate_file_size()

        suffix = self.file_path.suffix.lower()
        try:
            if suffix == ".csv":
                dataframe = pd.read_csv(self.file_path)
            elif suffix == ".json":
                dataframe = pd.read_json(self.file_path)
            elif suffix == ".txt":
                dataframe = pd.read_csv(self.file_path, sep=None, engine="python")
            else:
                raise DataValidationError(f"Unsupported file format: {suffix}")
        except DataValidationError:
            raise
        except Exception as error:
            raise DataValidationError(f"Failed to parse file: {error}") from error

        self.data = self.validate(dataframe)
        logger.info("Loaded %s samples from %s", len(self.data), self.file_path)
        return self.data

    def validate(self, dataframe: pd.DataFrame, parameters=None) -> pd.DataFrame:
        """Validate required columns and value ranges; return normalized DataFrame."""
        if dataframe is None or dataframe.empty:
            raise DataValidationError("File contains no data")

        validated = dataframe.copy()
        validated = self._normalize_columns(validated)

        missing_columns = [column for column in REQUIRED_COLUMNS if column not in validated.columns]
        if missing_columns:
            raise DataValidationError(
                f"Missing required columns: {', '.join(missing_columns)}. "
                f"Required: {', '.join(REQUIRED_COLUMNS)}"
            )

        self._validate_coordinates(validated)
        self._validate_timestamps(validated)
        self._validate_chemical_columns(validated)

        return validated

    def get_sample_count(self) -> int:
        return len(self.data) if self.data is not None else 0

    def get_summary(self) -> dict:
        if self.data is None:
            return {}

        chemistry_columns = [
            column for column in self.data.columns if column not in set(REQUIRED_COLUMNS)
        ]

        return {
            "sample_count": len(self.data),
            "required_columns": REQUIRED_COLUMNS,
            "chemistry_columns": chemistry_columns,
            "coordinate_bounds": {
                "long_min": float(self.data["Long"].min()),
                "long_max": float(self.data["Long"].max()),
                "lat_min": float(self.data["Lat"].min()),
                "lat_max": float(self.data["Lat"].max()),
            },
            "date_range": {
                "start": str(pd.to_datetime(self.data["timestamp"]).min()),
                "end": str(pd.to_datetime(self.data["timestamp"]).max()),
            },
        }

    def _validate_file_exists(self) -> None:
        if self.file_path is None or not self.file_path.exists():
            raise DataValidationError(f"File not found: {self.file_path}")

    def _validate_file_size(self) -> None:
        if self.file_path is None:
            raise DataValidationError("No file path set")

        size_mb = self.file_path.stat().st_size / (1024 * 1024)
        if size_mb > self.max_file_size_mb:
            raise DataValidationError(
                f"File too large: {size_mb:.1f}MB (max {self.max_file_size_mb}MB)"
            )

    def _normalize_columns(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        aliases = {
            "longitude": "Long",
            "long": "Long",
            "lon": "Long",
            "lng": "Long",
            "latitude": "Lat",
            "lat": "Lat",
            "time_stamp": "timestamp",
            "datetime": "timestamp",
            "time": "timestamp",
            "sampleid": "Sample_id",
            "sample id": "Sample_id",
            "sample_id": "Sample_id",
        }

        rename_map = {}
        for column in dataframe.columns:
            normalized = column.strip().lower().replace("-", "_")
            if normalized in aliases:
                rename_map[column] = aliases[normalized]

        if rename_map:
            dataframe = dataframe.rename(columns=rename_map)

        return dataframe

    def _validate_coordinates(self, dataframe: pd.DataFrame) -> None:
        long_min, long_max = COORDINATE_RANGES["Long"]
        lat_min, lat_max = COORDINATE_RANGES["Lat"]

        missing_coords = dataframe[dataframe["Long"].isna() | dataframe["Lat"].isna()]
        if not missing_coords.empty:
            raise DataValidationError(
                f"Found {len(missing_coords)} samples with missing coordinates"
            )

        bad_long = dataframe[(dataframe["Long"] < long_min) | (dataframe["Long"] > long_max)]
        if not bad_long.empty:
            raise DataValidationError(
                f"Found {len(bad_long)} samples with invalid longitude (must be {long_min} to {long_max})"
            )

        bad_lat = dataframe[(dataframe["Lat"] < lat_min) | (dataframe["Lat"] > lat_max)]
        if not bad_lat.empty:
            raise DataValidationError(
                f"Found {len(bad_lat)} samples with invalid latitude (must be {lat_min} to {lat_max})"
            )

    def _validate_timestamps(self, dataframe: pd.DataFrame) -> None:
        missing_timestamps = dataframe[dataframe["timestamp"].isna()]
        if not missing_timestamps.empty:
            raise DataValidationError(
                f"Found {len(missing_timestamps)} samples with missing timestamps"
            )

        try:
            pd.to_datetime(dataframe["timestamp"])
        except Exception as error:
            raise DataValidationError(f"Invalid timestamp format: {error}") from error

    def _validate_chemical_columns(self, dataframe: pd.DataFrame) -> None:
        chemistry_columns = [column for column in dataframe.columns if column not in REQUIRED_COLUMNS]
        if not chemistry_columns:
            raise DataValidationError(
                "No chemical concentration columns found. "
                "Provide at least one chemical column in addition to required fields."
            )

        for column in chemistry_columns:
            numeric_series = pd.to_numeric(dataframe[column], errors="coerce")
            if numeric_series.isna().all():
                continue

            negative_count = int((numeric_series < 0).sum())
            if negative_count > 0:
                raise DataValidationError(
                    f"Found {negative_count} negative values in '{column}' (concentrations must be >= 0)"
                )
