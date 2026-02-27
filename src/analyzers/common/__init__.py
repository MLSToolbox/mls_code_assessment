"""
Common utilities for analyzer implementations.

This package provides reusable components for AST analysis, variable detection,
LCOM analysis, and other shared functionality across different metrics.
"""

from analyzers.common.ast_utils import extract_methods, get_attribute_path
from analyzers.common.lcom_analysis import count_components, identify_disconnected_methods
from analyzers.common.variable_detection import (
    is_likely_global_variable,
    get_files_accessed,
    get_method_calls
)
from analyzers.common.package_utils import  find_connected_groups,transverse_tree_to_get_packages_and_files

__all__ = [
    'extract_methods',
    'get_attribute_path',
    'count_components',
    'identify_disconnected_methods',
    'is_likely_global_variable',
    'get_files_accessed',
    'get_method_calls',
    'find_connected_groups',
    'transverse_tree_to_get_packages_and_files'
]
