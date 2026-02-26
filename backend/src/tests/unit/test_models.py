"""
Test the updated ModelRunner with multi-model support
"""
import pytest
from pathlib import Path
import pandas as pd

from src.core.model_runner import ModelRunner, CONSERVATIVE_TRACER_KEYWORDS
from config.schemas import ProcessingParameters


# Fixtures

@pytest.fixture
def sample_nitrate_data():
    """Sample data with nitrate column"""
    return pd.DataFrame({
        'Sample_id': ['S001', 'S002', 'S003'],
        'timestamp': ['2024-02-16T10:00:00Z'] * 3,
        'Long': [-1.234, -1.235, -1.236],
        'Lat': [51.123, 51.124, 51.125],
        'NO3': [5.2, 6.1, 4.8],
    })


@pytest.fixture
def sample_conservative_data():
    """Sample data with conservative tracers only"""
    return pd.DataFrame({
        'Sample_id': ['S001', 'S002', 'S003'],
        'Long': [-1.234, -1.235, -1.236],
        'Lat': [51.123, 51.124, 51.125],
        'Chloride': [10.5, 12.3, 9.8],
        'Calcium': [25.1, 28.4, 22.9],
    })


@pytest.fixture
def sample_mixed_data():
    """Sample data with both nitrate and conservative tracers"""
    return pd.DataFrame({
        'Sample_id': ['S001', 'S002', 'S003'],
        'timestamp': ['2024-02-16T10:00:00Z'] * 3,
        'Long': [-1.234, -1.235, -1.236],
        'Lat': [51.123, 51.124, 51.125],
        'NO3': [5.2, 6.1, 4.8],
        'Chloride': [10.5, 12.3, 9.8],
        'Sodium': [15.2, 16.8, 14.5],
    })


@pytest.fixture
def processing_parameters():
    """Standard processing parameters"""
    return ProcessingParameters(
        session_id="test-123",
        catchment_threshold_area=1.0
    )


# Model Detection Tests

class TestModelDetection:
    """Test the model detection logic"""
    
    def test_detect_nitrate_only(self, sample_nitrate_data):
        """Test detection with nitrate column only"""
        runner = ModelRunner()
        result = runner._determine_models(sample_nitrate_data)
        
        assert result['nitrate'] is True
        assert result['conservative'] is False
    
    def test_detect_conservative_only(self, sample_conservative_data):
        """Test detection with conservative tracers only"""
        runner = ModelRunner()
        result = runner._determine_models(sample_conservative_data)
        
        assert result['nitrate'] is False
        assert result['conservative'] is True
    
    def test_detect_both_models(self, sample_mixed_data):
        """Test detection with both nitrate and conservative tracers"""
        runner = ModelRunner()
        result = runner._determine_models(sample_mixed_data)
        
        assert result['nitrate'] is True
        assert result['conservative'] is True
    
    def test_detect_no_tracers(self):
        """Test detection with no supported tracers"""
        data = pd.DataFrame({
            'Sample_id': ['S001', 'S002'],
            'Long': [-1.234, -1.235],
            'Lat': [51.123, 51.124],
            'UnknownColumn': [1.0, 2.0]
        })
        
        runner = ModelRunner()
        result = runner._determine_models(data)
        
        assert result['nitrate'] is False
        assert result['conservative'] is False
    
    def test_nitrate_column_variations(self):
        """Test that different nitrate column names are detected"""
        runner = ModelRunner()
        
        test_cases = [
            'Nitrate',
            'nitrate_concentration',
            'NO3',
            'NO3_mg/L',
            'Nitrate-N',
            'NITRATE'
        ]
        
        for col_name in test_cases:
            data = pd.DataFrame({
                'Long': [-1.234],
                'Lat': [51.123],
                col_name: [5.2]
            })
            
            result = runner._determine_models(data)
            assert result['nitrate'] is True, f"Failed to detect nitrate column: {col_name}"
    
    def test_conservative_tracer_detection(self):
        """Test that various conservative tracers are detected"""
        runner = ModelRunner()
        
        test_cases = [
            'Chloride',
            'Cl',
            'Cl-',
            'Sodium',
            'Na+',
            'Calcium',
            'Ca2+',
            'Conductivity',
            'EC',
            'δ18O',
            'D18O'
        ]
        
        for col_name in test_cases:
            data = pd.DataFrame({
                'Long': [-1.234],
                'Lat': [51.123],
                col_name: [10.5]
            })
            
            result = runner._determine_models(data)
            assert result['conservative'] is True, f"Failed to detect conservative tracer: {col_name}"


