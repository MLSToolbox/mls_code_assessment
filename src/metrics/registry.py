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
            "CCPM uses a 5-level qualitative evaluation based on:\n"
            "1. Pipeline stages detected (data_collection, data_cleaning, feature_engineering, model_training, model_evaluation)\n"
            "2. Pipeline phases (data_engineering=[collection+cleaning], model_development=[feature+training+evaluation])\n"
            "3. ML content purity (ml_content_only: True=only ML code, False=mixed with non-ML code)\n"
            "4. Module size (NLOC threshold = 30 lines)\n\n"
            "Calculation steps in ccpm_analyzer.py:\n"
            "• _detect_stages(): Uses pipeline_stages.json to map keywords/imports/patterns → ML stages\n"
            "• MLContentAnalyzer.analyze(): Detects non-ML code (GUI, web frameworks, utilities) using ml_content_config.json\n"
            "• NLOCCalculator.calculate(): Counts non-comment lines of code\n"
            "• _determine_cohesion_level(): Assigns qualitative level based on stages/phases/ml_content_only/nloc\n"
            "• _calculate_cohesion_score(): Maps levels to numeric scores for aggregation\n\n"
            "Cohesion levels (with point mapping):\n"
            "• very_high (10 pts): 1 phase + 1 stage + ml_content_only=True\n"
            "• high (8 pts): 1 phase + 1 stage + ml_content_only=False OR 1 phase + >1 stage + ml_content_only=True + NLOC≤30\n"
            "• medium (5 pts): 1 phase + >1 stage + ml_content_only=False OR 1 phase + >1 stage + ml_content_only=True + NLOC>30\n"
            "• low (3 pts): 2+ phases + ml_content_only=True\n"
            "• very_low (1 pt): 2+ phases + ml_content_only=False\n\n"
            "Evaluation (ccpm_evaluator.py): Matches calculated metrics against ccpm_rules.json (10 rules) to generate diagnosis and recommendations."
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
    
    "lccml": MetricMetadata(
        metric_id="lccml",
        name="Loose Class Cohesion Modified for ML",
        description=(
            "Measures module cohesion specifically for ML code by analyzing connectivity between "
            "methods based on shared access to variables, data/model files, ML library functions, "
            "and direct method calls. Extended version of LCOM4 adapted for ML pipelines. "
            "Operates at module level (not class level) to handle both OO and script-style code."
        ),
        formula=(
            "LCCML = (Mv ∪ Mf ∪ Ml ∪ Mc) / (n(n-1)/2), where: "
            "n = number of methods in file, "
            "Mv = pairs connected by shared variables, "
            "Mf = pairs connected by shared data/model files, "
            "Ml = pairs connected by shared ML library functions, "
            "Mc = pairs connected by direct method calls (A calls B or B calls A)"
        ),
        ideal_range={"min": 0, "max": 1.0, "optimal": ">0.7", "acceptable": "0.5-0.7", "warning": "<0.5"},
        interpretation={
            "0.8-1.0": "Excellent - highly cohesive module, methods work together well",
            "0.6-0.79": "Good - reasonable cohesion, minor improvements possible",
            "0.4-0.59": "Moderate - consider refactoring to improve method connectivity",
            "0.2-0.39": "Low - module likely doing too many unrelated things",
            "0.0-0.19": "Very Low - module should be split into separate files"
        },
        references=[
            "Loose Class Cohesion (LCC) - Bieman & Kang, 1995",
            "LCOM4 - Hitz & Montazeri, 1995",
            "Adapted for ML pipelines - considers data files and ML library usage"
        ],
        category="cohesion"
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
            "SCPM = (2 × sum(P_ij)) / (n × (n-1))\n"
            "where P_ij = 1 if functions i and j share at least one:\n"
            "• Class attributes (self.x)\n"
            "• Module-level global variables (UPPERCASE or _private)\n"
            "• Constants (UPPERCASE naming convention)\n"
            "• Data files (datasets: .csv, .parquet, .json, .xlsx, etc.)\n"
            "• Model files (.pkl, .h5, .pt, .ckpt, etc.)\n"
            "• Config files (.yaml, .yml, .ini, .cfg, etc.)\n\n"
            "Calculation steps in scpm_analyzer.py:\n"
            "• _extract_methods(): Extracts all functions and class methods from AST\n"
            "• _get_variables_accessed(): Detects self.x and module-level globals using enhanced heuristics:\n"
            "  - Includes: UPPERCASE (>1 char), _private, common ML globals (data, model, X_train, etc.)\n"
            "  - Excludes: builtins (list, dict, str), imports (pd, np, os), ML types (DataFrame, Tensor, ndarray),\n"
            "              common locals (result, temp, i, j), type suffixes (Type, Class, Error)\n"
            "• _get_files_accessed(): Scans for string literals with 19 ML file extensions\n"
            "• For each pair of methods (i, j):\n"
            "  - Check if they share variables: vars_i ∩ vars_j ≠ ∅\n"
            "  - Check if they share files: files_i ∩ files_j ≠ ∅\n"
            "  - If either is true: P_ij = 1\n"
            "• _count_components(): LCOM analysis using DFS to find disconnected method groups\n"
            "• _determine_shared_type(): Classify sharing as class_attributes (>50%), global_variables (>50%),\n"
            "                           files (>50%), or mixed\n\n"
            "Cohesion levels:\n"
            "• very_high (0.8-1.0): Almost all method pairs share data\n"
            "• high (0.6-0.79): Most methods share data, good structural organization\n"
            "• medium (0.4-0.59): Moderate data sharing\n"
            "• low (0.2-0.39): Weak structural connections\n"
            "• very_low (0.0-0.19): Methods operate independently, minimal data sharing\n\n"
            "LCOM Enhancement: If n_components > 1, module contains disconnected groups → should split into separate modules.\n\n"
            "Evaluation (scpm_evaluator.py): Matches metrics against scpm_rules.json (12 rules) considering:\n"
            "- Cohesion level, n_components, shared_variable_count, shared_file_count, shared_type"
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
            "Measures functional connection between functions via information flow. "
            "Considers direct method invocations and data flow (producer-consumer relationships)."
        ),
        formula=(
            "IFC-M = (2 * sum(F_ij)) / (n * (n-1)), where F_ij = 1 if function i calls j "
            "OR i consumes data produced by j."
        ),
        ideal_range={"min": 0, "max": 1.0, "optimal": ">0.7", "acceptable": "0.5-0.7", "warning": "<0.5"},
        interpretation={
            "0.8-1.0": "Excellent - High functional cohesion",
            "0.6-0.79": "Good - Functions are well connected",
            "0.4-0.59": "Moderate - Some functional connections",
            "0.2-0.39": "Low - Few functional connections",
            "0.0-0.19": "Very Low - Functions operate independently"
        },
        references=["Internal Definition"],
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