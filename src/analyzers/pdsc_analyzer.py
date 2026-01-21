import ast
import os
from typing import Dict, List, Set, Tuple, Optional, Any
from collections import defaultdict

from core.analysis_result import AnalysisResult
from analyzers.base_analyzer import BaseAnalyzer


class PDSCAnalyzer(BaseAnalyzer):
    """
    Analyzer for PDSC (Package Data Structure Cohesion) metric.
    
    Measures the structural sharing of data or models between modules of the same package.
    PDSC(P) = (2 * sum(Q_ij)) / (m * (m - 1))
    where Q_ij = 1 if modules i and j access or modify the same data structures or resources.
    """
    
  
    
    @property
    def analyzer_id(self) -> str:
        return "pdsc"
    
    def analyze(self) -> AnalysisResult:
        """
        Analyze PDSC cohesion for all Python packages.
        
        Returns:
            AnalysisResult with PDSC scores per package
        """
        results = {
            'packages': {},
            'summary': {
                'total_packages': 0,
                'high_cohesion': 0,      # 0.8-1.0
                'good_cohesion': 0,      # 0.6-0.79
                'moderate_cohesion': 0,  # 0.4-0.59
                'low_cohesion': 0,       # 0.2-0.39
                'very_low_cohesion': 0,  # 0.0-0.19
                'average_pdsc': 0.0
            }
        }
        
        # Group files by package (directory) - Inspired by CCPPAnalyzer
        python_files = self.context.get_all_python_files()
        packages = defaultdict(list)
        
        for file_path in python_files:
            if file_path.endswith('__init__.py'):
                continue
                
            package_path = os.path.dirname(file_path) or '.'
            packages[package_path].append(file_path)
            
        results['summary']['total_packages'] = len(packages)
        pdsc_scores = []
        
        for package_name, files in packages.items():
            if len(files) < 2:
                continue
                
            package_result = self._analyze_package(files)
            results['packages'][package_name] = package_result
            
            pdsc = package_result['pdsc']
            if pdsc is not None:
                pdsc_scores.append(pdsc)
                if pdsc >= 0.8:
                    results['summary']['high_cohesion'] += 1
                elif pdsc >= 0.6:
                    results['summary']['good_cohesion'] += 1
                elif pdsc >= 0.4:
                    results['summary']['moderate_cohesion'] += 1
                elif pdsc >= 0.2:
                    results['summary']['low_cohesion'] += 1
                else:
                    results['summary']['very_low_cohesion'] += 1
                    
        if pdsc_scores:
            results['summary']['average_pdsc'] = sum(pdsc_scores) / len(pdsc_scores)
            score = results['summary']['average_pdsc'] * 10
        else:
            score = 0
            
        messages = self._generate_messages(results)
        
        return self._create_result(
            score=round(score, 2),
            messages=messages,
            module_count=len(packages),
            details=results,
           
        )
        
    def _analyze_package(self, files: List[str]) -> Dict:
        """Analyze PDSC for a single package."""
        m = len(files)
        if m <= 1:
            return {'pdsc': None, 'n_modules': m}
            
        # Extract resources for each file
        file_resources = {}
        for file_path in files:
            tree = self.context.get_file_ast(file_path)
            if tree:
                file_resources[file_path] = self._extract_file_resources(tree)
            else:
                file_resources[file_path] = set()
                
        # Calculate Q_ij for all pairs
        shared_pairs = 0
        total_pairs = (m * (m - 1)) // 2
        shared_pair_list = []
        
        file_list = list(file_resources.keys())
        
        for i, file_a in enumerate(file_list):
            for file_b in file_list[i+1:]:
                resources_a = file_resources[file_a]
                resources_b = file_resources[file_b]
                
                # Q_ij = 1 if they share at least one resource
                if resources_a & resources_b:
                    shared_pairs += 1
                    shared_pair_list.append((
                        os.path.basename(file_a), 
                        os.path.basename(file_b)
                    ))
                    
        pdsc = (2 * shared_pairs) / (m * (m - 1)) if total_pairs > 0 else 0
        
        return {
            'pdsc': round(pdsc, 3),
            'n_modules': m,
            'n_possible_pairs': total_pairs,
            'n_shared_pairs': shared_pairs,
            'shared_pairs': shared_pair_list,
            'resources_per_file': {os.path.basename(k): list(v) for k, v in file_resources.items()}
        }

    def _extract_file_resources(self, tree: ast.Module) -> Set[str]:
        """Extract resources (significant variables) accessed in a file."""
        resources = set()
        
        for node in ast.walk(tree):
            # Check for global variable usage
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                if self._is_likely_global_variable(node.id):
                    resources.add(node.id)
                    
            # Check for attribute usage (e.g. self.config) - though less relevant for file-level, 
            # we might catch module-level objects
            elif isinstance(node, ast.Attribute):
                attr_path = self._get_attribute_path(node)
                if self._is_likely_global_variable(attr_path):
                    resources.add(attr_path)
                    
        return resources

    # --- Logic duplicated from LDSCAnalyzer ---

    def _get_attribute_path(self, node: ast.Attribute) -> str:
        parts = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
            return '.'.join(reversed(parts))
        return ''

    def _is_likely_global_variable(self, var_name: str) -> bool:
        """Heuristic to determine if a variable is likely a global resource."""
        if not var_name:
            return False
            
        builtins = {'list', 'dict', 'str', 'int', 'float', 'bool', 'len', 'print', 'range', 'enumerate', 'zip', 'set', 'min', 'max', 'sum', 'open'}
        common_imports = {'np', 'pd', 'plt', 'os', 'sys', 'json', 're', 'math'}
        
        # Check first part of dotted path
        root_var = var_name.split('.')[0]
        
        if root_var in builtins or root_var in common_imports:
            return False
            
        # Common ML globals
        ml_globals = {'data', 'df', 'model', 'config', 'X', 'y', 'X_train', 'y_train', 'scaler', 'dataset', 'feature_store'}
        if root_var in ml_globals:
            return True
            
        # Uppercase (constants)
        if root_var.isupper():
            return True
            
        # Starts with underscore (often shared internal state)
        if root_var.startswith('_'):
            return True
            
        # MixedCase starting with upper (Classes or Global Objects)
        if root_var[0].isupper():
            return True
            
        return False

    def _categorize_cohesion(self, score: float) -> str:
        if score >= 0.8: return 'excellent'
        if score >= 0.6: return 'good'
        if score >= 0.4: return 'moderate'
        if score >= 0.2: return 'low'
        return 'very_low'

    def _generate_messages(self, results: Dict) -> List[Dict[str, Any]]:
        messages = []
        summary = results['summary']
        

        
        for pkg_name, data in results['packages'].items():
            pdsc = data['pdsc']
            if pdsc is not None and pdsc < 0.4:
                messages.append({
                    'file': pkg_name, 
                    'diagnosis': f"Low package cohesion (PDSC: {pdsc:.2f}). Modules share few resources.",
                    'recommendation': "Consider regrouping modules that share data or passing resources explicitly.",
                    'severity': 'medium',
                    'rule_id': 'pdsc_cohesion'
                })
                
        return messages
