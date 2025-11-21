import ast
import os
from typing import Dict, List, Set, Tuple, Optional, Any
from collections import defaultdict

from core.analysis_result import AnalysisResult
from analyzers.base_analyzer import BaseAnalyzer


class IFCPAnalyzer(BaseAnalyzer):
    """
    Analyzer for IFC-P (Information Flow Cohesion - Package) metric.
    
    Measures the functional cooperation between modules of the same package
    via information flow (invocations or data consumption).
    
    IFC-P(P) = (2 * sum(F_ij)) / (m * (m - 1))
    where F_ij = 1 if module i invoca al modulo j o consume sus datos.
    """
    
    @property
    def analyzer_id(self) -> str:
        return "ifc_p"
    
    def analyze(self) -> AnalysisResult:
        """
        Analyze IFC-P cohesion for all Python packages.
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
                'average_ifc_p': 0.0
            }
        }
        
        # Group files by package (directory)
        python_files = self.context.get_all_python_files()
        packages = defaultdict(list)
        
        for file_path in python_files:
            if file_path.endswith('__init__.py'):
                continue
                
            package_path = os.path.dirname(file_path) or '.'
            packages[package_path].append(file_path)
            
        results['summary']['total_packages'] = len(packages)
        scores = []
        
        for package_name, files in packages.items():
            if len(files) < 2:
                continue
                
            package_result = self._analyze_package(files, package_name)
            results['packages'][package_name] = package_result
            
            score = package_result['ifc_p']
            if score is not None:
                scores.append(score)
                if score >= 0.8: results['summary']['high_cohesion'] += 1
                elif score >= 0.6: results['summary']['good_cohesion'] += 1
                elif score >= 0.4: results['summary']['moderate_cohesion'] += 1
                elif score >= 0.2: results['summary']['low_cohesion'] += 1
                else: results['summary']['very_low_cohesion'] += 1
        
        if scores:
            results['summary']['average_ifc_p'] = sum(scores) / len(scores)
            final_score = results['summary']['average_ifc_p'] * 10
        else:
            final_score = 0
            
        messages = self._generate_messages(results)
        
        return self._create_result(
            score=round(final_score, 2),
            messages=messages,
            module_count=len(packages),
            details=results,
            
        )
    
    def _analyze_package(self, files: List[str], package_path: str) -> Dict:
        """Analyze IFC-P for a single package."""
        m = len(files)
        if m <= 1:
            return {'ifc_p': None, 'n_modules': m}
            
        # Map module names to files for resolution
        # We assume module name is filename without extension
        module_map = {}
        for f in files:
            basename = os.path.basename(f)
            module_name = os.path.splitext(basename)[0]
            module_map[module_name] = f
            
        # Build dependency graph
        # dependencies[file_path] = set of file_paths it imports
        dependencies = defaultdict(set)
        
        for file_path in files:
            tree = self.context.get_file_ast(file_path)
            if not tree:
                continue
                
            imports = self._extract_imports(tree)
            resolved_deps = self._resolve_imports(imports, module_map, package_path)
            dependencies[file_path].update(resolved_deps)
            
        # Calculate connected pairs
        connected_pairs = 0
        total_pairs = (m * (m - 1)) // 2
        connected_pair_list = []
        
        file_list = list(files)
        
        for i, file_a in enumerate(file_list):
            for file_b in file_list[i+1:]:
                # Check connection in either direction
                # A imports B OR B imports A
                a_imports_b = file_b in dependencies[file_a]
                b_imports_a = file_a in dependencies[file_b]
                
                if a_imports_b or b_imports_a:
                    connected_pairs += 1
                    connected_pair_list.append((
                        os.path.basename(file_a),
                        os.path.basename(file_b)
                    ))
                    
        ifc_p = connected_pairs / total_pairs if total_pairs > 0 else 0
        
        return {
            'ifc_p': round(ifc_p, 3),
            'n_modules': m,
            'n_possible_pairs': total_pairs,
            'n_connected_pairs': connected_pairs,
            'connected_pairs': connected_pair_list,
            'cohesion_level': self._categorize_cohesion(ifc_p)
        }



    def _extract_imports(self, tree: ast.Module) -> List[Dict]:
        """Extract import statements from AST."""
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({'type': 'absolute', 'name': alias.name})
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                level = node.level
                names = [n.name for n in node.names]
                imports.append({'type': 'from', 'module': module, 'level': level, 'names': names})
        return imports

    def _resolve_imports(self, imports: List[Dict], module_map: Dict[str, str], package_path: str) -> Set[str]:
        """Resolve imports to file paths within the package."""
        resolved = set()
        package_name = os.path.basename(package_path)
        
        for imp in imports:
            target_module = None
            
            if imp['type'] == 'absolute':
                # Case: import module_name
                parts = imp['name'].split('.')
                if parts[0] in module_map:
                    resolved.add(module_map[parts[0]])
                # Case: import package.module_name
                elif len(parts) > 1 and parts[-1] in module_map:
                     # Simple heuristic: if last part matches a module in this package
                     # and the package name matches or is generic
                     resolved.add(module_map[parts[-1]])

            elif imp['type'] == 'from':
                level = imp['level']
                module = imp['module']
                names = imp['names']
                
                if level > 0:
                    # Relative import
                    if module:
                        # from .module import ... -> imports module
                        if module in module_map:
                            resolved.add(module_map[module])
                    else:
                        # from . import module1, module2
                        for name in names:
                            if name in module_map:
                                resolved.add(module_map[name])
                else:
                    # Absolute from: from package.module import ...
                    if module:
                        parts = module.split('.')
                        # from package.module import ... -> imports package.module
                        if parts[-1] in module_map:
                            resolved.add(module_map[parts[-1]])
                        # from package import module -> imports module
                        elif parts[-1] == package_name:
                            for name in names:
                                if name in module_map:
                                    resolved.add(module_map[name])
                                    
        return resolved

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
            score = data['ifc_p']
            if score is not None and score < 0.4:
                messages.append({
                    'file': pkg_name,
                    'diagnosis': f"Low package cohesion (IFC-P: {score:.2f}). Modules have few functional dependencies.",
                    'recommendation': "Ensure modules in the package interact with each other.",
                    'severity': 'medium',
                    'rule_id': 'ifc_p_cohesion'
                })
                
        return messages
