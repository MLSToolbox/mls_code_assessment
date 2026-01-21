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

    "ldsc": MetricMetadata(
        metric_id="ldsc",
        name="Linked Data Structure Cohesion",
        description=(
            "Measures how much functions within a module share data or structures. "
            "High values indicate that functions are tightly coupled through shared data."
        ),
        formula=(
            "LDSC = (2 * sum(P_ij)) / (n * (n-1)), where P_ij = 1 if functions i and j "
            "share at least one significant variable or data structure."
        ),
        ideal_range={"min": 0, "max": 1.0, "optimal": ">0.8", "acceptable": "0.6-0.8", "warning": "<0.6"},
        interpretation={
            "0.8-1.0": "Excellent - Maximum structural cohesion",
            "0.6-0.79": "Good - High data sharing",
            "0.4-0.59": "Moderate - Some data sharing",
            "0.2-0.39": "Low - Little data sharing",
            "0.0-0.19": "Very Low - Minimal structural cohesion"
        },
        references=["Internal Definition"],
        category="cohesion"
    ),

    "ifc_m": MetricMetadata(
        metric_id="ifc_m",
        name="Information Flow Cohesion - Modified",
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
    
    "ccpp": MetricMetadata(
        metric_id="ccpp",
        name="Conceptual Cohesion of Pipeline Packages",
        description=(
            "Measures how focused a package is on a specific ML pipeline function. Evaluates "
            "the concentration of ML-related modules within a package and penalizes packages "
            "that span multiple pipeline stages. Higher CCPP indicates better package cohesion "
            "and adherence to single responsibility principle."
        ),
        formula=(
            "CCPP = (n_ml / n_total) × CF, where CF = 1 - ((n_stages - 1) / (MAX_STAGES - 1)). "
            "n_ml = ML modules in package, n_total = total modules, n_stages = unique stages detected, "
            "CF = concentration factor that penalizes stage dispersion."
        ),
        ideal_range={
            "min": 0.0,
            "max": 1.0,
            "optimal": ">0.8",
            "acceptable": "0.6-0.8",
            "warning": "<0.6"
        },
        interpretation={
            "High (0.8-1.0)": "Excellent package purity - focused on single pipeline function with high ML content",
            "Moderate (0.6-0.79)": "Acceptable purity - package is reasonably focused but has room for improvement",
            "Low (0.4-0.59)": "Poor purity - package handles multiple stages or has low ML content, refactoring recommended",
            "Very Low (0.0-0.39)": "Critical purity issues - package lacks clear purpose, immediate refactoring needed"
        },
        references=[
            "https://github.com/MLS-Toobox/mls_code_generator",
            "Single Responsibility Principle - Clean Code by Robert C. Martin"
        ],
        category="cohesion"
    ),

    "pdsc": MetricMetadata(
        metric_id="pdsc",
        name="Package Data Structure Cohesion",
        description=(
            "Measures the structural sharing of data or models between modules of the same package. "
            "High values indicate that modules within a package are tightly coupled through shared resources."
        ),
        formula=(
            "PDSC(P) = (2 * sum(Q_ij)) / (m * (m - 1)), where Q_ij = 1 if modules i and j "
            "access or modify the same data structures or resources."
        ),
        ideal_range={"min": 0, "max": 1.0, "optimal": ">0.8", "acceptable": "0.6-0.8", "warning": "<0.6"},
        interpretation={
            "0.8-1.0": "Excellent - Maximum structural cohesion",
            "0.6-0.79": "Good - High resource sharing",
            "0.4-0.59": "Moderate - Some resource sharing",
            "0.2-0.39": "Low - Little resource sharing",
            "0.0-0.19": "Very Low - Minimal structural cohesion"
        },
        references=["Internal Definition"],
        category="cohesion"
    ),
    
    "pmcr": MetricMetadata(
        metric_id="pmcr",
        name="Package Module Cohesion Ratio",
        description=(
            "Measures the proportion of modules in a package that are interconnected, "
            "considering both code dependencies and shared ML resources (datasets, models, APIs). "
            "Adapts the Connected Pairs Ratio concept to the package level."
        ),
        formula=(
            "PMCR(P) = Mc / (n(n-1)/2), where Mc = number of connected module pairs "
            "(direct or indirect), n = total modules in package."
        ),
        ideal_range={"min": 0, "max": 1.0, "optimal": ">0.8", "acceptable": "0.6-0.8", "warning": "<0.6"},
        interpretation={
            "0.8-1.0": "Excellent - Highly cohesive package",
            "0.6-0.79": "Good - Strong module interconnection",
            "0.4-0.59": "Moderate - Some isolated modules",
            "0.2-0.39": "Low - Many isolated modules",
            "0.0-0.19": "Very Low - Fragmented package"
        },
        references=["Internal Definition"],
        category="cohesion"
    ),

    "ifc_p": MetricMetadata(
        metric_id="ifc_p",
        name="Information Flow Cohesion - Package",
        description=(
            "Measures the functional cooperation between modules of a package via information flow. "
            "Considers module invocations and data consumption (imports)."
        ),
        formula=(
            "IFC-P(P) = (2 * sum(F_ij)) / (m * (m - 1)), where F_ij = 1 if module i invokes module j "
            "or consumes its data."
        ),
        ideal_range={"min": 0, "max": 1.0, "optimal": ">0.8", "acceptable": "0.6-0.8", "warning": "<0.6"},
        interpretation={
            "0.8-1.0": "Excellent - High functional coupling within package",
            "0.6-0.79": "Good - Modules are well connected",
            "0.4-0.59": "Moderate - Some connections between modules",
            "0.2-0.39": "Low - Few connections, loose package",
            "0.0-0.19": "Very Low - Modules are independent"
        },
        references=["Internal Definition"],
        category="cohesion"
    ),
    
    "lpcml": MetricMetadata(
        metric_id="lpcml",
        name="Loose Package Cohesion Modified for ML",
        description=(
            "Measures the number of connected components within a package. "
            "A connected component represents a group of modules related through "
            "dependencies, shared data, model files, or ML library usage. "
            "Lower values indicate better cohesion (ideally 1 component)."
        ),
        formula=(
            "LPCML(P) = |CC(G_P)|, where G_P = (V, E) is the undirected dependency graph. "
            "V = first-level elements (modules/subpackages), "
            "E = edges exist when elements share resources (non-empty intersection)."
        ),
        ideal_range={"min": 1, "max": None, "optimal": "1", "acceptable": "2-3", "warning": ">3"},
        interpretation={
            "1": "Excellent - All modules form a single cohesive unit",
            "2-3": "Acceptable - Package has few disconnected subgroups",
            "4-5": "Moderate - Package fragmentation, consider reorganization",
            ">5": "Poor - Highly fragmented package, refactoring needed"
        },
        references=["Internal Definition - Graph Theory Applied to ML Package Structure"],
        category="cohesion"
    ),

    "scpp": MetricMetadata(
        metric_id="scpp",
        name="Structural Coupling Package Pipeline",
        description=(
            "Measures structural coupling of a package based on shared pipeline resources "
            "(datasets, models, configurations) between its modules and subpackages."
        ),
        formula=(
            "SCPP(P) = (2 * sum(Q_ij)) / (m * (m - 1)), where m = number of direct nodes "
            "(files/subpackages), and Q_ij = 1 if a pair shares pipeline resources."
        ),
        ideal_range={"min": 0, "max": 1.0, "optimal": ">0.6", "acceptable": "0.4-0.6", "warning": "<0.4"},
        interpretation={
            "0.8-1.0": "Very High",
            "0.6-0.8": "High",
            "0.4-0.6": "Medium",
            "0.2-0.4": "Low ",
            "0.0-0.2": "Very Low "
        },
        references=["Internal Definition - SCPP"],
        category="cohesion"
    ),
    "p-lcom": MetricMetadata(
        metric_id="p-lcom",
        name="Package Lack of Cohesion of Modules",
        description="Measures package fragmentation by counting unconnected groups of modules sharing pipeline resources.",
        formula="P-LCOM(P) = |ConnectedComponents(G)|",
        interpretation={
            "1": "High Cohesion (Single Group)",
            ">1": "Low Cohesion (Multiple Groups)"
        },
        ideal_range={"min": 1, "max": 1, "optimal": "1", "acceptable": "1"},
        category="cohesion"
    ),

    "fcpp": MetricMetadata(
        metric_id="fcpp",
        name="Functional Cohesion of Pipeline Packages",
        description=(
            "Measures functional cohesion based on call graph invocations (direct/indirect) "
            "between package modules."
        ),
        formula="FCPP(P) = (2 * sum(F_ij)) / (m * (m - 1))",
        ideal_range={"min": 0, "max": 1.0, "optimal": ">0.6", "acceptable": "0.4-0.6", "warning": "<0.4"},
        interpretation={
            "0.8-1.0": "Very High",
            "0.6-0.8": "High",
            "0.4-0.6": "Medium",
            "0.2-0.4": "Low",
            "0.0-0.2": "Very Low"
        },
        references=["Internal Definition - FCPP"],
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