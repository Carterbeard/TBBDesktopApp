"""
Analysis engine that orchestrates model execution
"""
from typing import Dict, Any, Optional, Callable
import pandas as pd

from config.logging_config import get_logger
from config.schemas import ProcessingParameters
from src.core.model_runner import ModelRunner

logger = get_logger(__name__)


class AnalysisEngine:
    """Orchestrates analysis using existing models"""
    
    def __init__(self):
        self.model_runner = ModelRunner()
    
    def run_analysis(
        self,
        csv_data: pd.DataFrame,
        parameters: ProcessingParameters,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Run complete analysis using your existing models
        
        Args:
            csv_data: Input DataFrame
            parameters: Processing parameters
            progress_callback: Optional progress callback
        
        Returns:
            Analysis results with outputs, summary, and metadata
        """
        logger.info("analysis_started")
        
        # Run the model
        results = self.model_runner.run(
            csv_data=csv_data,
            parameters=parameters,
            progress_callback=progress_callback
        )
        
        logger.info("analysis_completed")
        
        return results