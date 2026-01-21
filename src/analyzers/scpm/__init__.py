"""
SCPM (Structural Cohesion of Pipeline Modules) Analyzer Package.

Provides structural cohesion analysis for ML pipeline modules,
measuring how methods/functions share data structures and files.
"""

from analyzers.scpm.scpm_analyzer import SCPMAnalyzer

__all__ = ['SCPMAnalyzer']
