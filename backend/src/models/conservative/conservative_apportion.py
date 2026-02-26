"""
Conservative tracer apportionment model
"""
from typing import List, Dict, Any
import pandas as pd
import numpy as np

from config.logging_config import get_logger
from src.models.common import resolve_coordinate_columns

logger = get_logger(__name__)


class ConservativeApportionModel:
    """
    Conservative tracer apportionment analysis model
    
    This model analyzes conservative tracers (chemicals that don't decay)
    to determine subcatchment contributions.
    """

    def __init__(self):
        """Initialize the conservative model."""

    def process_conservative_data(self, csv_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Main processing function for conservative apportion analysis
        
        Args:
            csv_data: DataFrame with columns [Longitude, Latitude, and chemical concentrations]
        
        Returns:
            Dictionary with analysis summary metadata
        """
        try:
            logger.info(f"Conservative model started with {len(csv_data)} rows")

            # Parse CSV data
            samples = self.parse_samples(csv_data)

            logger.info(f"Conservative samples parsed: {len(samples)} samples")

            logger.info("Conservative model completed")

            return {
                "model_type": "conservative_apportion",
                "status": "success",
                "n_samples": len(samples),
                "n_chemicals": len(samples[0]["chemicals"]) if samples else 0
            }

        except Exception as e:
            logger.error(f"Conservative model failed: {str(e)}", exc_info=True)
            return {
                "model_type": "conservative_apportion",
                "status": "failed",
                "error": str(e)
            }

    def parse_samples(self, csv_data: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Parse CSV data into sample dictionaries, auto-detecting chemical columns.
        
        Args:
            csv_data: DataFrame with columns [sample_name, timestamp, long, lat, chemical_1, ..., chemical_n]
        
        Returns:
            List of sample dictionaries with all chemical concentrations
        """
        samples = []

        long_col, lat_col = resolve_coordinate_columns(csv_data)

        # Exclude known non-chemical columns
        non_chem_cols = {"sample_name", "timestamp", "long", "lat", "longitude", "latitude", "sample_id"}
        chemical_columns = [c for c in csv_data.columns if c.lower() not in non_chem_cols]

        logger.info(f"Detected chemical columns: {chemical_columns}")

        for idx, row in csv_data.iterrows():
            sample = {
                "sample_id": idx,
                "longitude": float(row[long_col]),
                "latitude": float(row[lat_col]),
                "chemicals": {}
            }

            for chem in chemical_columns:
                try:
                    sample["chemicals"][chem] = float(row[chem])
                except (ValueError, TypeError) as e:
                    logger.warning(f"Could not parse chemical value for '{chem}' in row {idx}: {str(e)}")
                    sample["chemicals"][chem] = np.nan

            samples.append(sample)

        return samples
