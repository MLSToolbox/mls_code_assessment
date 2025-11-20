import ast
import os
import json
from typing import Dict, List

from analyzers.base_analyzer import BaseAnalyzer
from core.analysis_result import AnalysisResult


class MLContentAnalyzer(BaseAnalyzer):
    """
    Simple analyzer to detect if Python files contain NON-ML content.
    
    SIMPLE LOGIC: 
    - Searches for non-ML keywords/imports (GUI, web frameworks, etc.)
    - Returns: has_no_ml_content (bool) and non_ml_keywords_found (list)
    
    Configuration loaded from ml_content_config.json.
    """
    
    def __init__(self, session_id: str, local_path: str, context=None):
        super().__init__(session_id, local_path, context)
        
        config_path = os.path.join(
            os.path.dirname(__file__),
            'ml_content_config.json'
        )
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                self.config = json.load(f)
        else:
            raise FileNotFoundError(
                f"ML content config not found at {config_path}"
            )
        
        non_ml_config = self.config.get('non_ml_indicators', {})
        self.non_ml_keywords = set(kw.lower() for kw in non_ml_config.get('keywords', []))
        self.non_ml_imports = set(imp.lower() for imp in non_ml_config.get('imports', []))
    
    @property
    def analyzer_id(self) -> str:
        return "ml_content"
    
    def analyze(self) -> AnalysisResult:
        """
        Analyze all Python files to detect non-ML content.
        
        Returns:
            AnalysisResult with per-file non-ML content detection
        """
        results = {
            'files': {},
            'summary': {
                'total_files': 0,
                'ml_files': 0,
                'non_ml_files': 0
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
            
            if file_result['has_no_ml_content']:
                results['summary']['non_ml_files'] += 1
            else:
                results['summary']['ml_files'] += 1
        
        if results['summary']['total_files'] > 0:
            score = (results['summary']['ml_files'] / results['summary']['total_files']) * 10
        else:
            score = 0
        
        messages = self._generate_messages(results)
        
        return self._create_result(
            score=round(score, 2),
            messages={'messages': messages},
            module_count=results['summary']['total_files'],
            details=results
        )
    
    def analyze_file(self, file_path: str) -> Dict:
        """
        Analyze a single file and return if it contains non-ML content.
        
        This is a convenience method for use by other analyzers (like FPC).
        
        Args:
            file_path: Path to the Python file
            
        Returns:
            Dict with 'has_no_ml_content' (bool) and 'non_ml_keywords_found' (list)
        """
        tree = self.context.get_file_ast(file_path)
        source = self.context.get_file_source(file_path)
        
        if tree is None or source is None:
            return {'has_no_ml_content': False, 'non_ml_keywords_found': []}
        
        return self._analyze_file(tree, source, file_path)
    
    def _analyze_file(self, tree: ast.Module, source: str, file_path: str) -> Dict:
        """
        SIMPLE detection of non-ML content.
        
        LOGIC:
        - Search for non-ML keywords in source code
        - Search for non-ML imports in import statements
        - If ANY found -> has_no_ml_content = True
        - Return list of what was found
        
        Returns:
            Dict with 'has_no_ml_content' (bool) and 'non_ml_keywords_found' (list)
        """
        source_lower = source.lower()
        non_ml_keywords_found = []
        
        for keyword in self.non_ml_keywords:
            if keyword in source_lower:
                non_ml_keywords_found.append(f"keyword:{keyword}")
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.lower()
                    for non_ml_import in self.non_ml_imports:
                        if non_ml_import in module_name:
                            non_ml_keywords_found.append(f"import:{non_ml_import}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_name = node.module.lower()
                    for non_ml_import in self.non_ml_imports:
                        if non_ml_import in module_name:
                            non_ml_keywords_found.append(f"import:{non_ml_import}")
        
        non_ml_keywords_found = list(set(non_ml_keywords_found))
        
        return {
            'has_no_ml_content': len(non_ml_keywords_found) > 0,
            'non_ml_keywords_found': non_ml_keywords_found
        }
    
    def _generate_messages(self, results: Dict) -> List[str]:
        """Generate human-readable messages."""
        messages = []
        summary = results['summary']
        
        messages.append(
            f"Analyzed {summary['total_files']} files for non-ML content"
        )
        
        if summary['ml_files'] > 0:
            messages.append(
                f"✓ {summary['ml_files']} files appear to be ML-related"
            )
        
        if summary['non_ml_files'] > 0:
            messages.append(
                f"ℹ {summary['non_ml_files']} files contain non-ML content "
                f"(GUI, web frameworks, utilities, etc.)"
            )
        
        return messages
