import os
import subprocess
from typing import Dict, Any

from analyzers.base_analyzer import BaseAnalyzer
from core.models.analysis_result import AnalysisResult
from core.exceptions import AnalyzerError

class RadonCCAnalyzer(BaseAnalyzer):
    """Radon Cyclomatic Complexity analyzer."""
    
    @property
    def analyzer_id(self) -> str:
        return "Radon - Complexity"
    
    def analyze(self, code_path: str = None) -> AnalysisResult:
        """Analyze cyclomatic complexity using Radon."""
        target_path = code_path or self.local_path
        
        try:
            complexity_score, block_count = self._run_complexity_analysis(target_path)
            
            return AnalysisResult(
                analyzer_id=self.analyzer_id,
                score=complexity_score,
                message_count={},  # Radon CC doesn't provide message counts
                module_count=block_count,
                details={"complexity_method": "cyclomatic"}
            )
        except Exception as e:
            raise AnalyzerError(f"Radon CC analysis failed: {str(e)}")
    
    def generate_report(self, code_path: str = None) -> bytes:
        """Generate detailed complexity report."""
        target_path = code_path or self.local_path
        
        try:
            return self._run_complexity_report(target_path)
        except Exception as e:
            raise AnalyzerError(f"Radon CC report generation failed: {str(e)}")
    
    def _run_complexity_analysis(self, target_path: str) -> tuple:
        """Execute radon cc analysis."""
        with self._change_to_project_dir():
            folders = self._get_project_folders('.')
            
            for folder in folders:
                try:
                    cmd = ["radon", "cc", "--total-average", "-s", folder]
                    
                    result = subprocess.run(
                        cmd, 
                        capture_output=True, 
                        text=True, 
                        check=True
                    )
                    
                    lines = result.stdout.strip().split('\n')
                    if len(lines) >= 2:
                        blocks_line = lines[-2]
                        complexity_line = lines[-1]
                        
                        blocks = int(blocks_line.split()[0])
                        
                        complexity_str = complexity_line.split('(')[-1].rstrip(')')
                        complexity = float(complexity_str)
                        
                        score = round(10 / pow(complexity, 0.3), 2)
                        
                        return score, blocks
                        
                except (subprocess.CalledProcessError, ValueError, IndexError):
                    continue
            
            raise AnalyzerError("No valid Radon CC output generated")
    
    def _run_complexity_report(self, target_path: str) -> bytes:
        """Generate detailed complexity report."""
        with self._change_to_project_dir():
            folders = self._get_project_folders('.')
            
            for folder in folders:
                try:
                    cmd = ["radon", "cc", "--total-average", "-s", folder]
                    
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        check=True
                    )
                    
                    return result.stdout
                    
                except subprocess.CalledProcessError:
                    continue
            
            raise AnalyzerError("No Radon CC report generated")