class TestColumnNormalization:
    """Test column name normalization"""
    
    def test_normalize_basic(self):
        """Test basic normalization"""
        assert ModelRunner._normalize_column("Chloride") == "chloride"
        assert ModelRunner._normalize_column("NO3") == "no3"
    
    def test_normalize_with_special_chars(self):
        """Test normalization with special characters"""
        assert ModelRunner._normalize_column("Cl-") == "cl"
        assert ModelRunner._normalize_column("Ca2+") == "ca2"
        assert ModelRunner._normalize_column("NO3_mg/L") == "no3 mg l"
    
    def test_normalize_with_delta(self):
        """Test normalization preserves δ symbol"""
        assert "δ18o" in ModelRunner._normalize_column("δ18O")
        assert "δ2h" in ModelRunner._normalize_column("δ2H")
    
    def test_normalize_with_spaces_and_underscores(self):
        """Test normalization handles spaces and underscores"""
        assert ModelRunner._normalize_column("Nitrate_Concentration") == "nitrate concentration"
        assert ModelRunner._normalize_column("Nitrate Concentration") == "nitrate concentration"


# Integration Tests

class TestModelRunnerIntegration:
    """Integration tests for the complete ModelRunner"""
    
    def test_run_nitrate_only(
        self, 
        sample_nitrate_data, 
        processing_parameters, 
        tmp_path,
        monkeypatch
    ):
        """Test running nitrate model only"""
        # Mock the nitrate model
        def mock_process_nitrate(self, csv_data):
            return {
                "model_type": "nitrate_apportion",
                "status": "success",
                "n_samples": len(csv_data)
            }
        
        from src.models.nitrate import nitrate_apportion
        monkeypatch.setattr(
            nitrate_apportion.NitrateApportionModel,
            'process_nitrate_data',
            mock_process_nitrate
        )
        
        # Run model
        runner = ModelRunner()
        
        results = runner.run(
            csv_data=sample_nitrate_data,
            parameters=processing_parameters,
        )
        
        # Check results
        assert results['models_run'] == ['nitrate']
        
        # Check summary
        assert results['summary']['n_models'] == 1
        assert 'nitrate' in results['summary']['models']
    
    def test_run_conservative_only(
        self,
        sample_conservative_data,
        processing_parameters,
        tmp_path,
        monkeypatch
    ):
        """Test running conservative model only"""
        # Mock the conservative model
        def mock_process_conservative(self, csv_data):
            return {
                "model_type": "conservative_apportion",
                "status": "success",
                "n_samples": len(csv_data),
                "n_chemicals": 2
            }
        
        from src.models.conservative import conservative_apportion
        monkeypatch.setattr(
            conservative_apportion.ConservativeApportionModel,
            'process_conservative_data',
            mock_process_conservative
        )
        
        # Run model
        runner = ModelRunner()
        
        results = runner.run(
            csv_data=sample_conservative_data,
            parameters=processing_parameters,
        )
        
        # Check results
        assert results['models_run'] == ['conservative']
        
        # Check summary
        assert results['summary']['n_models'] == 1
        assert 'conservative' in results['summary']['models']
        assert results['summary']['models']['conservative']['n_chemicals'] == 2
    
    def test_run_both_models(
        self,
        sample_mixed_data,
        processing_parameters,
        tmp_path,
        monkeypatch
    ):
        """Test running both nitrate and conservative models"""
        # Mock both models
        def mock_process_nitrate(self, csv_data):
            return {
                "model_type": "nitrate_apportion",
                "status": "success",
                "n_samples": len(csv_data)
            }
        
        def mock_process_conservative(self, csv_data):
            return {
                "model_type": "conservative_apportion",
                "status": "success",
                "n_samples": len(csv_data),
                "n_chemicals": 2
            }
        
        from src.models.nitrate import nitrate_apportion
        from src.models.conservative import conservative_apportion
        
        monkeypatch.setattr(
            nitrate_apportion.NitrateApportionModel,
            'process_nitrate_data',
            mock_process_nitrate
        )
        monkeypatch.setattr(
            conservative_apportion.ConservativeApportionModel,
            'process_conservative_data',
            mock_process_conservative
        )
        
        # Run models
        runner = ModelRunner()
        
        results = runner.run(
            csv_data=sample_mixed_data,
            parameters=processing_parameters,
        )
        
        # Check both models ran
        assert set(results['models_run']) == {'nitrate', 'conservative'}
        
        # Check summary
        assert results['summary']['n_models'] == 2
        assert 'nitrate' in results['summary']['models']
        assert 'conservative' in results['summary']['models']
    
    def test_no_supported_tracers_raises_error(
        self,
        processing_parameters,
        tmp_path
    ):
        """Test that error is raised when no supported tracers are found"""
        data = pd.DataFrame({
            'Sample_id': ['S001', 'S002'],
            'Long': [-1.234, -1.235],
            'Lat': [51.123, 51.124],
            'UnknownColumn': [1.0, 2.0]
        })
        
        runner = ModelRunner()
        
        with pytest.raises(ValueError, match="No supported nitrate or conservative tracer"):
            runner.run(
                csv_data=data,
                parameters=processing_parameters,
            )
    
    def test_model_failure_raises_error(
        self,
        sample_nitrate_data,
        processing_parameters,
        tmp_path,
        monkeypatch
    ):
        """Test that model failure is properly handled"""
        # Mock the nitrate model to return failure
        def mock_process_nitrate_fail(self, csv_data):
            return {
                "model_type": "nitrate_apportion",
                "status": "failed",
                "error": "Test error message"
            }
        
        from src.models.nitrate import nitrate_apportion
        monkeypatch.setattr(
            nitrate_apportion.NitrateApportionModel,
            'process_nitrate_data',
            mock_process_nitrate_fail
        )
        
        runner = ModelRunner()
        
        with pytest.raises(Exception, match="Nitrate model failed: Test error message"):
            runner.run(
                csv_data=sample_nitrate_data,
                parameters=processing_parameters,
            )


