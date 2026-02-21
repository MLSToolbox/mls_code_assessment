import ast
import os
import json
from typing import Dict, List, Optional, Tuple, Set, Any
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
        manual_file_stages = overrides.file_stages
        excluded_patterns = list(set(overrides.excluded_files))

        base_detected_stages = auto_detected.get("detected_stages", {})
        base_file_stages = auto_detected.get("file_stages")
        if not isinstance(base_file_stages, dict):
            # Backward compatibility for sessions created before file_stages existed.
            base_file_stages = self._build_file_stages(
                detected_stages=base_detected_stages,
                all_python_files=self._get_python_files()
            )

        modified_file_stages: Dict[str, List[str]] = {
            filepath: list(dict.fromkeys(stages))
            for filepath, stages in base_file_stages.items()
        }

        # Exclude files from the baseline map.
        for filepath in list(modified_file_stages.keys()):
            if self._is_excluded(filepath, excluded_patterns):
                modified_file_stages.pop(filepath, None)

        # Apply manual overrides (including empty list to explicitly clear a file assignment).
        manual_files = set()
        for filepath, stages in manual_file_stages.items():
            if self._is_excluded(filepath, excluded_patterns):
                continue
            manual_files.add(filepath)
            modified_file_stages[filepath] = list(dict.fromkeys(stages))

        modified_detected_stages = self._build_detected_stages_from_file_stages(
            file_stages=modified_file_stages,
            base_detected_stages=base_detected_stages,
            manual_files=manual_files
        )

        missing_stages = self._get_missing_stages(modified_detected_stages)
        return {
            "is_valid_pipeline": len(missing_stages) == 0,
            "detected_stages": modified_detected_stages,
            "file_stages": dict(sorted(modified_file_stages.items())),
            "missing_stages": missing_stages,
            "files_analyzed": len(modified_file_stages)
        }
    
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
        _, stage_files = self._detect_pipeline()
        detected_stages = self._format_stages(stage_files)
        python_files = self._get_python_files()
        file_stages = self._build_file_stages(detected_stages, python_files)
        missing_stages = self._get_missing_stages(detected_stages)
        is_pipeline = len(missing_stages) == 0
        
        return self._create_result(
            score=10.0 if is_pipeline else 0.0,
            messages={},
            module_count=len(python_files),
            details={
                "is_valid_pipeline": is_pipeline,
                "detected_stages": detected_stages,
                "file_stages": file_stages,
                "missing_stages": missing_stages,
                "files_analyzed": len(python_files)
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
            "file_stages": result.details.get("file_stages", {}),
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
        Returns all files detected for each stage, sorted by confidence.
        
        Args:
            stage_files: Raw stage detection results
            
        Returns:
            Formatted dictionary suitable for API response
        """
        formatted: Dict[str, List[Dict[str, Any]]] = {}
        
        for stage, files in stage_files.items():
            # Group evidences by file
            file_evidences: Dict[str, List[Dict[str, str]]] = defaultdict(list)
            
            for filepath, method, value in files:
                file_evidences[filepath].append({
                    "method": method,
                    "value": value
                })
            
            if file_evidences:
                # Higher evidence count first, then filepath for deterministic output.
                sorted_files = sorted(
                    file_evidences.items(),
                    key=lambda item: (-len(item[1]), item[0])
                )
                formatted[stage] = [
                    {
                        "file": filepath,
                        "evidences": evidences
                    }
                    for filepath, evidences in sorted_files
                ]
        
        return dict(sorted(formatted.items()))
    
    def _get_missing_stages(self, detected_stages: Dict[str, List[Dict[str, Any]]]) -> List[str]:
        """
        Get list of required stages that are missing (stage absent or empty list).
        
        Args:
            detected_stages: Stage-centric detection structure
            
        Returns:
            List of missing stage names
        """
        present_required_stages = {
            stage
            for stage, files in detected_stages.items()
            if stage in self.required_stages and len(files) > 0
        }
        missing = self.required_stages - present_required_stages
        return sorted(missing)

    def _build_file_stages(
        self,
        detected_stages: Dict[str, List[Dict[str, Any]]],
        all_python_files: Optional[List[str]] = None
    ) -> Dict[str, List[str]]:
        """
        Build file-centric stage map, optionally including unmatched Python files.
        """
        file_stages: Dict[str, List[str]] = {}

        if all_python_files:
            for file_path in all_python_files:
                file_stages[file_path] = []

        for stage, files in detected_stages.items():
            for file_info in files:
                filepath = file_info.get("file")
                if not filepath:
                    continue
                if filepath not in file_stages:
                    file_stages[filepath] = []
                if stage not in file_stages[filepath]:
                    file_stages[filepath].append(stage)

        for filepath in file_stages:
            file_stages[filepath] = sorted(file_stages[filepath])

        return dict(sorted(file_stages.items()))

    def _build_detected_stages_from_file_stages(
        self,
        file_stages: Dict[str, List[str]],
        base_detected_stages: Dict[str, List[Dict[str, Any]]],
        manual_files: Optional[Set[str]] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Rebuild stage-centric representation from file-centric map.
        """
        evidence_lookup = self._build_evidence_lookup(base_detected_stages)
        manual_files = manual_files or set()
        rebuilt: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for filepath in sorted(file_stages.keys()):
            stages = file_stages[filepath]
            for stage in stages:
                evidences = evidence_lookup.get(stage, {}).get(filepath)

                if filepath in manual_files or not evidences:
                    evidences = [self._manual_override_evidence()]

                rebuilt[stage].append({
                    "file": filepath,
                    "evidences": evidences
                })

        return dict(sorted(rebuilt.items()))

    def _build_evidence_lookup(
        self,
        detected_stages: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Dict[str, List[Dict[str, str]]]]:
        """
        Build stage/file evidence lookup table from stage-centric metadata.
        """
        lookup: Dict[str, Dict[str, List[Dict[str, str]]]] = defaultdict(dict)

        for stage, files in detected_stages.items():
            for file_info in files:
                filepath = file_info.get("file")
                evidences = file_info.get("evidences", [])
                if not filepath:
                    continue
                lookup[stage][filepath] = [
                    {"method": ev.get("method", ""), "value": ev.get("value", "")}
                    for ev in evidences
                ]

        return lookup

    def _manual_override_evidence(self) -> Dict[str, str]:
        """Evidence marker for user-provided manual stage assignments."""
        return {
            "method": "manual",
            "value": "user_override"
        }
    
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
