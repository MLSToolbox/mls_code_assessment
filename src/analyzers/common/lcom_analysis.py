"""
LCOM (Lack of Cohesion of Methods) analysis utilities.

Provides graph-based analysis to detect disconnected method groups
and identify methods without connections.
"""

from typing import Dict, List, Set, Union


def count_components(adjacency: Dict[str, Union[List[str], Set[str]]], methods: List[str]) -> int:
    """
    Count disconnected components in a method connectivity graph using DFS.
    
    Each component represents a group of methods that are connected to each other
    but isolated from other groups. If n_components > 1, the module likely violates
    the Single Responsibility Principle and should be split.
    
    Args:
        adjacency: Graph where adjacency[method] = list/set of connected methods
        methods: List of all method names in the module
        
    Returns:
        Number of disconnected components (groups)
        
    Example:
        methods = ['f1', 'f2', 'f3', 'f4']
        adjacency = {
            'f1': ['f2'],
            'f2': ['f1'],
            'f3': ['f4'],
            'f4': ['f3']
        }
        Returns: 2 (two disconnected groups: {f1, f2} and {f3, f4})
    """
    visited = set()
    components = 0
    
    def dfs(node: str):
        """Depth-first search to mark all reachable nodes."""
        visited.add(node)
        neighbors = adjacency.get(node, [])
        for neighbor in neighbors:
            if neighbor not in visited:
                dfs(neighbor)
    
    for method in methods:
        if method not in visited:
            components += 1
            dfs(method)
    
    return components


def identify_disconnected_methods(
    adjacency: Dict[str, Union[List[str], Set[str]]], 
    methods: List[str]
) -> List[str]:
    """
    Identify methods that have no connections to any other method.
    
    These methods are candidates for:
    - Extraction to separate modules (if they serve different purposes)
    - Better integration (if they should collaborate with others)
    
    Args:
        adjacency: Graph where adjacency[method] = list/set of connected methods
        methods: List of all method names in the module
        
    Returns:
        List of method names that have no connections
        
    Example:
        methods = ['f1', 'f2', 'f3']
        adjacency = {
            'f1': ['f2'],
            'f2': ['f1'],
            'f3': []  # f3 is disconnected
        }
        Returns: ['f3']
    """
    disconnected = []
    
    for method in methods:
        # Check if this method has any connections
        connections = adjacency.get(method, [])
        if not connections:
            disconnected.append(method)
    
    return disconnected
