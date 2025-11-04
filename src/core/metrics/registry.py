from core.metrics.metadata import MetricMetadata


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
        ideal_range={"min": -float('inf'), "max": 10.0, "optimal": ">8.0", "acceptable": "7.0-8.0", "warning": "<7.0"},
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
    
    "fpc": MetricMetadata(
        metric_id="fpc",
        name="Functional Pipeline Cohesion",
        description=(
            "Measures cohesion of ML pipeline code by analyzing how well functions and classes "
            "are organized around specific ML pipeline stages. Higher cohesion indicates better "
            "organized and more maintainable ML code. Focuses purely on functional cohesion "
            "without considering architectural patterns. Also detects and analyzes script-style "
            "files (loose code without functions) for pipeline stage alignment."
        ),
        formula=(
            "FPC = Weighted average of cohesion levels. "
            "High cohesion (10 pts): single stage. "
            "Medium cohesion (6 pts): single phase, multiple stages. "
            "Low cohesion (3 pts): multiple phases. "
            "Script-style files are analyzed as a single unit for stage detection."
        ),
        ideal_range={"min": 0, "max": 10, "optimal": ">7.0", "acceptable": "5.0-7.0", "warning": "<5.0"},
        interpretation={
            "high (7.0-10.0)": "Well-organized ML pipeline code with clear separation of concerns",
            "medium (4.0-6.9)": "Code organization is acceptable but could benefit from better structure",
            "low (0-3.9)": "Poorly organized code, consider restructuring around ML pipeline stages. Script-style files should be refactored into functions."
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