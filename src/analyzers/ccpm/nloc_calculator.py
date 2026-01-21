

class NLOCCalculator:
    """Calculate Non-comment Lines of Code (NLOC) for Python files."""
    
    def __init__(self, threshold: int):
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
            
            if not stripped:
                continue
            
            if in_multiline_string:
                if multiline_delimiter in stripped:
                    in_multiline_string = False
                continue
            
            if stripped.startswith('"""') or stripped.startswith("'''"):
                multiline_delimiter = stripped[:3]
                if stripped.count(multiline_delimiter) < 2:
                    in_multiline_string = True
                continue
            
            if stripped.startswith('#'):
                continue
            
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
