import ast
import os
from typing import Dict, List

from core.models.analysis_result import AnalysisResult
from analyzers.base_analyzer import BaseAnalyzer


class FileStructureAnalyzer(BaseAnalyzer):
    """
    Analyzes Python file structure patterns.
    
    Evaluates whether files follow:
    - OOP design (classes_only)
    - Functional style (functions_only) 
    - Anti-pattern (mixed)
    """
    
    @property
    def analyzer_id(self) -> str:
        return "file_structure"
    
    def analyze(self) -> AnalysisResult:
        """
        Analyze file structure patterns.
        
        The files to analyze are determined by the AnalysisContext configuration:
        - If context.all_files=True: Analyzes ALL Python files
        - If context.all_files=False: Prefers ML pipeline files, falls back to all files
        
        Returns:
            AnalysisResult with structure quality score and details.
        """
        results = {
            'files': {},
            'summary': {
                'total_files': 0,
                'classes_only': 0,
                'functions_only': 0,
                'mixed': 0,
                'scan_mode': self.context.get_scan_mode()
            }
        }
        
        # Get files from context (respects all_files configuration)
        python_files = self.context.get_python_files()
        results['summary']['total_files'] = len(python_files)
        
        # Analyze each file
        for py_file in python_files:
            tree = self.context.get_file_ast(py_file)
            if tree is None:
                continue
            
            pattern = self._classify_file_pattern(tree)
            file_info = self._analyze_file_structure(tree, pattern)
            
            results['files'][py_file] = file_info
            
            # Update summary counts
            if pattern == 'classes_only':
                results['summary']['classes_only'] += 1
            elif pattern == 'functions_only':
                results['summary']['functions_only'] += 1
            elif pattern == 'mixed':
                results['summary']['mixed'] += 1
        
        # Calculate score
        score = self._calculate_structure_score(results['summary'])
        messages = self._generate_messages(results)
        
        return self._create_result(
            score=round(score, 2),
            message_count={'messages': messages},
            module_count=results['summary']['total_files'],
            details=results
        )
    
    def _classify_file_pattern(self, tree: ast.Module) -> str:
        """
        Classify Python file structure pattern.
        
        Args:
            tree: AST of the file
            
        Returns:
            'functions_only': Only top-level functions (functional style)
            'classes_only': Only classes with methods (OOP style)
            'mixed': Mix of classes and top-level functions (anti-pattern)
        """
        has_classes = False
        has_top_level_functions = False
        
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                has_classes = True
            elif isinstance(node, ast.FunctionDef):
                has_top_level_functions = True
        
        if has_classes and not has_top_level_functions:
            return 'classes_only'
        elif has_top_level_functions and not has_classes:
            return 'functions_only'
        elif has_classes and has_top_level_functions:
            return 'mixed'
        else:
            return 'functions_only'  # Default for empty/import-only files
    
    def _analyze_file_structure(self, tree: ast.Module, pattern: str) -> Dict:
        """
        Analyze detailed structure of a file.
        
        Args:
            tree: AST of the file
            pattern: Pattern classification
            
        Returns:
            Dictionary with detailed structure information
        """
        num_classes = sum(1 for n in ast.iter_child_nodes(tree) 
                         if isinstance(n, ast.ClassDef))
        num_functions = sum(1 for n in ast.iter_child_nodes(tree) 
                           if isinstance(n, ast.FunctionDef))
        
        # Count methods inside classes
        num_methods = 0
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                num_methods += sum(1 for n in ast.iter_child_nodes(node)
                                  if isinstance(n, ast.FunctionDef))
        
        result = {
            'pattern': pattern,
            'num_classes': num_classes,
            'num_functions': num_functions,
            'num_methods': num_methods,
            'total_components': num_classes + num_functions
        }
        
        # Add recommendation for mixed pattern
        if pattern == 'mixed':
            result['recommendation'] = (
                'Consider separating classes and functions into distinct modules. '
                'Mixed patterns reduce maintainability and violate separation of concerns.'
            )
            result['severity'] = 'warning'
        elif pattern == 'classes_only' and num_classes > 0:
            result['recommendation'] = 'Good OOP structure following best practices.'
            result['severity'] = 'info'
        elif pattern == 'functions_only' and num_functions > 0:
            result['recommendation'] = 'Consistent functional style.'
            result['severity'] = 'info'
        
        return result
    
    def _calculate_structure_score(self, summary: Dict) -> float:
        """
        Calculate structure quality score.
        
        Pattern weights:
        - classes_only: 1.0 (best practice - OOP design)
        - functions_only: 0.9 (acceptable - functional style)
        - mixed: 0.7 (anti-pattern - penalized)
        
        Args:
            summary: Summary statistics
            
        Returns:
            Score from 0-10
        """
        pattern_weights = {
            'classes_only': 1.0,
            'functions_only': 0.9,
            'mixed': 0.7
        }
        
        total_files = summary['total_files']
        if total_files == 0:
            return 10.0  # Perfect score for no files
        
        weighted_sum = (
            summary['classes_only'] * pattern_weights['classes_only'] +
            summary['functions_only'] * pattern_weights['functions_only'] +
            summary['mixed'] * pattern_weights['mixed']
        )
        
        # Normalize to 0-10 scale
        score = (weighted_sum / total_files) * 10
        return score
    
    def _generate_messages(self, results: Dict) -> List[str]:
        """
        Generate human-readable messages.
        
        Args:
            results: Analysis results
            
        Returns:
            List of message strings
        """
        messages = []
        summary = results['summary']
        
        # Scan mode info
        scan_mode_text = {
            'all_files': 'all Python files in project',
            'ml_only': 'ML pipeline files only',
            'all_files_fallback': 'all Python files (no pipeline detected)'
        }
        mode = summary['scan_mode']
        messages.append(f"Analyzed {summary['total_files']} files ({scan_mode_text.get(mode, mode)})")
        
        # Pattern distribution
        if summary['classes_only'] > 0:
            messages.append(f"✓ {summary['classes_only']} files follow OOP design (classes only)")
        
        if summary['functions_only'] > 0:
            messages.append(f"✓ {summary['functions_only']} files follow functional style (functions only)")
        
        if summary['mixed'] > 0:
            messages.append(f"⚠ {summary['mixed']} files use mixed pattern (anti-pattern detected)")
            
            # List mixed files
            mixed_files = [
                fp for fp, data in results['files'].items()
                if data['pattern'] == 'mixed'
            ]
            
            if mixed_files:
                messages.append("Files with mixed patterns needing refactoring:")
                for fp in mixed_files:  # Mostrar TODOS los archivos
                    file_data = results['files'][fp]
                    messages.append(
                        f"  - {fp}: {file_data['num_classes']} classes + "
                        f"{file_data['num_functions']} functions"
                    )
        
        # Best practices recognition
        if summary['mixed'] == 0 and summary['total_files'] > 0:
            messages.append("✓ All files follow consistent architectural patterns")
        
        return messages
