import os
import subprocess
import json
from typing import Dict, Any

from analyzers.base_analyzer import BaseAnalyzer
from core.models.analysis_result import AnalysisResult
from core.exceptions import AnalyzerError
from config.settings import settings

class PyLintAnalyzer(BaseAnalyzer):
    """PyLint code quality analyzer."""
    
    @property
    def analyzer_id(self) -> str:
        return "PyLint"
    
    def analyze(self, code_path: str = None) -> AnalysisResult:
        """Analyze code using PyLint."""
        target_path = code_path or self.local_path
        
        try:
            json_output = self._run_pylint_analysis(target_path)
            
            return AnalysisResult(
                analyzer_id=self.analyzer_id,
                score=json_output["statistics"]["score"],
                message_count=json_output["statistics"]["messageTypeCount"],
                module_count=json_output["statistics"]["modulesLinted"],
                details=self._extract_details(json_output)
            )
        except Exception as e:
            raise AnalyzerError(f"PyLint analysis failed: {str(e)}")
    
    def generate_report(self, code_path: str = None) -> bytes:
        """Generate detailed PyLint report."""
        target_path = code_path or self.local_path
        
        try:
            return self._run_pylint_report(target_path)
        except Exception as e:
            raise AnalyzerError(f"PyLint report generation failed: {str(e)}")
    
    def _run_pylint_analysis(self, target_path: str) -> Dict[str, Any]:
        """Execute pylint for analysis."""
        config = settings.get_analyzer_config()["pylint"]
        
        with self._change_to_project_dir():
            folders = self._get_project_folders(target_path)
            
            for folder in folders:
                try:
                    cmd = [
                        "pylint", 
                        "--recursive", "y",
                        "--output-format", config["output_format"],
                        "--disable", ",".join(config["disable"]),
                        "--clear-cache-post-run", "y",
                        folder
                    ]
                    
                    result = subprocess.run(
                        cmd, 
                        capture_output=True, 
                        text=True,
                        check=False  # PyLint returns non-zero for issues
                    )
                    
                    if result.stdout:
                        return json.loads(result.stdout)
                    elif result.stderr:
                        return json.loads(result.stderr)
                        
                except (subprocess.SubprocessError, json.JSONDecodeError) as e:
                    continue  # Try next folder
            
            # If no valid output found
            raise AnalyzerError("No valid PyLint output generated")
    
    def _run_pylint_report(self, target_path: str) -> bytes:
        """Execute pylint for detailed report."""
        with self._change_to_project_dir():
            folders = self._get_project_folders(target_path)
            
            for folder in folders:
                try:
                    cmd = [
                        "pylint",
                        "--recursive", "y", 
                        "--score", "n",
                        "--reports", "y",
                        "--disable", "E0401",
                        "--clear-cache-post-run", "y",
                        folder
                    ]
                    
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        check=False
                    )
                    
                    if result.stdout:
                        return result.stdout
                    elif result.stderr:
                        return result.stderr
                        
                except subprocess.SubprocessError:
                    continue
            
            raise AnalyzerError("No PyLint report generated")
    
    def _get_project_folders(self, target_path: str) -> list:
        """Get folders containing Python files."""
        folders = []
        for item in os.listdir(target_path):
            item_path = os.path.join(target_path, item)
            if os.path.isdir(item_path):
                # Check if folder contains Python files
                has_python = any(
                    f.endswith('.py') 
                    for f in os.listdir(item_path) 
                    if os.path.isfile(os.path.join(item_path, f))
                )
                if has_python:
                    folders.append(item)
        
        return folders or ['.']  # Current directory if no folders found
    
    def _extract_details(self, json_output: Dict[str, Any]) -> Dict[str, Any]:
        """Extract additional details from PyLint output."""
        return {
            "messages": json_output.get("messages", []),
            "statistics": json_output.get("statistics", {}),
            "config": json_output.get("config", {})
        }