from metrics.metadata import MetricMetadata


METRICS_REGISTRY = {
    "radon_cc": MetricMetadata(
        metric_id="radon_cc",
        name="Cyclomatic Complexity",
        description=(
            "Complexity score derived from Radon cyclomatic complexity. "
            "The API returns a transformed score where higher is better."
        ),
        formula=(
            "=== Formula ===\n"
            "raw_cc = radon_total_average_cc\n"
            "score = round(10 / (raw_cc ** 0.3), 2)\n\n"
            "=== Notes ===\n"
            "- Output is a 0-10 score.\n"
            "- Higher complexity produces a lower score."
        ),
        ideal_range={"min": 0, "max": 10, "optimal": ">=8.0", "acceptable": "6.0-7.99", "warning": "<6.0"},
        interpretation={
            "8.0-10.0": "Low average complexity and easier-to-test code.",
            "6.0-7.99": "Manageable complexity with some refactoring opportunities.",
            "4.0-5.99": "High complexity trend; refactoring should be planned.",
            "0.0-3.99": "Very high complexity; prioritize simplification."
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
            "Maintainability based on Radon MI, normalized by this API to a 0-10 score."
        ),
        formula=(
            "=== Formula ===\n"
            "module_score = module_mi / 10\n"
            "score = average(module_score)\n\n"
            "=== Notes ===\n"
            "- Raw Radon MI is in [0, 100].\n"
            "- API score is normalized to [0, 10].\n"
            "- Radon rank boundaries map to API as: A >= 2.0, B 1.0-1.99, C < 1.0."
        ),
        ideal_range={"min": 0, "max": 10, "optimal": ">=2.0 (Radon A)", "acceptable": "1.0-1.99 (Radon B)", "warning": "<1.0 (Radon C)"},
        interpretation={
            "2.0-10.0": "Radon rank A: maintainable code.",
            "1.0-1.99": "Radon rank B: moderate maintainability.",
            "0.0-0.99": "Radon rank C: low maintainability."
        },
        references=["https://radon.readthedocs.io/en/latest/intro.html"],
        category="maintainability"
    ),
    "pylint_score": MetricMetadata(
        metric_id="pylint_score",
        name="Code Quality Score",
        description=(
            "Quality score from Pylint analysis, reported on a 0-10 scale."
        ),
        formula=(
            "=== Formula ===\n"
            "score = pylint_global_score\n\n"
            "=== Notes ===\n"
            "- Higher is better.\n"
            "- Score reflects style, potential errors, and code smells."
        ),
        ideal_range={"min": 0, "max": 10, "optimal": ">=8.0", "acceptable": "7.0-7.99", "warning": "<7.0"},
        interpretation={
            "9.0-10.0": "Excellent quality with very few issues.",
            "8.0-8.99": "Good quality with minor improvements.",
            "7.0-7.99": "Acceptable quality; clean up warnings.",
            "5.0-6.99": "Needs improvement across multiple checks.",
            "0.0-4.99": "Poor quality; significant cleanup recommended."
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
            "Evaluates whether each module keeps a focused ML pipeline responsibility."
        ),
        formula=(
            "=== Scoring Model ===\n"
            "- very_high -> 10 points\n"
            "- high -> 8 points\n"
            "- medium -> 5 points\n"
            "- low -> 3 points\n"
            "- very_low -> 1 point\n\n"
            "=== Project Score ===\n"
            "score = average(level_points for scored files)\n\n"
            "=== Notes ===\n"
            "- Files classified as non_ml_file or not_applicable are excluded from scoring.\n"
            "- Cohesion level depends on detected stages, phases, ML-only content, and NLOC threshold."
        ),
        ideal_range={"min": 0, "max": 10, "optimal": ">=8.0", "acceptable": "5.0-7.99", "warning": "<5.0"},
        interpretation={
            "8.0-10.0": "Strong module focus with limited responsibility mixing.",
            "5.0-7.99": "Moderate focus; related responsibilities are mixed.",
            "3.0-4.99": "Low conceptual cohesion; multiple concerns mixed.",
            "0.0-2.99": "Very low cohesion; severe responsibility mixing."
        },
        references=[
            "https://en.wikipedia.org/wiki/Single-responsibility_principle",
            "https://en.wikipedia.org/wiki/Cohesion_(computer_science)"
        ],
        category="cohesion"
    ),
    "file_structure": MetricMetadata(
        metric_id="file_structure",
        name="File Structure Quality",
        description=(
            "Assesses structural consistency of Python files (class-based, functional, script, or mixed patterns)."
        ),
        formula=(
            "=== Formula ===\n"
            "score = ((classes_only * 1.0) + (functions_only * 0.9) + (script_only * 0.6) +\n"
            "         (mixed * 0.5) + (mixed_script * 0.3)) / total_files * 10\n\n"
            "=== Notes ===\n"
            "- Higher weights reward clearer structure.\n"
            "- mixed_script is the most penalized pattern."
        ),
        ideal_range={"min": 0, "max": 10, "optimal": ">=8.0", "acceptable": "6.0-7.99", "warning": "<6.0"},
        interpretation={
            "9.0-10.0": "Excellent structural consistency.",
            "7.0-8.99": "Good overall structure with some weaker files.",
            "6.0-6.99": "Acceptable but inconsistent in parts.",
            "4.0-5.99": "Poor structure; multiple anti-patterns present.",
            "0.0-3.99": "Critical structural issues; refactor urgently."
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
            "Detects required pipeline stages and validates whether the codebase is a complete pipeline."
        ),
        formula=(
            "=== Formula ===\n"
            "score = 10 if all required stages are detected else 0\n\n"
            "=== Notes ===\n"
            "- Binary metric.\n"
            "- Detailed stage coverage is returned in analysis details."
        ),
        ideal_range={"min": 0, "max": 10, "optimal": "10", "warning": "0"},
        interpretation={
            "10": "All required stages were detected.",
            "0": "One or more required stages are missing."
        },
        references=["https://en.wikipedia.org/wiki/Machine_learning"],
        category="detection"
    ),
    "ml_content": MetricMetadata(
        metric_id="ml_content",
        name="ML Content Purity",
        description=(
            "Measures how many analyzed files are classified as ML-related based on non-ML indicator detection."
        ),
        formula=(
            "=== Formula ===\n"
            "ml_ratio = ml_files / total_files\n"
            "score = ml_ratio * 10\n\n"
            "=== Notes ===\n"
            "- A file is marked non-ML if configured non-ML keywords or imports are found.\n"
            "- Higher score means higher concentration of ML-focused files."
        ),
        ideal_range={"min": 0, "max": 10, "optimal": ">=8.0", "acceptable": "5.0-7.99", "warning": "<5.0"},
        interpretation={
            "8.0-10.0": "Mostly ML-focused codebase.",
            "5.0-7.99": "Mixed ML and non-ML content.",
            "0.0-4.99": "Low ML concentration in analyzed files."
        },
        references=[],
        category="detection"
    ),
    "scpm": MetricMetadata(
        metric_id="scpm",
        name="Structural Cohesion of Pipeline Modules",
        description=(
            "Measures structural cohesion through shared variables and shared resource/file access inside modules."
        ),
        formula=(
            "=== Raw Metric ===\n"
            "raw_scpm = shared_pairs / possible_pairs\n\n"
            "=== API Score ===\n"
            "score = average(raw_scpm_across_files) * 10\n\n"
            "=== Notes ===\n"
            "- raw_scpm is in [0, 1], API score is in [0, 10].\n"
            "- Cohesion levels are computed from raw_scpm thresholds (0.8, 0.6, 0.4, 0.2)."
        ),
        ideal_range={"min": 0, "max": 10, "optimal": ">=8.0", "acceptable": "6.0-7.99", "warning": "<6.0"},
        interpretation={
            "8.0-10.0": "Very high structural cohesion.",
            "6.0-7.99": "High structural cohesion.",
            "4.0-5.99": "Medium structural cohesion.",
            "2.0-3.99": "Low structural cohesion.",
            "0.0-1.99": "Very low structural cohesion."
        },
        references=[
            "https://en.wikipedia.org/wiki/Cohesion_(computer_science)",
            "https://en.wikipedia.org/wiki/Lack_of_cohesion_in_methods"
        ],
        category="cohesion"
    ),
    "fcpm": MetricMetadata(
        metric_id="fcpm",
        name="Functional Cohesion of Pipeline Modules",
        description=(
            "Measures functional cohesion through direct and indirect invocation relationships between methods/functions."
        ),
        formula=(
            "=== Raw Metric ===\n"
            "raw_fcpm = connected_pairs / possible_pairs\n\n"
            "=== API Score ===\n"
            "score = average(raw_fcpm_across_files) * 10\n\n"
            "=== Notes ===\n"
            "- raw_fcpm is in [0, 1], API score is in [0, 10].\n"
            "- Connection types include direct calls and shared-helper (indirect) links."
        ),
        ideal_range={"min": 0, "max": 10, "optimal": ">=8.0", "acceptable": "6.0-7.99", "warning": "<6.0"},
        interpretation={
            "8.0-10.0": "Very high functional cohesion.",
            "6.0-7.99": "High functional cohesion.",
            "4.0-5.99": "Medium functional cohesion.",
            "2.0-3.99": "Low functional cohesion.",
            "0.0-1.99": "Very low functional cohesion."
        },
        references=["https://en.wikipedia.org/wiki/Cohesion_(computer_science)"],
        category="cohesion"
    ),
    "ccpp": MetricMetadata(
        metric_id="ccpp",
        name="Conceptual Cohesion of Pipeline Packages",
        description=(
            "Evaluates package-level conceptual focus by combining ML-content ratio with stage/phase consistency."
        ),
        formula=(
            "=== Raw Metric ===\n"
            "content_ratio = n_ml_modules / n_total_modules\n"
            "cohesion_factor = stage_phase_consistency_penalty_adjusted\n"
            "raw_ccpp = content_ratio * cohesion_factor\n\n"
            "=== API Score ===\n"
            "score = average(raw_ccpp_across_packages) * 10\n\n"
            "=== Notes ===\n"
            "- raw_ccpp is in [0, 1], API score is in [0, 10].\n"
            "- Related stages in the same phase receive reduced penalty."
        ),
        ideal_range={"min": 0, "max": 10, "optimal": ">8.0", "acceptable": "6.0-8.0", "warning": "<6.0"},
        interpretation={
            ">8.0": "High conceptual cohesion and high package purity.",
            "6.0-8.0": "Moderate cohesion with limited stage/phase mixing.",
            "4.0-5.99": "Low cohesion; noticeable responsibility mixing.",
            "0.0-3.99": "Very low cohesion; package is highly mixed."
        },
        references=[
            "https://en.wikipedia.org/wiki/Cohesion_(computer_science)",
            "https://en.wikipedia.org/wiki/Single-responsibility_principle"
        ],
        category="cohesion"
    ),
    "scpp": MetricMetadata(
        metric_id="scpp",
        name="Structural Coupling Package Pipeline",
        description=(
            "Measures structural package cohesion based on shared resources across modules and subpackages."
        ),
        formula=(
            "=== Raw Metric ===\n"
            "raw_scpp = indirect_shared_pairs / total_pairs\n\n"
            "=== API Score ===\n"
            "score = average(raw_scpp_across_packages) * 10\n\n"
            "=== Notes ===\n"
            "- raw_scpp is in [0, 1], API score is in [0, 10].\n"
            "- Indirect sharing through connected groups is counted."
        ),
        ideal_range={"min": 0, "max": 10, "optimal": ">=8.0", "acceptable": "6.0-7.99", "warning": "<6.0"},
        interpretation={
            "8.0-10.0": "Very high structural package cohesion.",
            "6.0-7.99": "High structural package cohesion.",
            "4.0-5.99": "Medium structural cohesion with some fragmentation.",
            "2.0-3.99": "Low structural cohesion; fragmented package.",
            "0.0-1.99": "Very low structural cohesion; mostly disconnected."
        },
        references=["https://en.wikipedia.org/wiki/Cohesion_(computer_science)"],
        category="cohesion"
    ),
    "fcpp": MetricMetadata(
        metric_id="fcpp",
        name="Functional Cohesion of Pipeline Packages",
        description=(
            "Measures functional package cohesion from cross-module invocation and dependency relationships."
        ),
        formula=(
            "=== Raw Metric ===\n"
            "raw_fcpp = connected_pairs / total_pairs\n\n"
            "=== API Score ===\n"
            "score = average(raw_fcpp_across_packages) * 10\n\n"
            "=== Notes ===\n"
            "- raw_fcpp is in [0, 1], API score is in [0, 10].\n"
            "- Direct, indirect, and shared-dependency links contribute to connectivity."
        ),
        ideal_range={"min": 0, "max": 10, "optimal": ">=8.0", "acceptable": "6.0-7.99", "warning": "<6.0"},
        interpretation={
            "8.0-10.0": "Very high functional package cohesion.",
            "6.0-7.99": "High functional cohesion.",
            "4.0-5.99": "Medium cohesion with partial collaboration.",
            "2.0-3.99": "Low functional cohesion; weak collaboration.",
            "0.0-1.99": "Very low cohesion; package components are mostly isolated."
        },
        references=["https://en.wikipedia.org/wiki/Cohesion_(computer_science)"],
        category="cohesion"
    )
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