class TestProgressCallback:
    """Test progress callback functionality"""
    
    def test_progress_callback_called(
        self,
        sample_nitrate_data,
        processing_parameters,
        tmp_path,
        monkeypatch
    ):
        """Test that progress callback is called with correct values"""
        # Mock the nitrate model
        def mock_process_nitrate(self, csv_data):
            return {
                "model_type": "nitrate_apportion",
                "status": "success",
                "n_samples": len(csv_data)
            }
        
        from src.models.nitrate import nitrate_apportion
        monkeypatch.setattr(
            nitrate_apportion.NitrateApportionModel,
            'process_nitrate_data',
            mock_process_nitrate
        )
        
        # Track progress updates
        progress_updates = []
        
        def progress_callback(progress: float, message: str):
            progress_updates.append((progress, message))
        
        # Run with callback
        runner = ModelRunner()
        runner.run(
            csv_data=sample_nitrate_data,
            parameters=processing_parameters,
            progress_callback=progress_callback
        )
        
        # Check callback was called
        assert len(progress_updates) > 0
        
        # Check progress values are in order
        progresses = [p[0] for p in progress_updates]
        assert progresses == sorted(progresses)
        
        # Check messages
        messages = [p[1] for p in progress_updates]
        assert any("Detecting tracers" in m for m in messages)
        assert any("Running nitrate" in m for m in messages)
        assert any("Finalizing" in m for m in messages)
    
    def test_progress_callback_for_both_models(
        self,
        sample_mixed_data,
        processing_parameters,
        tmp_path,
        monkeypatch
    ):
        """Test progress callback when both models run"""
        # Mock both models
        def mock_process_nitrate(self, csv_data):
            return {
                "model_type": "nitrate_apportion",
                "status": "success",
                "n_samples": len(csv_data)
            }
        
        def mock_process_conservative(self, csv_data):
            return {
                "model_type": "conservative_apportion",
                "status": "success",
                "n_samples": len(csv_data),
                "n_chemicals": 2
            }
        
        from src.models.nitrate import nitrate_apportion
        from src.models.conservative import conservative_apportion
        
        monkeypatch.setattr(
            nitrate_apportion.NitrateApportionModel,
            'process_nitrate_data',
            mock_process_nitrate
        )
        monkeypatch.setattr(
            conservative_apportion.ConservativeApportionModel,
            'process_conservative_data',
            mock_process_conservative
        )
        
        # Track progress
        progress_updates = []
        
        def progress_callback(progress: float, message: str):
            progress_updates.append((progress, message))
        
        # Run
        runner = ModelRunner()
        runner.run(
            csv_data=sample_mixed_data,
            parameters=processing_parameters,
            progress_callback=progress_callback
        )
        
        # Check both models mentioned in progress
        messages = [p[1] for p in progress_updates]
        assert any("nitrate" in m.lower() for m in messages)
        assert any("conservative" in m.lower() for m in messages)


