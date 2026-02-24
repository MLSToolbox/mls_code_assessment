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
    - File discovery (filtered based on all_files flag)
    
    This prevents redundant parsing and computation across analyzers.
    """
    
    def __init__(
        self, 
        session_id: str, 
        local_path: str, 
        pipeline_metadata: Optional[Dict[str, Any]] = None,
        tree_metadata: Optional[Dict[str, Any]] = None,
        all_files: bool = False
    ):
        """
        Initialize AnalysisContext.
        
        Args:
            session_id: Unique session identifier
            local_path: Path to extracted code
            pipeline_metadata: Optional pipeline detection results from PipelineAnalyzer
            all_files: If True, analyze ALL Python files in project.
                      If False (default), prefer ML pipeline files when available.
        """
        self.session_id = session_id
        self.local_path = local_path
        self._file_cache: Dict[str, FileAnalysisCache] = {}
        self._global_metrics: Dict[str, Any] = {}
        self._pipeline_metadata: Optional[Dict[str, Any]] = pipeline_metadata
        self._tree_metadata: Optional[Dict[str, Any]] = tree_metadata
        self._all_files = all_files
        self._python_files_cache: Optional[List[str]] = None  # Cache for file discovery
    
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
    
    def get_python_files(self) -> List[str]:
        """
        Get Python files to analyze based on context configuration.
        
        Behavior depends on all_files flag set during initialization:
        - If all_files=True: Returns ALL filtered Python files
        - If all_files=False: Returns ML pipeline files if available,
          otherwise falls back to all filtered files
        
        This is the PRIMARY method analyzers should use.
        Results are cached for efficiency.
        
        Returns:
            List of relative paths to Python files
        """
        if self._python_files_cache is not None:
            return self._python_files_cache
        
        if self._all_files:
            # Mode: Analyze ALL Python files
            self._python_files_cache = self._get_filtered_all_python_files()
        else:
            # Mode: Prefer ML files, fallback to all if no ML detected
            ml_files = self.get_all_ml_files()
            if ml_files:
                self._python_files_cache = ml_files
            else:
                self._python_files_cache = self._get_filtered_all_python_files()
        
        return self._python_files_cache
    
    def get_scan_mode(self) -> str:
        """
        Get a string describing the current scan mode.
        
        Useful for logging and reporting.
        
        Returns:
            'all_files': Analyzing all Python files (all_files=True)
            'ml_only': Analyzing only ML pipeline files
            'all_files_fallback': Analyzing all files because no ML detected
        """
        if self._all_files:
            return 'all_files'
        
        ml_files = self.get_all_ml_files()
        if ml_files:
            return 'ml_only'
        else:
            return 'all_files_fallback'
    
    def is_analyzing_all_files(self) -> bool:
        """
        Check if context is configured to analyze all files.
        
        Returns:
            True if all_files mode is enabled
        """
        return self._all_files
    
    def _get_filtered_all_python_files(self) -> List[str]:
        """
        Get list of all Python files in the project with filtering.
        
        Excludes:
        - __init__.py
        - __pycache__/ directories  
        - .pyc, .pyo files
        - Virtual environments (venv, .venv, env)
        - Site packages
        - Build/dist directories
        - Test cache directories
        
        Returns:
            List of relative paths to Python files
        """
        excluded_patterns = [
            '__init__.py',
            '__pycache__',
            '.pyc',
            '.pyo',
            'venv/',
            '.venv/',
            'env/',
            'site-packages/',
            'dist/',
            'build/',
            '.pytest_cache/',
            '.tox/'
        ]
        
        python_files = []
        
        for root, dirs, files in (self.local_path):
            # Filter out excluded directories in-place
            dirs[:] = [d for d in dirs if not any(
                excl.rstrip('/') in d for excl in excluded_patterns
            )]
            
            for file in files:
                if not file.endswith('.py'):
                    continue
                
                # Skip if matches exclusion pattern
                if any(pattern in file or pattern in root for pattern in excluded_patterns):
                    continue
                
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, self.local_path)
                python_files.append(rel_path)
        
        return python_files
    
    def get_all_python_files(self) -> List[str]:
        """
        Get list of ALL filtered Python files (ignores all_files flag).
        
        This is a lower-level method that always returns all files.
        Most analyzers should use get_python_files() instead.
        
        Excludes:
        - __init__.py
        - __pycache__/ directories  
        - .pyc, .pyo files
        - Virtual environments
        - Build/dist directories
        
        Returns:
            List of relative paths to Python files
        """
        return self._get_filtered_all_python_files()
    
    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._file_cache.clear()
        self._global_metrics.clear()
        self._python_files_cache = None
    
    def get_pipeline_metadata(self) -> Optional[Dict[str, Any]]:
        """
        Get pipeline detection metadata.
        
        Returns:
            Pipeline metadata from PipelineAnalyzer or None if not available
        """
        return self._pipeline_metadata
    def get_tree_metadata(self) -> Optional[Dict[str, Any]]:
        """
        Get tree structure metadata.
        
        Returns:
            Tree structure metadata from TreeGenerator or None if not available
        """
        return self._tree_metadata
    
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
