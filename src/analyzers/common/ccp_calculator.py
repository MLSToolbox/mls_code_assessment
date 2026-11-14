"""
Shared Conceptual Cohesion (CCP_i) calculator for ML pipeline components.

Implements the formula from the paper's cohesion-metrics proposal:

    CCP_i(C) = 5 - MP(C) - MS(C) - 2 * MPC(C)      i in {m, p}

where, for a software component C (a module/file or a package/directory):
    MP(C)  = 1 if C spans multiple pipeline phases, else 0
    MS(C)  = 1 if C spans multiple pipeline stages, else 0
    MPC(C) = 1 if C mixes ML pipeline code with non-pipeline code, else 0

The formula yields an integer level in {1, 2, 3, 4, 5} (very_low..very_high),
since MP=1 implies MS=1 (spanning multiple phases implies multiple stages),
leaving 6 valid (MP, MS, MPC) combinations. This module is the single source
of truth for that arithmetic, used by both the module-level (CCPM) and
package-level (CCPP) analyzers so they can never diverge from each other or
from the paper's definition.
"""

from typing import Dict

LEVEL_TO_LABEL = {
    5: 'very_high',
    4: 'high',
    3: 'medium',
    2: 'low',
    1: 'very_low',
}


def calculate_ccp(unique_phases: int, unique_stages: int, has_mixed_content: bool) -> Dict:
    """
    Calculate the CCP_i level and its binary indicators for one component.

    Args:
        unique_phases: Number of distinct pipeline phases the component spans.
        unique_stages: Number of distinct pipeline stages the component spans.
        has_mixed_content: True if the component mixes ML pipeline code with
            code foreign to the pipeline (web API, UI, logs, utilities, ...).

    Returns:
        Dict with the binary indicators (mp, ms, mpc), the resulting integer
        level (1-5), and the paper's qualitative label for that level.
    """
    mp = 1 if unique_phases >= 2 else 0
    ms = 1 if unique_stages >= 2 else 0
    mpc = 1 if has_mixed_content else 0

    level = 5 - mp - ms - 2 * mpc
    level = max(1, min(5, level))

    return {
        'mp': bool(mp),
        'ms': bool(ms),
        'mpc': bool(mpc),
        'ccp_level': level,
        'cohesion_level': LEVEL_TO_LABEL[level],
    }