class TestConservativeTracerKeywords:
    """Test the conservative tracer keyword set"""
    
    def test_keywords_exist(self):
        """Test that keyword set is defined and not empty"""
        assert isinstance(CONSERVATIVE_TRACER_KEYWORDS, set)
        assert len(CONSERVATIVE_TRACER_KEYWORDS) > 0
    
    def test_keywords_are_lowercase(self):
        """Test that all keywords are lowercase"""
        for keyword in CONSERVATIVE_TRACER_KEYWORDS:
            assert keyword == keyword.lower()
    
    def test_major_ions_included(self):
        """Test that major conservative ions are included"""
        expected_ions = {'chloride', 'cl', 'sodium', 'na', 'calcium', 'ca'}
        assert expected_ions.issubset(CONSERVATIVE_TRACER_KEYWORDS)
    
    def test_isotopes_included(self):
        """Test that stable isotopes are included"""
        expected_isotopes = {'δ18o', 'd18o', 'δ2h', 'd2h'}
        assert expected_isotopes.issubset(CONSERVATIVE_TRACER_KEYWORDS)


# Edge Cases and Error Handling

class TestEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_empty_dataframe(self, processing_parameters, tmp_path):
        """Test handling of empty DataFrame"""
        data = pd.DataFrame(columns=['Long', 'Lat', 'NO3'])
        
        runner = ModelRunner()
        
        # Should detect nitrate but handle empty data gracefully
        result = runner._determine_models(data)
        assert result['nitrate'] is True
    
    def test_case_insensitive_detection(self):
        """Test that detection is case-insensitive"""
        runner = ModelRunner()
        
        test_cases = [
            ('NITRATE', 'nitrate'),
            ('Nitrate', 'nitrate'),
            ('nitrate', 'nitrate'),
            ('CHLORIDE', 'conservative'),
            ('Chloride', 'conservative'),
            ('chloride', 'conservative'),
        ]
        
        for col_name, expected_model in test_cases:
            data = pd.DataFrame({
                'Long': [-1.234],
                'Lat': [51.123],
                col_name: [5.2]
            })
            
            result = runner._determine_models(data)
            
            if expected_model == 'nitrate':
                assert result['nitrate'] is True
            else:
                assert result['conservative'] is True
    
    def test_special_characters_in_column_names(self):
        """Test handling of special characters in column names"""
        runner = ModelRunner()
        
        data = pd.DataFrame({
            'Long': [-1.234],
            'Lat': [51.123],
            'NO3-N (mg/L)': [5.2],
            'Cl- [mg/L]': [10.5]
        })
        
        result = runner._determine_models(data)
        assert result['nitrate'] is True
        assert result['conservative'] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])