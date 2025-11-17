"""
Analyzer Execution Orchestrator.

Manages the execution order of analyzers based on their dependencies.
Uses topological sort to ensure dependencies run before dependents.
NO CACHE - just pure execution ordering.
"""

from typing import List, Dict, Set


class AnalyzerExecutionOrchestrator:
    
    
    # Explicit dependency declarations (single source of truth)
    DEPENDENCIES: Dict[str, List[str]] = {
        "pfp": ["fpc"],      
        
    }
    
    @classmethod
    def get_execution_order(cls, requested: List[str]) -> List[str]:
        """
        Calculate execution order using topological sort.
        
        Ensures all dependencies are included and executed first.
        
        Args:
            requested: Analyzers requested by user
            
        Returns:
            Ordered list for execution (dependencies first)
            
        Examples:
            >>> get_execution_order(["pfp"])
            ["ml_content", "fpc", "pfp"]
            
            >>> get_execution_order(["pfp", "pylint"])
            ["ml_content", "fpc", "pfp", "pylint"]
            
            >>> get_execution_order(["pylint"])
            ["pylint"]  # No dependencies - returns immediately
        """
        #  Early exit if no analyzers have dependencies
        if not any(analyzer in cls.DEPENDENCIES for analyzer in requested):
            return requested.copy()  # No ordering needed
        
        #  Collect all needed analyzers (including dependencies)
        all_needed = cls._collect_all_dependencies(requested)
        
        #  Sort topologically (dependencies first)
        ordered = cls._topological_sort(all_needed)
        
        return ordered
    
    @classmethod
    def _collect_all_dependencies(cls, requested: List[str]) -> Set[str]:
        """
        Recursively collect all dependencies.
        
        Args:
            requested: Initial set of analyzers
            
        Returns:
            Complete set including all transitive dependencies
        """
        result = set(requested)
        to_process = list(requested)
        
        while to_process:
            current = to_process.pop(0)
            
            # Get direct dependencies
            deps = cls.DEPENDENCIES.get(current, [])
            
            for dep in deps:
                if dep not in result:
                    result.add(dep)
                    to_process.append(dep)
        
        return result
    
    @classmethod
    def _topological_sort(cls, analyzers: Set[str]) -> List[str]:
        """
        Topological sort using Kahn's algorithm.
        
        Guarantees dependencies execute before dependents.
        
        Args:
            analyzers: Set of all analyzers to sort
            
        Returns:
            Topologically sorted list
            
        Raises:
            ValueError: If circular dependency detected
        """
        # Build dependency graph
        in_degree = {a: 0 for a in analyzers}
        graph = {a: [] for a in analyzers}
        
        for analyzer in analyzers:
            deps = cls.DEPENDENCIES.get(analyzer, [])
            for dep in deps:
                if dep in analyzers:
                    # dep → analyzer (dep must run before analyzer)
                    graph[dep].append(analyzer)
                    in_degree[analyzer] += 1
        
        # Kahn's algorithm
        queue = [a for a in analyzers if in_degree[a] == 0]
        result = []
        
        while queue:
            # Process node with no dependencies
            current = queue.pop(0)
            result.append(current)
            
            # Reduce in-degree for neighbors
            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # Check for cycles
        if len(result) != len(analyzers):
            unprocessed = [a for a in analyzers if a not in result]
            raise ValueError(
                f"Circular dependency detected in analyzers: {unprocessed}"
            )
        
        return result
    
    @classmethod
    def get_dependencies_for(cls, analyzer_id: str) -> List[str]:
        """
        Get direct dependencies for an analyzer.
        
        Args:
            analyzer_id: The analyzer to check
            
        Returns:
            List of direct dependencies
        """
        return cls.DEPENDENCIES.get(analyzer_id, []).copy()
    
    @classmethod
    def has_dependencies(cls, analyzer_id: str) -> bool:
        """Check if analyzer has any dependencies."""
        return analyzer_id in cls.DEPENDENCIES and len(cls.DEPENDENCIES[analyzer_id]) > 0
