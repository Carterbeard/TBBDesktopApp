"""
Analysis pipeline orchestrator
"""
from typing import Dict, Any, Callable, Optional
from pathlib import Path
import uuid

from config.logging_config import get_logger
from config.schemas import ProcessingParameters
from config.constants import ProcessingStatus
from src.core.data_loader import DataLoader
from src.core.analysis_engine import AnalysisEngine

logger = get_logger(__name__)


class AnalysisPipeline:
    """Orchestrates the complete analysis pipeline"""
    
    def __init__(self):
        self.loader = DataLoader()
        self.engine = AnalysisEngine()
    
    def run(
        self,
        input_file: Path,
        parameters: ProcessingParameters,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Execute analysis pipeline
        
        Args:
            input_file: Path to input CSV file
            parameters: Processing parameters
            progress_callback: Optional callback for progress updates
        
        Returns:
            Dictionary with job_id, status, outputs, and summary
        """
        job_id = str(uuid.uuid4())
        
        logger.info("pipeline_started", job_id=job_id)
        
        try:
            # Load data (0-10%)
            self._update_progress(progress_callback, 5, "Loading data...")
            data = self.loader.load(input_file)
            
            # Validate (10-20%)
            self._update_progress(progress_callback, 10, "Validating data...")
            validated_data = self.loader.validate(data, parameters)
            
            # Run analysis (20-90%)
            # Your models handle progress from 30-90%
            self._update_progress(progress_callback, 20, "Preparing analysis...")
            results = self.engine.run_analysis(
                csv_data=validated_data,
                parameters=parameters,
                progress_callback=progress_callback
            )
            
            # Complete (100%)
            self._update_progress(progress_callback, 100, "Complete!")
            
            # Add metadata
            results['job_id'] = job_id
            results['status'] = ProcessingStatus.COMPLETED
            
            logger.info("pipeline_completed", job_id=job_id)
            return results
            
        except Exception as e:
            logger.error("pipeline_failed", job_id=job_id, error=str(e), exc_info=True)
            raise
    
    def _update_progress(self, callback: Optional[Callable], progress: float, message: str):
        """Update progress if callback provided"""
        if callback:
            callback(progress, message)