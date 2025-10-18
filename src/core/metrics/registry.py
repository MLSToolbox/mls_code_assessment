from typing import Dict
from .metadata import MetricMetadata


METRICS_REGISTRY: Dict[str, MetricMetadata] = {
    "radon_cc": MetricMetadata(
        metric_id="radon_cc",
        name="Cyclomatic Complexity",
        description=(
            "Measures the cyclomatic complexity of code, representing the number of "
            "independent paths through the code. Higher complexity indicates more "
            "difficult code to test and maintain."
        ),
        formula="CC = E - N + 2P (where E=edges, N=nodes, P=connected components)",
        ideal_range={"min": 1, "max": 10, "optimal": "1-5", "acceptable": "6-10", "warning": ">10"},
        interpretation={
            "1-5": "Simple code, easy to understand and maintain",
            "6-10": "Moderate complexity, acceptable but monitor",
            "11-20": "High complexity, consider refactoring",
            ">20": "Very high complexity, refactoring recommended"
        },
        references=[
            "https://radon.readthedocs.io/en/latest/intro.html",
            "https://en.wikipedia.org/wiki/Cyclomatic_complexity"
        ],
        category="complexity",
        unit="score"
    ),
    
    "radon_mi": MetricMetadata(
        metric_id="radon_mi",
        name="Maintainability Index",
        description=(
            "Composite metric calculating maintainability based on Halstead Volume, "
            "Cyclomatic Complexity, and Lines of Code. Higher values indicate better maintainability."
        ),
        formula=(
            "MI = 171 - 5.2 * ln(Halstead Volume) - 0.23 * (Cyclomatic Complexity) - "
            "16.2 * ln(Lines of Code)"
        ),
        ideal_range={"min": 0, "max": 100, "optimal": ">20", "warning": "<10"},
        interpretation={
            "A (20-100)": "High maintainability - easy to maintain",
            "B (10-19)": "Medium maintainability - acceptable but can improve",
            "C (0-9)": "Low maintainability - refactoring strongly recommended"
        },
        references=[
            "https://radon.readthedocs.io/en/latest/intro.html",
            "https://www.verifysoft.com/en_maintainability.html"
        ],
        category="maintainability",
        unit="index"
    ),
    
    "pylint_score": MetricMetadata(
        metric_id="pylint_score",
        name="PyLint Code Quality Score",
        description=(
            "Overall code quality score based on static analysis. Evaluates code against "
            "PEP 8 style guide, detects errors, enforces coding standards, and finds code smells."
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
        category="quality",
        unit="score"
    ),
    
    "fpc": MetricMetadata(
        metric_id="fpc",
        name="Functional Pipeline Cohesion",
        description=(
            "Measures cohesion of ML pipeline code by analyzing how well functions and classes "
            "are organized around specific ML pipeline stages. Higher cohesion indicates better "
            "organized and more maintainable ML code."
        ),
        formula=(
            "FPC = (Number of cohesive modules / Total modules) * 10. "
            "A module is cohesive when its functions/methods belong to the same pipeline stage or phase."
        ),
        ideal_range={"min": 0, "max": 10, "optimal": ">7.0", "acceptable": "5.0-7.0", "warning": "<5.0"},
        interpretation={
            "high (7.0-10.0)": "Well-organized ML pipeline code with clear separation of concerns",
            "medium (4.0-6.9)": "Code organization is acceptable but could benefit from better structure",
            "low (0-3.9)": "Poorly organized code, consider restructuring around ML pipeline stages"
        },
        references=["https://github.com/MLS-Toobox/mls_code_generator"],
        category="cohesion",
        unit="score"
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
        category="detection",
        unit="detection"
    ),
}


def get_metric_metadata(metric_id: str) -> MetricMetadata:
    if metric_id not in METRICS_REGISTRY:
        raise KeyError(
            f"Metric '{metric_id}' not found. Available: {list(METRICS_REGISTRY.keys())}"
        )
    return METRICS_REGISTRY[metric_id]
