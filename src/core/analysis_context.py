import ast
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field


@dataclass
class FileAnalysisCache:
    """Cache for a single file analysis."""
    file_path: str
    ast_tree: Optional[ast.Module] = None
    source_code: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


class AnalysisContext:
    """
    Manages shared state across multiple analyzers.
    
    Provides caching for:
    - AST trees per file
    - Source code per file  
    - Metric results that can be reused
    
    This prevents redundant parsing and computation across analyzers.
    """
    
    def __init__(self, session_id: str, local_path: str, pipeline_metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize AnalysisContext.
        
        Args:
            session_id: Unique session identifier
            local_path: Path to extracted code
            pipeline_metadata: Optional pipeline detection results from PipelineAnalyzer
        """
        self.session_id = session_id
        self.local_path = local_path
        self._file_cache: Dict[str, FileAnalysisCache] = {}
        self._global_metrics: Dict[str, Any] = {}
        self._pipeline_metadata: Optional[Dict[str, Any]] = pipeline_metadata
    
    def get_file_ast(self, file_path: str) -> Optional[ast.Module]:
        """
        Get or generate AST for a file.
        
        Args:
            file_path: Relative path to Python file
            
        Returns:
            Parsed AST module or None if parsing fails
        """
        if file_path not in self._file_cache:
            self._file_cache[file_path] = FileAnalysisCache(file_path)
        
        cache = self._file_cache[file_path]
        if cache.ast_tree is None:
            try:
                cache.source_code = self._read_file(file_path)
                cache.ast_tree = ast.parse(cache.source_code, filename=file_path)
            except (SyntaxError, FileNotFoundError, UnicodeDecodeError) as e:
                print(f"Warning: Could not parse {file_path}: {e}")
                return None
        
        return cache.ast_tree
    
    def get_file_source(self, file_path: str) -> Optional[str]:
        """
        Get source code for a file.
        
        Args:
            file_path: Relative path to Python file
            
        Returns:
            Source code as string or None if read fails
        """
        if file_path not in self._file_cache:
            self._file_cache[file_path] = FileAnalysisCache(file_path)
        
        cache = self._file_cache[file_path]
        if cache.source_code is None:
            try:
                cache.source_code = self._read_file(file_path)
            except (FileNotFoundError, UnicodeDecodeError) as e:
                print(f"Warning: Could not read {file_path}: {e}")
                return None
        
        return cache.source_code
    
    def set_file_metric(self, file_path: str, metric_name: str, value: Any) -> None:
        """
        Store metric result for a file.
        
        Args:
            file_path: Relative path to Python file
            metric_name: Name of the metric
            value: Metric result value
        """
        if file_path not in self._file_cache:
            self._file_cache[file_path] = FileAnalysisCache(file_path)
        
        self._file_cache[file_path].metrics[metric_name] = value
    
    def get_file_metric(self, file_path: str, metric_name: str) -> Optional[Any]:
        """
        Retrieve cached metric result for a file.
        
        Args:
            file_path: Relative path to Python file
            metric_name: Name of the metric
            
        Returns:
            Cached metric value or None if not found
        """
        if file_path in self._file_cache:
            return self._file_cache[file_path].metrics.get(metric_name)
        return None
    
    def set_global_metric(self, metric_name: str, value: Any) -> None:
        """
        Store global metric (project-level).
        
        Args:
            metric_name: Name of the metric
            value: Metric result value
        """
        self._global_metrics[metric_name] = value
    
    def get_global_metric(self, metric_name: str) -> Optional[Any]:
        """
        Retrieve cached global metric.
        
        Args:
            metric_name: Name of the metric
            
        Returns:
            Cached metric value or None if not found
        """
        return self._global_metrics.get(metric_name)
    
    def has_file_metric(self, file_path: str, metric_name: str) -> bool:
        """
        Check if a metric exists for a file.
        
        Args:
            file_path: Relative path to Python file
            metric_name: Name of the metric
            
        Returns:
            True if metric exists, False otherwise
        """
        if file_path in self._file_cache:
            return metric_name in self._file_cache[file_path].metrics
        return False
    
    def _read_file(self, file_path: str) -> str:
        """
        Read file content.
        
        Args:
            file_path: Relative path to file
            
        Returns:
            File content as string
        """
        full_path = os.path.join(self.local_path, file_path)
        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def get_all_python_files(self) -> List[str]:
        """
        Get list of all Python files in the project.
        
        Returns:
            List of relative paths to Python files
        """
        python_files = []
        for root, _, files in os.walk(self.local_path):
            for file in files:
                if file.endswith('.py'):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.local_path)
                    python_files.append(rel_path)
        return python_files
    
    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._file_cache.clear()
        self._global_metrics.clear()
    
    def get_pipeline_metadata(self) -> Optional[Dict[str, Any]]:
        """
        Get pipeline detection metadata.
        
        Returns:
            Pipeline metadata from PipelineAnalyzer or None if not available
        """
        return self._pipeline_metadata
    
    def get_ml_files_by_stage(self, stage: Optional[str] = None) -> Dict[str, List[str]]:
        """
        Get ML-related files grouped by pipeline stage.
        
        Args:
            stage: Optional stage name to filter by. If None, returns all stages.
            
        Returns:
            Dictionary mapping stage names to list of file paths.
            If stage is specified, returns dict with single key.
            Returns empty dict if no pipeline metadata is available.
        """
        if not self._pipeline_metadata:
            return {}
        
        detected_stages = self._pipeline_metadata.get("detected_stages", {})
        
        if stage:
            if stage in detected_stages:
                files = [
                    file_info["file"] 
                    for file_info in detected_stages[stage]
                ]
                return {stage: files}
            return {}
        
        result = {}
        for stage_name, file_list in detected_stages.items():
            result[stage_name] = [
                file_info["file"] 
                for file_info in file_list
            ]
        return result
    
    def get_all_ml_files(self) -> List[str]:
        """
        Get all files detected as part of the ML pipeline.
        
        Returns:
            List of file paths that are part of the ML pipeline.
            Returns empty list if no pipeline metadata is available.
        """
        if not self._pipeline_metadata:
            return []
        
        ml_files = set()
        detected_stages = self._pipeline_metadata.get("detected_stages", {})
        
        for file_list in detected_stages.values():
            for file_info in file_list:
                ml_files.add(file_info["file"])
        
        return list(ml_files)
