from metrics.metadata import MetricMetadata


METRICS_REGISTRY = {
    "radon_cc": MetricMetadata(
        metric_id="radon_cc",
        name="Cyclomatic Complexity",
        description=(
            "Measures code complexity by counting independent paths through code. "
            "Higher values indicate more complex, harder to test code."
        ),
        formula="CC = E - N + 2P (E=edges, N=nodes, P=connected components)",
        ideal_range={"min": 1, "max": 10, "optimal": "1-5", "acceptable": "6-10", "warning": ">10"},
        interpretation={
            "1-5": "Simple, easy to test",
            "6-10": "More complex, acceptable",
            "11-20": "Complex, consider refactoring",
            ">20": "Very complex, refactoring needed"
        },
        references=[
            "https://radon.readthedocs.io/en/latest/intro.html",
            "https://en.wikipedia.org/wiki/Cyclomatic_complexity"
        ],
        category="complexity"
    ),
    
    "radon_mi": MetricMetadata(
        metric_id="radon_mi",
        name="Maintainability Index",
        description=(
            "Composite metric measuring code maintainability based on complexity, "
            "volume, and comments. Higher values indicate more maintainable code."
        ),
        formula="MI = 171 - 5.2*ln(V) - 0.23*G - 16.2*ln(L) (V=volume, G=complexity, L=lines)",
        ideal_range={"min": 0, "max": 100, "optimal": ">20", "acceptable": "10-20", "warning": "<10"},
        interpretation={
            "20-100": "Maintainable",
            "10-19": "Moderate maintainability",
            "0-9": "Difficult to maintain"
        },
        references=["https://radon.readthedocs.io/en/latest/intro.html"],
        category="maintainability"
    ),
    
    "pylint_score": MetricMetadata(
        metric_id="pylint_score",
        name="Code Quality Score",
        description=(
            "Evaluates code against PEP 8 style guide, detects errors, enforces coding standards, "
            "and finds code smells."
        ),
        formula=(
            "Score = 10.0 - ((float(5 * error + warning + refactor + convention) / statement) * 10)"
        ),
        ideal_range={"min": None, "max": 10.0, "optimal": ">8.0", "acceptable": "7.0-8.0", "warning": "<7.0"},
        interpretation={
            "9.0-10.0": "Excellent - very few issues detected",
            "8.0-8.9": "Good - minor improvements possible",
            "7.0-7.9": "Acceptable - consider addressing warnings",
            "5.0-6.9": "Needs improvement - multiple issues found",
            "<5.0": "Poor - significant refactoring needed"
        },
        references=[
            "https://pylint.pycqa.org/en/latest/",
            "https://peps.python.org/pep-0008/"
        ],
        category="quality"
    ),
    
    "ccpm": MetricMetadata(
        metric_id="ccpm",
        name="Conceptual Cohesion of Pipeline Modules",
        description=(
            "Measures cohesion of ML pipeline code by analyzing how well functions and classes "
            "are organized around specific ML pipeline stages. Higher cohesion indicates better "
            "organized and more maintainable ML code. Focuses purely on functional cohesion "
            "without considering architectural patterns. Also detects and analyzes script-style "
            "files (loose code without functions) for pipeline stage alignment."
        ),
        formula=(
            "CCPM uses a 5-level qualitative evaluation to detect modules mixing responsibilities "
            "from different ML pipeline tasks/stages (SRP violations).\n\n"
            "=== DECISION TABLE ===\n"
            "Stages | Phases | ML_Only | NLOC>30 | Level      | Points | Interpretation\n"
            "-------|--------|---------|---------|------------|--------|------------------\n"
            "1      | 1      | Yes     | Yes     | very_high  | 10     | Perfect SRP: Single stage, pure ML\n"
            "1      | 1      | No      | Yes     | high       | 8      | Single stage + non-ML code mixed\n"
            "1      | 1      | Yes/No  | No      | high       | 8      | Single stage but small file (<30 lines)\n"
            ">1     | 1      | Yes/No  | Yes/No  | medium     | 5      | Multiple stages, same phase (related)\n"
            "≥1     | ≥2     | Yes     | Yes/No  | low        | 3      | Mixes unrelated phases, ML only\n"
            "≥1     | ≥2     | No      | Yes/No  | very_low   | 1      | Mixes unrelated phases + non-ML code\n"
            "0      | -      | -       | -       | non_ml_file| -      | No ML content (not scored)\n\n"
            "=== CALCULATION PROCESS ===\n"
            "1. Pipeline Stage Detection (pipeline_stages.json):\n"
            "   - Stages: data_collection, data_cleaning, feature_engineering, model_training, model_evaluation\n"
            "   - Detection via: keywords, imports, filename patterns, pipeline metadata\n\n"
            "2. Phase Grouping:\n"
            "   - data_engineering = {data_collection, data_cleaning}\n"
            "   - model_development = {feature_engineering, model_training, model_evaluation}\n\n"
            "3. ML Content Analysis (ml_content_config.json):\n"
            "   - ml_content_only=True: Only ML pipeline code\n"
            "   - ml_content_only=False: Mixed ML + non-ML (GUI, web frameworks, utilities)\n\n"
            "4. NLOC Calculation (Non-comment Lines of Code):\n"
            "   - Threshold: 30 lines\n"
            "   - Rationale: Small modules (<30) with multiple stages don't severely violate SRP\n\n"
            "5. Cohesion Level Assignment:\n"
            "   - _determine_cohesion_level() applies decision table\n\n"
            "6. Aggregate Score Calculation:\n"
            "   CCPM_Score = (Σ points_i / (n × 10)) × 10\n"
            "   where n = number of ML files (excludes non_ml_file)\n"
            "   Result normalized to 0-10 scale\n\n"
            "=== IMPLEMENTATION METHODS (ccpm_analyzer.py) ===\n"
            "• _detect_stages(): Maps keywords/imports/patterns → ML stages\n"
            "• MLContentAnalyzer.analyze(): Detects non-ML code using ml_content_config.json\n"
            "• NLOCCalculator.calculate(): Counts non-comment lines\n"
            "• _determine_cohesion_level(): Assigns level per decision table\n"
            "• _calculate_cohesion_score(): Aggregates file scores to project score\n\n"
            "=== EVALUATION (ccpm_evaluator.py) ===\n"
            "Matches metrics against ccpm_rules.json (10 rules) to generate diagnosis and recommendations."
        ),
        ideal_range={"min": 0, "max": 10, "optimal": ">7.0", "acceptable": "5.0-7.0", "warning": "<5.0"},
        interpretation={
            "very_high (10)": "Excellent - Single stage, pure ML code, optimal SRP compliance",
            "high (8)": "Good - Single stage or phase with minor impurities or small multi-stage modules",
            "medium (5)": "Moderate - Multiple stages in same phase or mixed ML/non-ML code",
            "low (3)": "Poor - Multiple phases mixed, violates SRP, needs refactoring",
            "very_low (1)": "Critical - Multiple phases + non-ML code mixed, severe SRP violation"
        },
        references=["https://github.com/MLS-Toobox/mls_code_generator"],
        category="cohesion"
    ),
    
    
    "file_structure": MetricMetadata(
        metric_id="file_structure",
        name="File Structure Quality",
        description=(
            "Evaluates Python file organization patterns. Identifies whether files follow "
            "OOP principles (classes only), functional style (functions only), script style "
            "(loose code), or anti-patterns (mixed classes/functions or mixed structured/loose code). "
            "Promotes architectural consistency and separation of concerns."
        ),
        formula=(
            "Score = (classes_only * 1.0 + functions_only * 0.9 + script_only * 0.6 + "
            "mixed * 0.5 + mixed_script * 0.3) / total_files * 10. "
            "Classes-only pattern receives highest weight (1.0), functional style is acceptable (0.9), "
            "script-style is poor (0.6), mixed classes+functions is anti-pattern (0.5), "
            "and mixed structured+loose code is critical anti-pattern (0.3)."
        ),
        ideal_range={"min": 0, "max": 10, "optimal": ">8.0", "acceptable": "6.0-8.0", "warning": "<6.0"},
        interpretation={
            "9.0-10.0": "Excellent - consistent OOP or functional patterns throughout",
            "7.0-8.9": "Good - mostly consistent with few script-style files",
            "6.0-6.9": "Acceptable - some script-style or mixed pattern files",
            "4.0-5.9": "Poor - many anti-patterns, architectural inconsistency",
            "3.0-3.9": "Critical - severe anti-patterns with mixed script code",
            "<3.0": "Critical - predominant use of mixed script anti-pattern, immediate refactoring needed"
        },
        references=[
            "https://peps.python.org/pep-0008/",
            "https://en.wikipedia.org/wiki/Separation_of_concerns"
        ],
        category="structure"
    ),
    
    "pipeline_detection": MetricMetadata(
        metric_id="pipeline_detection",
        name="ML Pipeline Detection",
        description=(
            "Detects and maps ML pipeline stages in the codebase. Identifies which files and "
            "functions belong to different stages and provides insights into pipeline structure."
        ),
        formula=None,
        ideal_range={},
        interpretation={
            "comprehensive": "All major ML pipeline stages detected",
            "partial": "Some pipeline stages detected, others may be missing",
            "minimal": "Few or no ML pipeline patterns detected"
        },
        references=["https://github.com/MLS-Toobox/mls_code_generator"],
        category="detection"
    ),

    "scpm": MetricMetadata(
        metric_id="scpm",
        name="Structural Cohesion of Pipeline Modules",
        description=(
            "Measures how much functions within a module share DATA or STRUCTURES. "
            "Higher values indicate that methods are tightly coupled through shared data access, "
            "which suggests good structural cohesion. Focuses on structural connections only "
            "(variables and files), excluding functional connections (method calls)."
        ),
        formula=(
            "=== MATHEMATICAL FORMULA ===\n"
            "SCPM = LDSC(M) = (2 × Σ(i<j) P_ij) / (n × (n - 1))\n\n"
            "Where:\n"
            "• n = number of methods/functions in the module\n"
            "• P_ij = 1 if methods i and j share at least one data structure or file\n"
            "• P_ij = 0 otherwise\n"
            "• Result range: [0.0, 1.0] (0 = minimum cohesion, 1 = maximum cohesion)\n\n"
            "=== WHAT COUNTS AS SHARED (P_ij = 1) ===\n"
            "Methods share if they access at least one common:\n"
            "1. Class attributes: self.attribute_name\n"
            "2. Module-level global variables:\n"
            "   - UPPERCASE constants (e.g., CONFIG, DATA_PATH)\n"
            "   - _private variables (e.g., _cache, _model)\n"
            "   - Common ML globals (data, model, X_train, y_train, scaler, etc.)\n"
            "3. Data files: .csv, .parquet, .json, .xlsx, .feather, .avro, etc.\n"
            "4. Model files: .pkl, .h5, .pt, .ckpt, .pb, .onnx, .weights, etc.\n"
            "5. Config files: .yaml, .yml, .ini, .cfg, .toml, etc.\n\n"
            "=== CALCULATION PROCESS (scpm_analyzer.py) ===\n\n"
            "Step 1: Extract Methods\n"
            "  • _extract_methods(): Parse AST to get all functions and class methods\n"
            "  • Qualified names: ClassName.method_name or function_name\n\n"
            "Step 2: Detect Variables Accessed\n"
            "  • _get_variables_accessed(method_node):\n"
            "    - Scans AST for ast.Attribute nodes → detects self.x\n"
            "    - Scans ast.Name nodes → detects global variables\n"
            "  • Enhanced heuristics:\n"
            "    ✓ Includes: UPPERCASE (>1 char), _private, common ML names\n"
            "    ✗ Excludes: builtins (list, dict, str), imports (pd, np, os),\n"
            "                ML types (DataFrame, Tensor), locals (result, temp, i, j),\n"
            "                type suffixes (Type, Class, Error)\n\n"
            "Step 3: Detect Files Accessed\n"
            "  • _get_files_accessed(method_node):\n"
            "    - Scans for string literals containing file extensions\n"
            "    - 30+ ML file extensions supported (data, model, config files)\n\n"
            "Step 4: Build Connectivity Graph\n"
            "  For each pair of methods (i, j) where i < j:\n"
            "    shared_vars = vars_i ∩ vars_j    # Set intersection of variables\n"
            "    shared_files = files_i ∩ files_j  # Set intersection of files\n"
            "    \n"
            "    if shared_vars OR shared_files:\n"
            "      P_ij = 1\n"
            "      adjacency[i].add(j)  # Add edge to graph\n"
            "      adjacency[j].add(i)\n"
            "    else:\n"
            "      P_ij = 0\n\n"
            "Step 5: Calculate SCPM Score\n"
            "  total_pairs = n × (n - 1) / 2\n"
            "  shared_pairs = count of pairs where P_ij = 1\n"
            "  SCPM = (2 × shared_pairs) / (n × (n - 1))\n"
            "       = shared_pairs / total_pairs\n\n"
            "Step 6: LCOM Analysis (Lack of Cohesion of Methods)\n"
            "  • count_components(adjacency, methods):\n"
            "    - Uses DFS (Depth-First Search) on connectivity graph\n"
            "    - Finds disconnected groups of methods\n"
            "    - n_components > 1 → module violates SRP, should split\n"
            "  • identify_disconnected_methods(adjacency, methods):\n"
            "    - Finds methods with NO connections (isolated nodes)\n"
            "    - Candidates for extraction to separate modules\n"
            "  • Special methods (__init__, __str__) excluded from LCOM analysis\n\n"
            "Step 7: Classify Sharing Type\n"
            "  • _determine_shared_type(shared_vars, shared_files):\n"
            "    - 'class_attributes': >50% are self.x\n"
            "    - 'global_variables': >50% are module-level globals\n"
            "    - 'files': >50% are shared files\n"
            "    - 'mixed': No single type dominates\n\n"
            "Step 8: Categorize Cohesion Level\n"
            "  • _categorize_cohesion(scpm):\n"
            "    [0.8-1.0]: very_high\n"
            "    [0.6-0.8): high\n"
            "    [0.4-0.6): medium\n"
            "    [0.2-0.4): low\n"
            "    [0.0-0.2): very_low\n\n"
            "=== EXAMPLE CALCULATION ===\n"
            "Module with 4 methods: f1, f2, f3, f4\n"
            "Shared data:\n"
            "  f1 & f2: share self.data\n"
            "  f1 & f3: share 'model.pkl'\n"
            "  f2 & f3: share CONFIG\n"
            "  f4: shares nothing\n\n"
            "Total pairs = 4×3/2 = 6 pairs\n"
            "Shared pairs = 3 (f1-f2, f1-f3, f2-f3)\n"
            "SCPM = 3/6 = 0.50 → medium cohesion\n"
            "n_components = 2 (group {f1,f2,f3} and isolated {f4})\n"
            "disconnected_methods = ['f4']\n\n"
            "=== EVALUATION (scpm_evaluator.py) ===\n"
            "Matches metrics against scpm_rules.json (14 rules) considering:\n"
            "• cohesion_level, n_components, n_disconnected_methods\n"
            "• shared_variable_count, shared_file_count, shared_type\n"
            "• Generates specific diagnosis and refactoring recommendations"
        ),
        ideal_range={"min": 0, "max": 1.0, "optimal": ">0.8", "acceptable": "0.6-0.8", "warning": "<0.6"},
        interpretation={
            "very_high (0.8-1.0)": "Excellent - Maximum structural cohesion, methods highly interconnected through shared data",
            "high (0.6-0.79)": "Good - Strong data sharing between methods, well-organized module",
            "medium (0.4-0.59)": "Moderate - Some data sharing exists, consider improving organization",
            "low (0.2-0.39)": "Poor - Weak structural connections, methods operate too independently",
            "very_low (0.0-0.19)": "Critical - Minimal data sharing, module likely violates SRP, needs refactoring"
        },
        references=["LDSC - Local Data Structure Cohesion (Internal Definition)"],
        category="cohesion"
    ),

    "fcpm": MetricMetadata(
        metric_id="fcpm",
        name="Functional Cohesion of Pipeline Modules",
        description=(
            "Measures functional cohesion through method invocation patterns. "
            "Analyzes how methods collaborate by calling each other (directly or indirectly), "
            "indicating if they work together toward a common functional goal. Complementary "
            "to SCPM (structural cohesion), focusing on behavioral relationships rather than data sharing."
        ),
        formula=(
            "=== MATHEMATICAL FORMULA ===\n"
            "FCPM = (2 × Σ(i<j) F_ij) / (n × (n - 1))\n\n"
            "Where:\n"
            "• n = number of methods/functions in the module\n"
            "• F_ij = 1 if methods i and j have functional relationship (direct or indirect invocation)\n"
            "• F_ij = 0 otherwise\n"
            "• Result range: [0.0, 1.0] (0 = minimum cohesion, 1 = maximum cohesion)\n\n"
            "=== CONDITIONS FOR F_ij = 1 (Functional Connection) ===\n\n"
            "Two methods i and j are functionally connected if ANY of:\n\n"
            "1. **Direct Invocation (Method Calls Method)**:\n"
            "   • f_i → f_j  (method i calls method j)\n"
            "   • f_j → f_i  (method j calls method i)\n"
            "   • Bidirectional relationship (either direction counts)\n\n"
            "2. **Indirect Invocation (Both Call Common Helper)**:\n"
            "   • f_i → f_t AND f_j → f_t\n"
            "   • Both methods call a third function f_t\n"
            "   • CRITICAL: f_t must belong to the SAME module/class\n"
            "   • Represents collaboration through shared helper functions\n\n"
            "If neither condition is met: F_ij = 0\n\n"
            "=== CALCULATION PROCESS (fcpm_analyzer.py) ===\n\n"
            "Step 1: Extract Methods\n"
            "  • _extract_methods(): Parse AST to get all functions and class methods\n"
            "  • Qualified names: ClassName.method_name or function_name\n\n"
            "Step 2: Build Call Graph\n"
            "  • _build_call_graph(methods):\n"
            "    - For each method, detect which other methods it calls\n"
            "    - Returns: {method_name: [list of methods it calls]}\n"
            "  • _get_method_calls(method_node, all_methods):\n"
            "    - Scans AST for ast.Call nodes\n"
            "    - Identifies function names from ast.Name and ast.Attribute\n"
            "    - Matches against all_methods to find internal calls\n\n"
            "Step 3: Detect Connected Pairs\n"
            "  For each pair of methods (i, j) where i < j:\n"
            "  \n"
            "    # Check DIRECT invocation\n"
            "    is_direct = (j in call_graph[i]) OR (i in call_graph[j])\n"
            "    \n"
            "    # Check INDIRECT invocation\n"
            "    calls_i = set(call_graph[i])\n"
            "    calls_j = set(call_graph[j])\n"
            "    common_callees = calls_i ∩ calls_j\n"
            "    common_internal = common_callees ∩ {methods in same module}\n"
            "    is_indirect = (common_internal ≠ ∅)\n"
            "    \n"
            "    # Set F_ij\n"
            "    if is_direct OR is_indirect:\n"
            "      F_ij = 1\n"
            "      connected_pairs.append((i, j))\n"
            "      adjacency[i].append(j)  # Add edge to graph\n"
            "      adjacency[j].append(i)\n"
            "      \n"
            "      if is_direct:\n"
            "        direct_invocations += 1\n"
            "      else:  # is_indirect\n"
            "        indirect_invocations += 1\n"
            "    else:\n"
            "      F_ij = 0\n\n"
            "Step 4: Calculate FCPM Score\n"
            "  total_pairs = n × (n - 1) / 2\n"
            "  n_connected_pairs = count of pairs where F_ij = 1\n"
            "  FCPM = (2 × n_connected_pairs) / (n × (n - 1))\n"
            "       = n_connected_pairs / total_pairs\n\n"
            "Step 5: LCOM Analysis (Lack of Cohesion of Methods)\n"
            "  • count_components(adjacency, methods):\n"
            "    - Uses DFS on functional connectivity graph\n"
            "    - Finds disconnected functional groups (workflows)\n"
            "    - n_components > 1 → module contains independent workflows\n"
            "  • identify_disconnected_methods(adjacency, methods):\n"
            "    - Finds methods with NO invocation relationships\n"
            "    - Methods that neither call nor are called by others\n"
            "  • Special methods (__init__, __str__) excluded from LCOM\n\n"
            "Step 6: Categorize Cohesion Level\n"
            "  • _categorize_cohesion(fcpm):\n"
            "    [0.8-1.0]: very_high\n"
            "    [0.6-0.8): high\n"
            "    [0.4-0.6): medium\n"
            "    [0.2-0.4): low\n"
            "    [0.0-0.2): very_low\n\n"
            "=== EXAMPLE CALCULATION ===\n\n"
            "Module with 4 methods: f1, f2, f3, f4\n\n"
            "Call graph:\n"
            "  f1 calls: [f2, helper]\n"
            "  f2 calls: [helper]\n"
            "  f3 calls: [f2]\n"
            "  f4 calls: []\n"
            "  helper calls: []\n\n"
            "Analysis:\n"
            "  f1-f2: DIRECT (f1 → f2) → F_12 = 1\n"
            "  f1-f3: INDIRECT (both call helper) → F_13 = 1\n"
            "  f1-f4: NO connection → F_14 = 0\n"
            "  f2-f3: DIRECT (f3 → f2) → F_23 = 1\n"
            "  f2-f4: NO connection → F_24 = 0\n"
            "  f3-f4: NO connection → F_34 = 0\n\n"
            "Wait, let me recalculate including helper:\n"
            "  n = 5 methods (f1, f2, f3, f4, helper)\n"
            "  total_pairs = 5×4/2 = 10 pairs\n"
            "  \n"
            "  Connected pairs:\n"
            "  • f1-f2: DIRECT ✓\n"
            "  • f1-helper: DIRECT ✓\n"
            "  • f2-helper: DIRECT ✓\n"
            "  • f2-f3: DIRECT ✓\n"
            "  • f1-f2: INDIRECT via helper (already counted as direct)\n"
            "  \n"
            "  n_connected = 4\n"
            "  FCPM = 4/10 = 0.40 → medium cohesion\n"
            "  \n"
            "  n_components = 2 (group {f1,f2,f3,helper} and isolated {f4})\n"
            "  disconnected_methods = ['f4']\n"
            "  breakdown:\n"
            "    direct_invocations: 4\n"
            "    indirect_invocations: 0 (already counted in direct)\n\n"
            "=== BREAKDOWN METRICS ===\n\n"
            "The analysis provides:\n"
            "• direct_invocations: Count of pairs connected by direct calls\n"
            "• indirect_invocations: Count of pairs connected ONLY via common helper\n"
            "• Note: A pair can't be both (direct takes precedence)\n\n"
            "=== EVALUATION (fcpm_evaluator.py) ===\n\n"
            "Matches metrics against fcpm_rules.json (14 rules) considering:\n"
            "• cohesion_level: very_low | low | medium | high | very_high\n"
            "• n_components: Number of disconnected functional groups\n"
            "• n_disconnected_methods: Count of methods with no connections\n"
            "• disconnected_methods: List of isolated method names\n"
            "• breakdown: {direct_invocations, indirect_invocations}\n\n"
            "Generates diagnosis and recommendations, often cross-referencing SCPM:\n"
            "• Low FCPM + Low SCPM → Extract to separate modules\n"
            "• Low FCPM + High SCPM → Methods share data but don't collaborate\n"
            "• High FCPM + Low SCPM → Methods collaborate but don't share state"
        ),
        ideal_range={"min": 0, "max": 1.0, "optimal": ">0.8", "acceptable": "0.6-0.8", "warning": "<0.6"},
        interpretation={
            "very_high (0.8-1.0)": "Excellent - Maximum functional cohesion, methods highly interconnected via invocations",
            "high (0.6-0.79)": "Good - Strong functional collaboration between methods",
            "medium (0.4-0.59)": "Moderate - Some invocation relationships exist",
            "low (0.2-0.39)": "Poor - Weak functional connections, methods operate too independently",
            "very_low (0.0-0.19)": "Critical - Minimal invocations, methods likely violate SRP, needs refactoring"
        },
        references=["FCPM - Functional Cohesion of Pipeline Modules (Internal Definition)"],
        category="cohesion"
    ),
}


def get_metric_metadata(metric_id: str) -> MetricMetadata:
    """
    Retrieve metadata for a specific metric.
    
    Args:
        metric_id: Unique identifier for the metric
        
    Returns:
        MetricMetadata object
        
    Raises:
        KeyError: If metric_id not found in registry
    """
    if metric_id not in METRICS_REGISTRY:
        raise KeyError(
            f"Metric '{metric_id}' not found. Available: {list(METRICS_REGISTRY.keys())}"
        )
    return METRICS_REGISTRY[metric_id]