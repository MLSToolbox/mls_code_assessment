import ast
import os
import json
from typing import Dict, List, Set, Optional
from collections import defaultdict

from core.models.analysis_result import AnalysisResult
from analyzers.base_analyzer import BaseAnalyzer


class FPCAnalyzer(BaseAnalyzer):
    """Analyzes functional pipeline cohesion of ML code."""
    
    def __init__(self, session_id: str, local_path: str, context=None):
        """Initialize FPCAnalyzer."""
        super().__init__(session_id, local_path, context)
                
        
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

      
        self.stage_to_phase = {}
        for phase, stages in self.config.get('phases', {}).items():
            for stage in stages:
                self.stage_to_phase[stage] = phase
    
    @property
    def analyzer_id(self) -> str:
        return "FPC"
    
    def analyze(self) -> AnalysisResult:
        """Run FPC analysis on all Python files."""
        results = {
            'files': {},
            'summary': {
                'total_files': 0,
                'high_cohesion': 0,
                'medium_cohesion': 0,
                'low_cohesion': 0
            }
        }
        
        python_files = self.context.get_all_python_files()
        results['summary']['total_files'] = len(python_files)
        
        for py_file in python_files:
            tree = self.context.get_file_ast(py_file)
            if tree is None:
                continue
            
            file_result = self._analyze_file(tree, py_file)
            results['files'][py_file] = file_result
            
            
            self.context.set_file_metric(py_file, 'fpc', file_result)
            
            
            cohesion_level = file_result['cohesion_level']
            if cohesion_level == 'high':
                results['summary']['high_cohesion'] += 1
            elif cohesion_level == 'medium':
                results['summary']['medium_cohesion'] += 1
            else:
                results['summary']['low_cohesion'] += 1
        
       
        if results['summary']['total_files'] > 0:
            score = (results['summary']['high_cohesion'] / 
                    results['summary']['total_files']) * 10
        else:
            score = 0
        
        messages = self._generate_messages(results)
        
        return AnalysisResult(
            analyzer_id=self.analyzer_id,
            score=round(score, 2),
            message_count={'messages': messages},
            module_count=results['summary']['total_files'],
            details=results
        )
    
    def _analyze_file(self, tree: ast.Module, file_path: str) -> Dict:
        """Analyze a single file for FPC."""
        functions = self._extract_functions(tree)
        
        function_stages = {}
        for func_name, func_node in functions.items():
            stages = self._detect_stages(func_node, file_path)
            function_stages[func_name] = list(stages)
        
        
        all_stages = set()
        for stages in function_stages.values():
            all_stages.update(stages)
        
        unique_stages = len(all_stages)
        all_phases = {self.stage_to_phase.get(stage, 'unknown') for stage in all_stages}
        all_phases.discard('unknown')
        unique_phases = len(all_phases)
        
        cohesion_level = self._determine_cohesion_level(unique_stages, unique_phases)
        
        return {
            'unique_stages': unique_stages,
            'unique_phases': unique_phases,
            'stages_detected': list(all_stages),
            'phases_detected': list(all_phases),
            'cohesion_level': cohesion_level,
            'function_stages': function_stages
        }
    
    def _extract_functions(self, tree: ast.Module) -> Dict[str, ast.FunctionDef]:
        """Extract all functions and methods from AST."""
        functions = {}
        
        class FunctionVisitor(ast.NodeVisitor):
            def __init__(self):
                self.current_class = None
                self.functions = {}
            
            def visit_ClassDef(self, node):
                old_class = self.current_class
                self.current_class = node.name
                self.generic_visit(node)
                self.current_class = old_class
            
            def visit_FunctionDef(self, node):
                if self.current_class:
                    func_name = f"{self.current_class}.{node.name}"
                else:
                    func_name = node.name
                self.functions[func_name] = node
                self.generic_visit(node)
        
        visitor = FunctionVisitor()
        visitor.visit(tree)
        return visitor.functions
    
    def _detect_stages(self, func_node: ast.FunctionDef, file_path: str) -> Set[str]:
        """Detect ML pipeline stages in a function."""
        detected_stages = set()
        
        source = self.context.get_file_source(file_path)
        if source is None:
            return detected_stages
        
        try:
            func_source = ast.get_source_segment(source, func_node)
        except:
            func_source = None
        
        if func_source is None:
            return detected_stages
        
        func_source_lower = func_source.lower()
        
        for stage_name, stage_config in self.config['stages'].items():
            # Check keywords
            for keyword in stage_config.get('keywords', []):
                if keyword.lower() in func_source_lower:
                    detected_stages.add(stage_name)
                    break
            
            if stage_name in detected_stages:
                continue
            
            
            for node in ast.walk(func_node):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for import_pattern in stage_config.get('imports', []):
                            if import_pattern.lower() in alias.name.lower():
                                detected_stages.add(stage_name)
                                break
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        for import_pattern in stage_config.get('imports', []):
                            if import_pattern.lower() in node.module.lower():
                                detected_stages.add(stage_name)
                                break
                
                if stage_name in detected_stages:
                    break
        
        return detected_stages
    
    def _determine_cohesion_level(self, unique_stages: int, unique_phases: int) -> str:
        """Determine cohesion level based on stages and phases."""
        if unique_stages == 0:
            return 'high'  
        elif unique_stages == 1:
            return 'high'
        elif unique_phases == 1:
            return 'medium'
        else:
            return 'low'
    
    def _generate_messages(self, results: Dict) -> List[str]:
        """Generate human-readable messages."""
        messages = []
        summary = results['summary']
        
        messages.append(
            f"Analyzed {summary['total_files']} files for functional pipeline cohesion"
        )
        
        if summary['high_cohesion'] > 0:
            messages.append(
                f"✓ {summary['high_cohesion']} files have high cohesion"
            )
        
        if summary['medium_cohesion'] > 0:
            messages.append(
                f"⚠ {summary['medium_cohesion']} files have medium cohesion"
            )
        
        if summary['low_cohesion'] > 0:
            messages.append(
                f"✗ {summary['low_cohesion']} files have low cohesion"
            )
            
            low_cohesion_files = [
                fp for fp, data in results['files'].items()
                if data['cohesion_level'] == 'low'
            ]
            if low_cohesion_files:
                messages.append("Files needing refactoring:")
                for fp in low_cohesion_files[:5]:
                    messages.append(f"  - {fp}")
        
        return messages
