import ast
import os
import json
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict

from core.analysis_result import AnalysisResult
from analyzers.pipeline.pipeline_overrides import PipelineOverrides
from analyzers.base_analyzer import BaseAnalyzer


class PipelineAnalyzer(BaseAnalyzer):
    
    def __init__(self, session_id: str, local_path: str, context=None, config_path: Optional[str] = None):
        super().__init__(session_id, local_path, context)
        
        # Required stages for a valid pipeline
        self.required_stages = {
            "data_collection",
            "model_training",
            "model_evaluation"
        }
        
        # Load configuration
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                self.config = json.load(f)
        else:
            # Default configuration
            config_file = os.path.join(
                os.path.dirname(__file__), 
                "pipeline_stages.json"
            )
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    self.config = json.load(f)
            else:
                self.config = self._default_config()
    
    @property
    def analyzer_id(self) -> str:
        return "pipeline_detection"
    
    def apply_overrides(
        self, 
        auto_detected: Dict, 
        overrides: PipelineOverrides
    ) -> Dict:
        """
        Apply user overrides to auto-detected pipeline.
        
        Args:
            auto_detected: Auto-detected pipeline structure
            overrides: User-provided overrides
            
        Returns:
            Modified pipeline structure
        """
        file_stages = overrides.file_stages
        excluded_files = overrides.excluded_files
        
        # Copy original structure
        modified = {
            "is_valid_pipeline": auto_detected["is_valid_pipeline"],
            "detected_stages": {},
            "missing_stages": auto_detected["missing_stages"].copy(),
            "files_analyzed": auto_detected["files_analyzed"]
        }
        
        # Process excluded files
        excluded_set = set()
        for pattern in excluded_files:
            excluded_set.add(pattern)
        
        # Apply file exclusions and manual stage assignments
        for stage, file_list in auto_detected["detected_stages"].items():
            modified["detected_stages"][stage] = []
            
            for file_info in file_list:
                filepath = file_info["file"]
                
                # Check if file should be excluded
                if self._is_excluded(filepath, list(excluded_set)):
                    continue
                
                # Check if file has manual override
                if filepath in file_stages:
                    # Only include if this stage is in manual assignment
                    if stage in file_stages[filepath]:
                        modified["detected_stages"][stage].append({
                            "file": filepath,
                            "evidences": [
                                {
                                    "method": "manual",
                                    "value": "user_override"
                                }
                            ]
                        })
                else:
                    # Keep auto-detected
                    modified["detected_stages"][stage].append(file_info)
        
        # Add manually assigned stages not in auto-detected
        for filepath, stages in file_stages.items():
            if self._is_excluded(filepath, list(excluded_set)):
                continue
            
            for stage in stages:
                # Initialize stage if not exists
                if stage not in modified["detected_stages"]:
                    modified["detected_stages"][stage] = []
                
                # Check if file already exists in this stage
                exists = any(
                    f["file"] == filepath 
                    for f in modified["detected_stages"][stage]
                )
                
                if not exists:
                    modified["detected_stages"][stage].append({
                        "file": filepath,
                        "evidences": [
                            {
                                "method": "manual",
                                "value": "user_override"
                            }
                        ]
                    })
        
        # Recalculate missing stages
        detected_stage_names = set(modified["detected_stages"].keys())
        modified["missing_stages"] = list(
            self.required_stages - detected_stage_names
        )
        
        # Recalculate validity
        modified["is_valid_pipeline"] = len(modified["missing_stages"]) == 0
        
        # Update file count (exclude excluded files)
        modified["files_analyzed"] = sum(
            len(files) for files in modified["detected_stages"].values()
        )
        
        return modified
    
    def _is_excluded(self, filepath: str, patterns: List[str]) -> bool:
        """
        Check if filepath matches exclusion patterns.
        
        Supports both directory patterns (ending with /) and file patterns.
        
        Args:
            filepath: Path to check
            patterns: List of exclusion patterns
            
        Returns:
            True if filepath should be excluded
        """
        for pattern in patterns:
            # Pattern ending with / means directory
            if pattern.endswith('/'):
                # Check if path starts with pattern or contains it as directory
                if filepath.startswith(pattern) or f"/{pattern}" in filepath:
                    return True
            # Exact substring match for files
            elif pattern in filepath:
                return True
        return False
    
    def analyze(self) -> AnalysisResult:
        """
        Execute pipeline analysis.
        
        Returns:
            AnalysisResult with pipeline detection details
        """
        is_pipeline, stage_files = self._detect_pipeline()
        
        detected_stages = self._format_stages(stage_files)
        missing_stages = self._get_missing_stages(stage_files)
        
        all_files = self._get_python_files()
        
        return self._create_result(
            score=10.0 if is_pipeline else 0.0,
            messages={},
            module_count=len(all_files),
            details={
                "is_valid_pipeline": is_pipeline,
                "detected_stages": detected_stages,
                "missing_stages": missing_stages,
                "files_analyzed": len(all_files)
            }
        )
    
    def generate_report(self, code_path: str = None) -> bytes:
        """
        Generate detailed pipeline analysis report.
        
        Args:
            code_path: Optional path to code (uses self.local_path if not provided)
            
        Returns:
            Report as bytes (JSON format)
        """
        # Run analysis
        result = self.analyze()
        
        # Create detailed report
        report = {
            "analyzer": self.analyzer_id,
            "session_id": self.session_id,
            "is_valid_pipeline": result.details["is_valid_pipeline"],
            "detected_stages": result.details["detected_stages"],
            "missing_stages": result.details["missing_stages"],
            "files_analyzed": result.details["files_analyzed"],
            "score": result.score,
            "summary": {
                "total_stages_detected": len(result.details["detected_stages"]),
                "required_stages": list(self.required_stages),
                "pipeline_status": "valid" if result.details["is_valid_pipeline"] else "incomplete"
            }
        }
        
        # Convert to JSON bytes
        import json
        return json.dumps(report, indent=2).encode('utf-8')
    
    def _detect_pipeline(self) -> Tuple[bool, Dict[str, List[Tuple[str, str, str]]]]:
        """
        Detect pipeline stages in code.
        
        Returns:
            Tuple of (is_valid_pipeline, stage_files_dict)
        """
        stage_files: Dict[str, List[Tuple[str, str, str]]] = defaultdict(list)
        
        python_files = self._get_python_files()
        
        for filepath in python_files:
            detected = self._analyze_file(filepath)
            for stage, evidences in detected.items():
                for method, value in evidences:
                    stage_files[stage].append((filepath, method, value))
        
        # Check if all required stages are present
        detected_stages = set(stage_files.keys())
        is_valid = self.required_stages.issubset(detected_stages)
        
        return is_valid, stage_files
    
    def _analyze_file(self, filepath: str) -> Dict[str, List[Tuple[str, str]]]:
        """
        Analyze a single file for pipeline stages.
        
        Args:
            filepath: Path to Python file (relative or absolute)
            
        Returns:
            Dictionary mapping stages to evidences
        """
        detected: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        
        try:
            # Convert to absolute path if relative
            if not os.path.isabs(filepath):
                full_path = os.path.join(self.local_path, filepath)
            else:
                full_path = filepath
            
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            # Check each stage
            for stage, config in self.config["stages"].items():
                # Filename detection
                filename = os.path.basename(filepath).lower()
                for pattern in config["filename_patterns"]:
                    if pattern.lower() in filename:
                        detected[stage].append(("filename", pattern))
                
                # Keyword detection in code
                for keyword in config["keywords"]:
                    if keyword.lower() in content.lower():
                        detected[stage].append(("keyword", keyword))
                
                # Import detection
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name in config["imports"]:
                                detected[stage].append(("import", alias.name))
                    elif isinstance(node, ast.ImportFrom):
                        if node.module and node.module in config["imports"]:
                            detected[stage].append(("import", node.module))
        
        except Exception:
            pass  # Skip files that can't be parsed
        
        return detected
    
    def _format_stages(self, stage_files: Dict[str, List[Tuple]]) -> Dict:
        """
        Format stage detection results for API response.
        Returns only the file with most evidences per stage.
        
        Args:
            stage_files: Raw stage detection results
            
        Returns:
            Formatted dictionary suitable for API response
        """
        formatted = {}
        
        for stage, files in stage_files.items():
            # Group evidences by file
            file_evidences = defaultdict(list)
            
            for filepath, method, value in files:
                file_evidences[filepath].append({
                    "method": method,
                    "value": value
                })
            
            # Select only the file with most evidences
            if file_evidences:
                best_file = max(
                    file_evidences.items(),
                    key=lambda x: len(x[1])
                )
                
                formatted[stage] = [
                    {
                        "file": best_file[0],
                        "evidences": best_file[1]
                    }
                ]
        
        return formatted
    
    def _get_missing_stages(self, stage_files: Dict) -> List[str]:
        """
        Get list of required stages that are missing.
        
        Args:
            stage_files: Detected stage files
            
        Returns:
            List of missing stage names
        """
        detected_stages = set(stage_files.keys())
        missing = self.required_stages - detected_stages
        return list(missing)
    
    def _get_python_files(self) -> List[str]:
        """
        Get all Python files in the workspace.
        
        Returns:
            List of Python file paths
        """
        python_files = []
        
        # Excluded directories
        exclude_dirs = {
            '__pycache__', '.git', 'venv', 'env', 
            'node_modules', '.vscode', '.idea'
        }
        
        for root, dirs, files in os.walk(self.local_path):
            # Remove excluded directories from search
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    # Make path relative to local_path
                    rel_path = os.path.relpath(filepath, self.local_path)
                    python_files.append(rel_path)
        
        return python_files
    
    def _default_config(self) -> Dict:
        """
        Return default pipeline configuration.
        
        Returns:
            Default configuration dictionary
        """
        return {
            "stages": {
                "data_collection": {
                    "filename_patterns": ["load", "collect", "fetch", "download"],
                    "keywords": ["read_csv", "read_excel", "read_json", "load_data"],
                    "imports": ["pandas", "numpy", "requests"]
                },
                "data_cleaning": {
                    "filename_patterns": ["clean", "preprocess", "prepare"],
                    "keywords": ["dropna", "fillna", "drop_duplicates", "clean"],
                    "imports": ["pandas", "numpy"]
                },
                "feature_engineering": {
                    "filename_patterns": ["feature", "transform", "encode"],
                    "keywords": ["fit_transform", "transform", "encode", "scale"],
                    "imports": ["sklearn.preprocessing", "sklearn.feature_extraction"]
                },
                "model_training": {
                    "filename_patterns": ["train", "model", "fit"],
                    "keywords": ["fit(", "train", "model.fit"],
                    "imports": ["sklearn", "tensorflow", "keras", "torch"]
                },
                "model_evaluation": {
                    "filename_patterns": ["eval", "test", "validate", "score"],
                    "keywords": ["score", "evaluate", "predict", "accuracy"],
                    "imports": ["sklearn.metrics"]
                }
            }
        }