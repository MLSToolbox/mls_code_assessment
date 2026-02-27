
"""
Package Detection Utilities.
"""
import ast
import os
from typing import List, Set, Dict, Any, Optional


def find_connected_groups(nodes: List[str], adjacency: dict) -> tuple:
    """
    Identifies connected components (groups) and isolated nodes in a package graph 
    using Depth First Search (DFS).
    Args:
        nodes: List of node names (strings) corresponding to indices 0..m-1
        adjacency: Dict where key is node index (int) and value is set of neighbor indices (Set[int])
        
    Returns:
        tuple(groups, isolated_nodes)
        - groups: List of lists, where each inner list contains node names of a connected group.
        - isolated_nodes: List of node names that have no connections.
    """
    m = len(nodes)
    visited = set()
    groups = []
    for i in range(m):
        if i not in visited:
            # Check if it has any edges (connected component of size > 1)
            # OR if it is a single island.
            if i in adjacency or any(i in adj_set for adj_set in adjacency.values()):
                 # It is part of a graph structure (even if self-loop, theoretically)
                 # Start DFS
                 component = []
                 stack = [i]
                 visited.add(i)
                 while stack:
                     curr = stack.pop()
                     component.append(nodes[curr])
                     # Get neighbors
                     neighbors = adjacency.get(curr, set())
                     for neighbor in neighbors:
                         if neighbor not in visited:
                             visited.add(neighbor)
                             stack.append(neighbor)
                 groups.append(component)
            else:
                 # It's an isolated node (not in adjacency keys or values)
                 # However, the DFS logic handles single-node components too. 
                 # To distinguish "Group of 1" vs "Isolated", strictly speaking:
                 # If we iterate 0..m, any unvisited node starts a new component.
                 # The metrics define "Isolated" as having 0 edges.
                 pass

    visited = set()
    all_components = []
    
    for i in range(m):
        if i not in visited:
            component_indices = []
            stack = [i]
            visited.add(i)
            while stack:
                curr = stack.pop()
                component_indices.append(curr)
                for neighbor in adjacency.get(curr, set()):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        stack.append(neighbor)
            all_components.append(component_indices)
            
    groups = []
    isolated = []
    
    for comp_indices in all_components:
        comp_names = [nodes[idx] for idx in comp_indices]
        if len(comp_indices) > 1:
            groups.append(comp_names)
        else:
            # Size 1: Check if it has a self-loop or really isolated?
            # Metric def: Isolated if R[i][j] is false for all j!=i.
            # In our adjacency dict, usually only relevant edges are added.
            # If it's size 1, it's virtually always isolated in SCPP/FCPP context.
            isolated.extend(comp_names)
            
    # However, sometimes a group of size 1 IS valid if the graph had a self-connection?
    # No, typically irrelevant for cohesion.
    # But wait: SCPP/FCPP logic says "Isolated" if not in connected_indices keys.
    # Let's match exact SCPP/FCPP logic for consistency:
    
    connected_indices = set(adjacency.keys()) | {x for v in adjacency.values() for x in v}
    groups = []
    visited_connected = set()
    
    for i in range(m):
        if i in connected_indices and i not in visited_connected:
            comp = []
            stack = [i]
            visited_connected.add(i)
            while stack:
                curr = stack.pop()
                comp.append(nodes[curr])
                for neighbor in adjacency.get(curr, set()):
                    if neighbor not in visited_connected:
                        visited_connected.add(neighbor)
                        stack.append(neighbor)
            groups.append(comp)
            
    isolated_nodes = [nodes[i] for i in range(m) if i not in connected_indices]
    
    return groups, isolated_nodes

def transverse_tree_to_get_packages_and_files(node, dir_list=None):
    """
    Traverses the directory tree to identify Python packages and their modules.
    
    Args:
        node: Current node in the tree (directory or file)
        dir_list: List of dictionaries to collect package metadata
        
    Returns:
        List[str]: A list of relative paths for Python modules found in the current branch
    """
    n_type = node.get("type")
    n_path = node.get("path", "").lstrip("/")
    
    # Case: Python module (file)
    if n_type == "file":
        n_name = node.get("name", "")
        if n_name.endswith(".py") and n_name != "__init__.py":
            # Return list with single module path
            return [n_path]
        return []

    # Case: Directory (potential package)
    packages_file_path = []
    for child in node.get("children", []):
        # Extend results from recursive calls (always returns a list now)
        packages_file_path.extend(transverse_tree_to_get_packages_and_files(child, dir_list))

    # Identify as package if it's a directory (excluding root) and contains modules
    if n_type == "directory" and n_path:
        dir_list.append({
            "path": n_path,
            "modules": packages_file_path
        })
        
    return packages_file_path

def extract_file_features(tree: ast.AST) -> Dict[str, Any]:
    """
    Extracts relevant features from an AST in a single pass.
    Avoids multiple ast.walk calls across different analyzers.
    """
    from .ast_utils import get_attribute_path
    from .variable_detection import is_likely_global_variable
    
    results = {
        'definitions': set(),
        'imports': [],
        'calls': [],
        'attributes': set(),
        'names': set(),
        'name_nodes': [],
        'constants': set(),
        'files_accessed': set()
    }

    if not tree:
        return results

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            attr_path = get_attribute_path(node)
            if attr_path and attr_path.startswith("self."):
                results['attributes'].add(attr_path)
        
        elif isinstance(node, ast.Name):
            if is_likely_global_variable(node.id):
                results['names'].add(node.id)
            results['name_nodes'].append(node)
            
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            val = node.value
            if is_likely_global_variable(val):
                results['constants'].add(val)
            # Heuristic for files
            if any(ext in val.lower() for ext in ['.csv', '.json', '.parquet', '.xlsx', '.pkl', '.h5', '.pt', '.yaml', '.yml', '.npy']):
                results['files_accessed'].add(val)
                
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            results['definitions'].add(node.name)
            
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            results['imports'].append(node)
            
        elif isinstance(node, ast.Call):
            results['calls'].append(node)

    return results
