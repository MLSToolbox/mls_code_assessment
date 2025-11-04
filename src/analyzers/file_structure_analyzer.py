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
    - Script style (script_only) - loose code without functions/classes
    - Mixed patterns (mixed) - Anti-pattern combining classes + functions
    - Mixed script (mixed_script) - Anti-pattern combining structured code + loose code
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
                'script_only': 0,
                'mixed': 0,
                'mixed_script': 0,
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
            elif pattern == 'script_only':
                results['summary']['script_only'] += 1
            elif pattern == 'mixed':
                results['summary']['mixed'] += 1
            elif pattern == 'mixed_script':
                results['summary']['mixed_script'] += 1
        
        # Calculate score
        score = self._calculate_structure_score(results['summary'])
        messages = self._generate_messages(results)
        
        return self._create_result(
            score=round(score, 2),
            messages={'messages': messages},
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
            'script_only': Only loose code without functions/classes (script style)
            'mixed': Mix of classes and top-level functions (anti-pattern)
            'mixed_script': Mix of structured code (classes/functions) with loose code (anti-pattern)
        """
        has_classes = False
        has_top_level_functions = False
        has_loose_code = False
        
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                has_classes = True
            elif isinstance(node, ast.FunctionDef):
                has_top_level_functions = True
            elif self._is_executable_statement(node):
                has_loose_code = True
        
        # Determine pattern based on combinations
        has_structured = has_classes or has_top_level_functions
        
        if has_loose_code and has_structured:
            # Loose code mixed with classes/functions is anti-pattern
            return 'mixed_script'
        elif has_classes and has_top_level_functions:
            # Classes + functions is anti-pattern
            return 'mixed'
        elif has_classes and not has_top_level_functions and not has_loose_code:
            return 'classes_only'
        elif has_top_level_functions and not has_classes and not has_loose_code:
            return 'functions_only'
        elif has_loose_code and not has_structured:
            return 'script_only'
        else:
            # Empty file or only imports/docstrings
            return 'script_only'
    
    def _is_executable_statement(self, node: ast.AST) -> bool:
        """
        Check if a node represents executable loose code (not just imports/definitions).
        
        Args:
            node: AST node to check
            
        Returns:
            True if node is executable code, False if it's import/definition
        """
        # Ignore imports, module docstrings, and type annotations
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return False
        
        # Module-level constants/type aliases are acceptable
        # TypeAlias only exists in Python 3.10+, so check for it safely
        type_alias_types = (ast.AnnAssign,)
        if hasattr(ast, 'TypeAlias'):
            type_alias_types = (ast.AnnAssign, ast.TypeAlias)
        
        if isinstance(node, type_alias_types):
            return False
        
        # Ignore module docstrings (first Expr node with a Str/Constant)
        if isinstance(node, ast.Expr):
            if isinstance(node.value, (ast.Str, ast.Constant)):
                # Could be docstring, but we'll count it as loose code if there's logic
                return False
            # Also check for older Python versions with just ast.Str
            if hasattr(ast, 'Str') and isinstance(node.value, ast.Str):
                return False
        
        # Everything else is executable loose code
        return True
    
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
        num_loose_statements = sum(1 for n in ast.iter_child_nodes(tree)
                                   if self._is_executable_statement(n))
        
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
            'num_loose_statements': num_loose_statements,
            'total_components': num_classes + num_functions
        }
        
        # Add recommendations based on pattern
        if pattern == 'mixed_script':
            result['recommendation'] = (
                'CRITICAL: Loose executable code mixed with functions/classes. '
                'Refactor loose code into functions and organize under if __name__ == "__main__" block.'
            )
            result['severity'] = 'error'
        elif pattern == 'mixed':
            result['recommendation'] = (
                'Consider separating classes and functions into distinct modules. '
                'Mixed patterns reduce maintainability and violate separation of concerns.'
            )
            result['severity'] = 'warning'
        elif pattern == 'script_only':
            result['recommendation'] = (
                'Script-style code detected. Consider refactoring into functions for better '
                'testability, reusability, and maintainability.'
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
        - script_only: 0.6 (poor - loose code, not modular)
        - mixed: 0.5 (anti-pattern - classes + functions)
        - mixed_script: 0.3 (critical anti-pattern - structured + loose code)
        
        Args:
            summary: Summary statistics
            
        Returns:
            Score from 0-10
        """
        pattern_weights = {
            'classes_only': 1.0,
            'functions_only': 0.9,
            'script_only': 0.6,
            'mixed': 0.5,
            'mixed_script': 0.3
        }
        
        total_files = summary['total_files']
        if total_files == 0:
            return 10.0  # Perfect score for no files
        
        weighted_sum = (
            summary['classes_only'] * pattern_weights['classes_only'] +
            summary['functions_only'] * pattern_weights['functions_only'] +
            summary['script_only'] * pattern_weights['script_only'] +
            summary['mixed'] * pattern_weights['mixed'] +
            summary['mixed_script'] * pattern_weights['mixed_script']
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
        
        if summary['script_only'] > 0:
            messages.append(f"⚠ {summary['script_only']} files use script style (loose code without structure)")
            
            script_files = [
                fp for fp, data in results['files'].items()
                if data['pattern'] == 'script_only'
            ]
            
            if script_files:
                messages.append("Files with script-style code (consider refactoring into functions):")
                for fp in script_files:
                    file_data = results['files'][fp]
                    messages.append(
                        f"  - {fp}: {file_data['num_loose_statements']} loose statements"
                    )
        
        if summary['mixed'] > 0:
            messages.append(f"⚠ {summary['mixed']} files use mixed pattern (classes + functions)")
            
            mixed_files = [
                fp for fp, data in results['files'].items()
                if data['pattern'] == 'mixed'
            ]
            
            if mixed_files:
                messages.append("Files with mixed patterns needing refactoring:")
                for fp in mixed_files:
                    file_data = results['files'][fp]
                    messages.append(
                        f"  - {fp}: {file_data['num_classes']} classes + "
                        f"{file_data['num_functions']} functions"
                    )
        
        if summary['mixed_script'] > 0:
            messages.append(
                f"✗ {summary['mixed_script']} files mix structured code with loose statements (CRITICAL)"
            )
            
            mixed_script_files = [
                fp for fp, data in results['files'].items()
                if data['pattern'] == 'mixed_script'
            ]
            
            if mixed_script_files:
                messages.append("Files with mixed script anti-pattern (REQUIRES IMMEDIATE REFACTORING):")
                for fp in mixed_script_files:
                    file_data = results['files'][fp]
                    messages.append(
                        f"  - {fp}: {file_data['num_classes']} classes, "
                        f"{file_data['num_functions']} functions, "
                        f"{file_data['num_loose_statements']} loose statements"
                    )
        
        # Best practices recognition
        anti_patterns = summary['mixed'] + summary['mixed_script']
        if anti_patterns == 0 and summary['total_files'] > 0:
            messages.append("✓ No anti-patterns detected")
        
        return messages
