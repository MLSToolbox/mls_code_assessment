"""
NLOC (Non-comment Lines of Code) Calculator Module

Calculates the number of non-comment lines of code in Python files.
This is used to determine if a file is large enough to warrant cohesion concerns.
"""

import ast
from typing import Optional


class NLOCCalculator:
    """Calculate Non-comment Lines of Code (NLOC) for Python files."""
    
    def __init__(self, threshold: int = 30):
        """
        Initialize NLOC calculator.
        
        Args:
            threshold: Minimum lines of code for cohesion evaluation
        """
        self.threshold = threshold
    
    def calculate_nloc(self, source: str) -> int:
        """
        Calculate NLOC for a Python source file.
        
        Args:
            source: Python source code as string
            
        Returns:
            Number of non-comment lines of code
        """
        if not source:
            return 0
        
        lines = source.split('\n')
        nloc = 0
        in_multiline_string = False
        multiline_delimiter = None
        
        for line in lines:
            stripped = line.strip()
            
            # Skip empty lines
            if not stripped:
                continue
            
            # Handle multiline strings/docstrings
            if in_multiline_string:
                if multiline_delimiter in stripped:
                    in_multiline_string = False
                continue
            
            # Check for start of multiline string
            if stripped.startswith('"""') or stripped.startswith("'''"):
                multiline_delimiter = stripped[:3]
                # Check if it ends on the same line
                if stripped.count(multiline_delimiter) < 2:
                    in_multiline_string = True
                continue
            
            # Skip single-line comments
            if stripped.startswith('#'):
                continue
            
            # Count as code line
            nloc += 1
        
        return nloc
    
    def is_above_threshold(self, nloc: int) -> bool:
        """
        Check if NLOC is above the configured threshold.
        
        Args:
            nloc: Number of lines of code
            
        Returns:
            True if NLOC is above threshold
        """
        return nloc >= self.threshold
    
    def get_threshold(self) -> int:
        """Get the current NLOC threshold."""
        return self.threshold
