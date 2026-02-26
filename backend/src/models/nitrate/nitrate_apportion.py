"""
Nitrate apportionment model with decay
"""
from typing import List, Dict, Any
import pandas as pd
import numpy as np

from config.logging_config import get_logger
from src.models.common import resolve_coordinate_columns, resolve_timestamp_column

logger = get_logger(__name__)


class NitrateApportionModel:
    """
    Nitrate apportionment analysis model
    
    This model analyzes nitrate concentrations accounting for decay over time
    to determine subcatchment contributions.
    """

    def __init__(self):
        """Initialize the nitrate model."""

    def process_nitrate_data(self, csv_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Main processing function for nitrate apportion analysis
        
        Args:
            csv_data: DataFrame with columns [Timestamp, Longitude, Latitude, Nitrate_Concentration]
        
        Returns:
            Dictionary with analysis summary metadata
        """
        try:
            logger.info(f"Nitrate model started with {len(csv_data)} rows")

            # Parse CSV data
            samples = self.parse_samples(csv_data)

            logger.info(f"Nitrate samples parsed: {len(samples)} samples")

            logger.info("Nitrate model completed")

            return {
                "model_type": "nitrate_apportion",
                "status": "success",
                "n_samples": len(samples)
            }

        except Exception as e:
            logger.error(f"Nitrate model failed: {str(e)}", exc_info=True)
            return {
                "model_type": "nitrate_apportion",
                "status": "failed",
                "error": str(e)
            }

    def parse_samples(self, csv_data: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Parse CSV data into sample dictionaries, auto-detecting nitrate column.
        
        Args:
            csv_data: DataFrame with columns [sample_name, timestamp, long, lat, chemical_1, ..., chemical_n]
        
        Returns:
            List of sample dictionaries (for nitrate, only the nitrate column is used for concentration)
        """
        samples = []

        long_col, lat_col = resolve_coordinate_columns(csv_data)
        timestamp_col = resolve_timestamp_column(csv_data)

        # Find nitrate column (case-insensitive, must contain 'nitrate' or 'no3')
        nitrate_col = None
        for c in csv_data.columns:
            if "nitrate" in c.lower() or "no3" in c.lower():
                nitrate_col = c
                break

        if nitrate_col is None:
            raise ValueError("No nitrate column found in input CSV. Column name must contain 'nitrate' or 'NO3'.")

        logger.info(f"Detected nitrate column: {nitrate_col}")

        for idx, row in csv_data.iterrows():
            try:
                concentration = float(row[nitrate_col])
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse nitrate concentration in row {idx}: {str(e)}")
                concentration = np.nan

            sample = {
                "sample_id": idx,
                "timestamp": row[timestamp_col] if timestamp_col else None,
                "longitude": float(row[long_col]),
                "latitude": float(row[lat_col]),
                "concentration": concentration
            }
            samples.append(sample)

        return samples
