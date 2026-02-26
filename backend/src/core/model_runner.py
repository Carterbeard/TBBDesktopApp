"""
Model runner that wraps your existing models for the pipeline
"""
from pathlib import Path
from typing import Dict, Any, Optional, Callable
import pandas as pd
import re

from config.logging_config import get_logger
from config.schemas import ProcessingParameters
from config.constants import CONSERVATIVE_TRACER_KEYWORDS
from src.models.conservative.conservative_apportion import ConservativeApportionModel
from src.models.nitrate.nitrate_apportion import NitrateApportionModel

logger = get_logger(__name__)


class ModelRunner:
    """
    Wrapper for existing models that integrates with the pipeline.

    This class:
    1. Determines which models should run based on detected tracers
    2. Runs one or more models
    3. Returns standardized, multi-model results
    """

    def __init__(self):
        self.conservative_model = ConservativeApportionModel()
        self.nitrate_model = NitrateApportionModel()

    @classmethod
    def determine_model_type(cls, csv_data: pd.DataFrame) -> str:
        flags = cls._determine_models_static(csv_data)
        if flags["nitrate"] and flags["conservative"]:
            return "combined"
        if flags["nitrate"]:
            return "nitrate"
        return "conservative"

    @classmethod
    def build_contributions_csv(cls, dataframe: pd.DataFrame, output_path: Path) -> tuple[pd.DataFrame, str]:
        result = dataframe.copy()

        base_columns = ["Sample_id", "timestamp", "Long", "Lat"]
        existing_base = [column for column in base_columns if column in result.columns]

        chemistry_columns = [column for column in result.columns if column not in existing_base]
        nitrate_columns = [column for column in chemistry_columns if "nitrate" in column.lower() or "no3" in column.lower()]
        conservative_columns = [column for column in chemistry_columns if column not in nitrate_columns]

        conservative_contribution_columns: list[str] = []

        if nitrate_columns:
            result["nitrate_contribution"] = pd.to_numeric(result[nitrate_columns].mean(axis=1), errors="coerce")

        for index, conservative_column in enumerate(conservative_columns, start=1):
            contribution_column = f"conservative_contribution_{index}"
            result[contribution_column] = pd.to_numeric(result[conservative_column], errors="coerce")
            conservative_contribution_columns.append(contribution_column)

        final_columns = existing_base + chemistry_columns
        if "nitrate_contribution" in result.columns:
            final_columns.append("nitrate_contribution")
        final_columns.extend(conservative_contribution_columns)

        if not final_columns:
            final_columns = list(result.columns)

        contributions_df = result[final_columns].copy()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        contributions_df.to_csv(output_path, index=False)

        model_type = "conservative"
        if "nitrate_contribution" in contributions_df.columns and conservative_contribution_columns:
            model_type = "combined"
        elif "nitrate_contribution" in contributions_df.columns:
            model_type = "nitrate"

        return contributions_df, model_type

    # Public API
    def run(
        self,
        csv_data: pd.DataFrame,
        parameters: ProcessingParameters,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> Dict[str, Any]:

        logger.info("Model runner started")
        self._update_progress(progress_callback, 30, "Detecting tracers...")

        model_flags = self._determine_models(csv_data)

        if not any(model_flags.values()):
            raise ValueError("No supported nitrate or conservative tracer columns detected.")

        results: Dict[str, Dict[str, Any]] = {}

        # Run nitrate model
        if model_flags["nitrate"]:
            logger.info("Running nitrate model")
            self._update_progress(progress_callback, 40, "Running nitrate apportionment model...")

            nitrate_result = self.nitrate_model.process_nitrate_data(csv_data)

            if nitrate_result.get("status") == "failed":
                raise Exception(f"Nitrate model failed: {nitrate_result.get('error', 'Unknown error')}")

            results["nitrate"] = nitrate_result

        # Run conservative model
        if model_flags["conservative"]:
            logger.info(f"Running conservative model with {len(csv_data)} rows")
            self._update_progress(progress_callback, 55, "Running conservative apportionment model...")

            conservative_result = self.conservative_model.process_conservative_data(csv_data)

            if conservative_result.get("status") == "failed":
                raise Exception(
                    f"Conservative model failed: {conservative_result.get('error', 'Unknown error')}"
                )

            results["conservative"] = conservative_result

        self._update_progress(progress_callback, 90, "Finalizing results...")

        return {
            "models_run": list(results.keys()),
            "summary": {
                "total_samples": len(csv_data),
                "n_models": len(results),
                "models": {
                    name: {
                        "model_type": res.get("model_type"),
                        "n_samples": res.get("n_samples", len(csv_data)),
                        "n_chemicals": res.get("n_chemicals", 0),
                    }
                    for name, res in results.items()
                },
            },
            "metadata": {
                "model_version": "v1.2",
                "parameters": parameters.model_dump(),
            },
        }

    # Helper methods
    def _determine_models(self, csv_data: pd.DataFrame) -> Dict[str, bool]:
        return self._determine_models_static(csv_data)

    @classmethod
    def _determine_models_static(cls, csv_data: pd.DataFrame) -> Dict[str, bool]:
        """
        Determine which models should be run based on detected columns.
        """
        normalized_columns = [cls._normalize_column(c) for c in csv_data.columns]

        has_nitrate = any(
            "nitrate" in col or "no3" in col
            for col in normalized_columns
        )

        # FIX: Match whole words only, not substrings
        has_conservative = any(
            any(
                # Use word boundaries: keyword must be a complete word
                keyword == word
                for word in col.split()  # Split column into words
            )
            for keyword in CONSERVATIVE_TRACER_KEYWORDS
            for col in normalized_columns
        )

        logger.info(
            f"Model detection complete: nitrate_detected={has_nitrate}, "
            f"conservative_detected={has_conservative}"
        )

        return {
            "nitrate": has_nitrate,
            "conservative": has_conservative,
        }

    @staticmethod
    def _normalize_column(col: str) -> str:
        # Replace non-alphanumeric chars with space and lowercase
        return re.sub(r"[^a-z0-9δ]+", " ", col.lower()).strip()

    def _update_progress(
        self,
        callback: Optional[Callable[[float, str], None]],
        progress: float,
        message: str,
    ):
        if callback:
            callback(progress, message)
