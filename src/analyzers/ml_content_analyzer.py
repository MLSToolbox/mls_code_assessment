import ast
import os
import json
from typing import Dict, List, Set

from analyzers.base_analyzer import BaseAnalyzer
from core.models.analysis_result import AnalysisResult


class MLContentAnalyzer(BaseAnalyzer):
    """
    Analyzer to detect if Python files contain ML-related content using heuristics.
    
    This analyzer uses similar heuristics to PipelineAnalyzer to determine if a file
    contains machine learning code or if it's non-ML code (e.g., GUI, utilities, etc.).
    """
    
    def __init__(self, session_id: str, local_path: str, context=None):
        super().__init__(session_id, local_path, context)
        
        # Load ML detection configuration from pipeline_stages.json
        pipeline_stages_json_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'config',
            'pipeline_stages.json'
        )
        
        if os.path.exists(pipeline_stages_json_path):
            with open(pipeline_stages_json_path, 'r') as f:
                self.config = json.load(f)
        else:
            raise FileNotFoundError(
                f"Pipeline stages config not found at {pipeline_stages_json_path}"
            )
        
        # Extract all ML-related keywords and imports from config
        self.ml_keywords = set()
        self.ml_imports = set()
        
        for stage_config in self.config.get('stages', {}).values():
            self.ml_keywords.update(
                kw.lower() for kw in stage_config.get('keywords', [])
            )
            self.ml_imports.update(
                imp.lower() for imp in stage_config.get('imports', [])
            )
        
        # Non-ML indicators (GUI frameworks, web frameworks, etc.)
        self.non_ml_indicators = {
            'keywords': {
                'tkinter', 'pyqt', 'pyside', 'wxpython', 'kivy',
                'flask', 'django', 'fastapi', 'streamlit', 'dash',
                'gui', 'window', 'button', 'label', 'entry', 'frame',
                'widget', 'layout', 'event', 'callback'
            },
            'imports': {
                'tkinter', 'pyqt5', 'pyqt6', 'pyside2', 'pyside6',
                'wx', 'kivy', 'flask', 'django', 'fastapi',
                'streamlit', 'dash', 'gradio'
            }
        }
    
    @property
    def analyzer_id(self) -> str:
        return "ml_content"
    
    def analyze(self) -> AnalysisResult:
        """
        Analyze all Python files to detect ML content.
        
        Returns:
            AnalysisResult with per-file ML content detection
        """
        results = {
            'files': {},
            'summary': {
                'total_files': 0,
                'ml_files': 0,
                'non_ml_files': 0,
                'uncertain_files': 0
            }
        }
        
        python_files = self.context.get_python_files()
        results['summary']['total_files'] = len(python_files)
        
        for py_file in python_files:
            tree = self.context.get_file_ast(py_file)
            source = self.context.get_file_source(py_file)
            
            if tree is None or source is None:
                continue
            
            file_result = self._analyze_file(tree, source, py_file)
            results['files'][py_file] = file_result
            
            # Update summary
            if file_result['has_ml_content']:
                results['summary']['ml_files'] += 1
            elif file_result['has_non_ml_content']:
                results['summary']['non_ml_files'] += 1
            else:
                results['summary']['uncertain_files'] += 1
        
        # Calculate score: percentage of ML files
        if results['summary']['total_files'] > 0:
            score = (results['summary']['ml_files'] / results['summary']['total_files']) * 10
        else:
            score = 0
        
        messages = self._generate_messages(results)
        
        return self._create_result(
            score=round(score, 2),
            message_count={'messages': messages},
            module_count=results['summary']['total_files'],
            details=results
        )
    
    def analyze_file(self, file_path: str) -> bool:
        """
        Analyze a single file and return if it contains ML content.
        
        This is a convenience method for use by other analyzers (like FPC).
        
        Args:
            file_path: Path to the Python file
            
        Returns:
            True if file contains ML content, False otherwise
        """
        tree = self.context.get_file_ast(file_path)
        source = self.context.get_file_source(file_path)
        
        if tree is None or source is None:
            return False
        
        result = self._analyze_file(tree, source, file_path)
        return result['has_ml_content']
    
    def _analyze_file(self, tree: ast.Module, source: str, file_path: str) -> Dict:
        """
        Analyze a single file for ML content.
        
        Returns:
            Dict with detection results
        """
        source_lower = source.lower()
        
        # Detect ML indicators
        ml_keywords_found = set()
        ml_imports_found = set()
        
        for keyword in self.ml_keywords:
            if keyword in source_lower:
                ml_keywords_found.add(keyword)
        
        # Detect imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.lower()
                    for ml_import in self.ml_imports:
                        if ml_import in module_name:
                            ml_imports_found.add(ml_import)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_name = node.module.lower()
                    for ml_import in self.ml_imports:
                        if ml_import in module_name:
                            ml_imports_found.add(ml_import)
        
        # Detect non-ML indicators
        non_ml_keywords_found = set()
        non_ml_imports_found = set()
        
        for keyword in self.non_ml_indicators['keywords']:
            if keyword in source_lower:
                non_ml_keywords_found.add(keyword)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.lower()
                    for non_ml_import in self.non_ml_indicators['imports']:
                        if non_ml_import in module_name:
                            non_ml_imports_found.add(non_ml_import)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_name = node.module.lower()
                    for non_ml_import in self.non_ml_indicators['imports']:
                        if non_ml_import in module_name:
                            non_ml_imports_found.add(non_ml_import)
        
        # Determine ML content presence
        ml_score = len(ml_keywords_found) + len(ml_imports_found) * 2
        non_ml_score = len(non_ml_keywords_found) + len(non_ml_imports_found) * 3
        
        has_ml_content = ml_score > 0 and ml_score > non_ml_score
        has_non_ml_content = non_ml_score > ml_score
        
        return {
            'has_ml_content': has_ml_content,
            'has_non_ml_content': has_non_ml_content,
            'ml_keywords_found': list(ml_keywords_found),
            'ml_imports_found': list(ml_imports_found),
            'non_ml_keywords_found': list(non_ml_keywords_found),
            'non_ml_imports_found': list(non_ml_imports_found),
            'ml_score': ml_score,
            'non_ml_score': non_ml_score,
            'confidence': 'high' if abs(ml_score - non_ml_score) > 3 else 'medium' if abs(ml_score - non_ml_score) > 0 else 'low'
        }
    
    def _generate_messages(self, results: Dict) -> List[str]:
        """Generate human-readable messages."""
        messages = []
        summary = results['summary']
        
        messages.append(
            f"Analyzed {summary['total_files']} files for ML content"
        )
        
        if summary['ml_files'] > 0:
            messages.append(
                f"✓ {summary['ml_files']} files contain ML content"
            )
        
        if summary['non_ml_files'] > 0:
            messages.append(
                f"ℹ {summary['non_ml_files']} files contain non-ML content "
                f"(GUI, web frameworks, utilities, etc.)"
            )
        
        if summary['uncertain_files'] > 0:
            messages.append(
                f"⚠ {summary['uncertain_files']} files have uncertain content type"
            )
        
        return messages
