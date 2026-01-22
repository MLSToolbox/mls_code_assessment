
"""
Package Detection Utilities.
"""
import os
from typing import List

def get_package_nodes(package_path: str) -> List[str]:
    """
    Get all relevant nodes (modules and subpackages) directly inside a package.
    Used for package-level analysis (SCPP, FCPP).
    """
    nodes = []
    try:
        for item in os.listdir(package_path):
            if item in ["__pycache__", "test", "tests", "examples", ".pytest_cache", "docs", "venv", ".venv"]:
                continue
            
            abs_path = os.path.join(package_path, item)
            
            if os.path.isfile(abs_path):
                # Include Python files, exclude __init__ (it's the package definition, not a child module)
                if item.endswith('.py') and item != '__init__.py':
                    nodes.append(abs_path)
            elif os.path.isdir(abs_path):
                # Include subpackages
                if is_package(abs_path):
                    nodes.append(abs_path)
    except (PermissionError, FileNotFoundError):
        pass
    
    return nodes

def is_package(dir_path: str) -> bool:
    """
    Check if a directory is a valid Python package (contains .py files).
    Relaxed check: doesn't strictly require __init__.py for implicit namespaces, 
    but must contain python code to be relevant.
    """
    for _, _, files in os.walk(dir_path):
        if any(f.endswith(".py") for f in files):
            return True
    return False
