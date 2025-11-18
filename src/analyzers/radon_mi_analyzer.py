import os
import subprocess
import json
from typing import Dict, Any

from analyzers.base_analyzer import BaseAnalyzer
from core.analysis_result import AnalysisResult
from core.exceptions import AnalyzerError


class RadonMIAnalyzer(BaseAnalyzer):
    
    @property
    def analyzer_id(self) -> str:
        return "radon_mi"
    
    def analyze(self, code_path: str = None) -> AnalysisResult:
        target_path = code_path or self.local_path
        
        try:
            mi_data = self._run_maintainability_analysis(target_path)
            
            return self._create_result(
                score=mi_data["average_score"],
                messages=mi_data["rank_counts"],
                module_count=mi_data["module_count"],
                details=mi_data["details"]
            )
        except Exception as e:
            raise AnalyzerError(f"Radon MI analysis failed: {str(e)}")
    
    def generate_report(self, code_path: str = None) -> bytes:
        """Generate detailed maintainability report."""
        target_path = code_path or self.local_path
        
        try:
            return self._run_maintainability_report(target_path)
        except Exception as e:
            raise AnalyzerError(f"Radon MI report generation failed: {str(e)}")
    
    def _run_maintainability_analysis(self, target_path: str) -> Dict[str, Any]:
        """Execute radon mi analysis."""
        with self._change_to_project_dir():
            folders = self._get_project_folders('.')
            
            for folder in folders:
                try:
                    cmd = ["radon", "mi", "-j", folder]
                    
                    result = subprocess.run(
                        cmd, 
                        capture_output=True, 
                        text=True, 
                        check=True
                    )
                    
                    json_data = json.loads(result.stdout)
                    return self._process_mi_data(json_data)
                    
                except (subprocess.CalledProcessError, json.JSONDecodeError):
                    continue
            
            raise AnalyzerError("No valid Radon MI output generated")
    
    def _run_maintainability_report(self, target_path: str) -> bytes:
        """Generate detailed maintainability report."""
        with self._change_to_project_dir():
            folders = self._get_project_folders('.')
            
            for folder in folders:
                try:
                    cmd = ["radon", "mi", "-s", folder]
                    
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        check=True
                    )
                    
                    return result.stdout
                    
                except subprocess.CalledProcessError:
                    continue
            
            raise AnalyzerError("No Radon MI report generated")
    
    def _process_mi_data(self, json_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process maintainability index data."""
        rank_counts = {
            "Very High": 0,  # A rank
            "Medium": 0,     # B rank
            "Extremely low": 0  # C rank
        }
        
        total_score = 0.0
        valid_modules = 0
        module_details = {}
        
        for module_path, module_data in json_data.items():
            if 'mi' not in module_data:
                continue
            
            mi_score = float(module_data['mi'])
            rank = module_data.get('rank', 'C')
            
            total_score += mi_score / 10.0  # Normalize to 0-10 scale
            valid_modules += 1
            
            if rank == 'A':
                rank_counts["Very High"] += 1
            elif rank == 'B':
                rank_counts["Medium"] += 1
            elif rank == 'C':
                rank_counts["Extremely low"] += 1
            
            module_details[module_path] = {
                "mi_score": mi_score,
                "rank": rank
            }
        
        average_score = round(total_score / valid_modules, 2) if valid_modules > 0 else 0
        
        return {
            "average_score": average_score,
            "rank_counts": rank_counts,
            "module_count": len(json_data),
            "details": {
                "valid_modules": valid_modules,
                "modules": module_details
            }
        }
